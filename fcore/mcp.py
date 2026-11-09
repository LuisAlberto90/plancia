"""Server MCP (stdio, JSON-RPC 2.0, solo libreria standard): espone la plancia a Copilot Chat in VS Code, Copilot CLI, Claude Code e ogni host MCP.
  plancia mcp            avvia il server (lo lancia l'host, non la persona)
Strumenti: stato, task, passo, richiesta, handoff, verifica_policy. VERIFICATO non e esposto: lo dichiara solo la persona da terminale."""
import contextlib, io, json, os, sys, tempfile
from pathlib import Path

VERSIONE = "0.16.0"
S = {"type": "string"}
PIANO_TOOLS = [
    {"name": "plancia_piano_nuovo", "description": "FIRST action for any request that is not a pure question (sub-agents: never). Write the plan the user follows as a graph: each step one action on an exact file/module/command from .factory/CONTESTO.md, with a check. 3-5 steps for analysis, 6-12 for a change (baseline tests before changing, one step per file, callers, docs, verification, summary). Independent parts = parallel branches.",
     "inputSchema": {"type": "object", "required": ["titolo", "passi"], "properties": {"titolo": {"type": "string"},
         "passi": {"type": "array", "items": {"type": "string"}, "description": "\"A: <verb> <exact file/module/command> => <check>\", \"B: ... <- A\", \"C: ... <-\" (<- X,Y = depends on X,Y; no <- = after previous; <- alone = independent branch)"},
        "nuovo": {"type": "boolean", "description": "true only if a plan of a previous request is still open and this is a new user request. Sub-agents never create plans."}}}},
    {"name": "plancia_passo", "description": "Update a plan step: stato inizia when you start it, fatto with the result in a few words, errore with the cause, saltato with why. Close every step.",
     "inputSchema": {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}, "stato": {"type": "string", "enum": ["inizia", "fatto", "errore", "saltato", "aspetta"]}, "nota": {"type": "string"}}}},
    {"name": "plancia_piano_aggiungi", "description": "Append steps to the current plan when new work appears (\"E: step <- B\").",
     "inputSchema": {"type": "object", "required": ["passi"], "properties": {"passi": {"type": "array", "items": {"type": "string"}}}}},
]
TOOLS = [
    {"name": "plancia_stato", "description": "Task corrente, piano con stato dei passi e salute del progetto. Chiamalo all'inizio di ogni richiesta.",
     "inputSchema": {"type": "object", "properties": {}}, "annotations": {"readOnlyHint": True}},
    {"name": "plancia_task", "description": "Ciclo del task: apri (con i passi del piano) -> conferma (frase esatta della persona) -> avvia -> eseguito. Anche riprendi ed elenco. VERIFICATO lo dichiara solo la persona.",
     "inputSchema": {"type": "object", "required": ["azione"], "properties": {
         "azione": {"type": "string", "enum": ["apri", "conferma", "avvia", "eseguito", "riprendi", "elenco"]},
         "id": {"type": "string", "description": "id breve del task, es. fix-login"}, "titolo": S,
         "frase": {"type": "string", "description": "per conferma: la frase con cui la persona ha confermato, testuale"},
         "analisi": {"type": "boolean", "description": "per apri: task di sola lettura (analisi, domande): nessuna conferma, nessuna modifica ai file"},
         "passi": {"type": "array", "description": "per apri: passi del piano", "items": {"type": "object", "required": ["id", "testo"], "properties": {
             "id": S, "testo": S, "dipende_da": {"type": "array", "items": S}, "chi": {"type": "string", "enum": ["agente", "script", "controllore", "utente"]}}}}}}},
    {"name": "plancia_passo", "description": "Aggiorna un passo del piano attivo. Un passo bloccato dice causa e prossimo passo.",
     "inputSchema": {"type": "object", "required": ["id", "stato"], "properties": {
         "id": S, "stato": {"type": "string", "enum": ["in_corso", "fatto", "bloccato", "aspetta", "problema", "non_necessario"]},
         "frase": {"type": "string", "description": "una riga in italiano semplice"}, "evidenza": {"type": "string", "description": "file o comando che prova il risultato"},
         "causa": S, "prossimo": S}}},
    {"name": "plancia_richiesta", "description": "Richiesta nuova arrivata a meta lavoro: la classifica e la registra nel piano senza rinumerare i passi.",
     "inputSchema": {"type": "object", "required": ["testo"], "properties": {"testo": S, "passo": S, "applica": {"type": "boolean"}}}},
    {"name": "plancia_handoff", "description": "Scrive .factory/STATE.md per la prossima sessione, un altro agente o un collega.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "plancia_verifica_policy", "description": "Prima di modificare un file o lanciare un comando rischioso: chiede alla policy del progetto se e ammesso.",
     "inputSchema": {"type": "object", "properties": {"file": S, "comando": S}}, "annotations": {"readOnlyHint": True}},
]


def _esegui(main, argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try: rc = main(argv)
        except SystemExit as e: rc = e.code if isinstance(e.code, int) else 2
        except Exception as e: print("errore: %s" % e); rc = 1
    return rc or 0, out.getvalue().strip()


def chiama(main, nome, a):
    if os.environ.get("PLANCIA_PLUGIN"): _progetto_plugin()
    if nome.startswith("lava" + "gna_"): nome = "plancia_" + nome.split("_", 1)[1]          # nomi della vecchia Lavagna
    a = a or {}; az = a.get("azione")
    if nome == "plancia_piano_nuovo": return _esegui(main, ["piano", "nuovo"] + (["--new"] if a.get("nuovo") else []) + [a.get("titolo") or "Piano"] + [str(x) for x in a.get("passi") or []])
    if nome == "plancia_piano_aggiungi": return _esegui(main, ["piano", "aggiungi"] + [str(x) for x in a.get("passi") or []])
    if nome == "plancia_passo": return _esegui(main, ["passo", a.get("id", "")] + ([a["stato"]] if a.get("stato") else []) + ([a["nota"]] if a.get("nota") else []))
    if nome == "plancia_stato":
        testi = [_esegui(main, x)[1] for x in (["task", "stato"], ["piano", "mostra"], ["salute"])]
        return 0, "\n\n".join(testi)
    if nome == "plancia_task":
        if az == "elenco": return _esegui(main, ["task", "elenco"])
        if not a.get("id"): return 2, "serve id"
        if az == "apri":
            argv = ["task", "apri", a["id"], a.get("titolo", "")] + (["--analisi"] if a.get("analisi") else [])
            if a.get("passi"):
                f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
                json.dump({"task": a.get("titolo") or a["id"], "steps": a["passi"]}, f, ensure_ascii=False); f.close()
                try: return _esegui(main, argv + ["--da", f.name])
                finally: os.unlink(f.name)
            return _esegui(main, argv)
        if az == "conferma": return _esegui(main, ["task", "conferma", a["id"], a.get("frase") or ""] if a.get("frase") else ["task", "conferma", a["id"]])
        if az in ("avvia", "eseguito", "riprendi"): return _esegui(main, ["task", az, a["id"]])
        return 2, "azione non valida"
    if nome == "plancia_passo":
        argv = ["piano", "passo", a.get("id", ""), a.get("stato", "")] + ([a["frase"]] if a.get("frase") else [])
        for k, o in (("evidenza", "--evidenza"), ("causa", "--causa"), ("prossimo", "--prossimo")):
            if a.get(k): argv += [o, a[k]]
        return _esegui(main, argv)
    if nome == "plancia_richiesta":
        return _esegui(main, ["piano", "evento", a.get("testo", "")] + (["--passo", a["passo"]] if a.get("passo") else []) + (["--applica"] if a.get("applica") else []))
    if nome == "plancia_handoff": return _esegui(main, ["handoff"])
    if nome == "plancia_verifica_policy":
        if a.get("file"): return _esegui(main, ["policy", "verifica", "--file", a["file"]])
        if a.get("comando"): return _esegui(main, ["policy", "verifica", "--comando", a["comando"]])
        return 2, "serve file o comando"
    return 2, "strumento sconosciuto: %s" % nome


def risposta(main, m):
    meth, mid = m.get("method"), m.get("id")
    if meth == "initialize":
        pv = (m.get("params") or {}).get("protocolVersion") or "2025-06-18"
        r = {"protocolVersion": pv, "capabilities": {"tools": {}}, "serverInfo": {"name": "plancia", "version": VERSIONE},
             "instructions": "Plancia: piano visibile del lavoro. Per richieste con piu passi: plancia_stato, poi plancia_task apri con i passi, aggiorna con plancia_passo, chiudi con plancia_task eseguito e plancia_handoff. Prima di toccare file sensibili: plancia_verifica_policy."}
    elif meth == "tools/list": r = {"tools": PIANO_TOOLS if os.environ.get("PLANCIA_MCP") == "piano" else [x for x in TOOLS if x["name"] != "plancia_passo"] + PIANO_TOOLS}     # "piano": solo 3 strumenti, pochi token
    elif meth == "tools/call":
        p = m.get("params") or {}; rc, txt = chiama(main, p.get("name"), p.get("arguments"))
        r = {"content": [{"type": "text", "text": txt or "(nessun output)"}], "isError": rc not in (0,)}
    elif meth == "ping": r = {}
    elif mid is None: return None                                          # notifiche (initialized, cancelled...)
    else: return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "metodo non supportato: %s" % meth}}
    return {"jsonrpc": "2.0", "id": mid, "result": r}


def _progetto_plugin():
    """Plugin: il server MCP non sa in che progetto e. Usa FACTORY_ROOT se e un progetto, altrimenti l'ultimo progetto in cui hai scritto una domanda."""
    try:
        from fcore import auto
        auto.scrivi_boot()
        fr = os.environ.get("FACTORY_ROOT", "")
        if fr and "${" not in fr and (Path(fr) / ".factory").is_dir(): return
        u = json.loads((auto.CASA() / "ultimo.json").read_text(encoding="utf-8")).get("progetto")
        if u and (Path(u) / ".factory").is_dir(): os.environ["FACTORY_ROOT"] = u
    except Exception: pass


def serve(main):
    for s_ in (sys.stdin, sys.stdout):
        try: s_.reconfigure(encoding="utf-8")
        except Exception: pass
    for riga in sys.stdin:
        if not riga.strip(): continue
        try: m = json.loads(riga)
        except Exception:
            print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON non valido"}}), flush=True); continue
        r = risposta(main, m)
        if r is not None: print(json.dumps(r, ensure_ascii=False), flush=True)
    return 0

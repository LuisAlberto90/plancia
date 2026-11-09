"""Panoramica multi-progetto: cosa stanno facendo gli agenti in tutti i progetti, a costo zero in token.
Legge solo cio che gli agenti scrivono comunque: trascrizioni di Claude Code (~/.claude/projects) e Copilot CLI (~/.copilot/session-state),
eventi degli hook (.factory/eventi.jsonl). Non chiama LLM, non chiede nulla agli agenti.
  plancia progetti                 una riga per progetto (stato, task, attenzione)
  plancia progetti aggiungi [DIR]  registra un progetto anche senza sessioni recenti (default: cartella corrente)
  plancia progetti togli DIR
Progetti mostrati: registrati (~/.plancia/progetti.json, anche da `init --scrivi`) + quelli con sessioni nelle ultime ORE_RECENTI ore."""
import glob, json, os, re, sys, time
from pathlib import Path
try: from . import store as lib, sessioni as S
except ImportError: import store as lib, sessioni as S

ORE_RECENTI = 24
LAVORA_S, FERMO_S, INATTIVO_S = 120, 15 * 60, 30 * 60
ATTESA_OK_S = 5                                              # VS Code: comando senza esito dopo 5 s = quasi sempre il tuo "Allow" in chat     # soglie: risposta in corso / nessun segno di vita / turno finito da tempo
ORDINE = ["loop", "errore", "permesso", "fermo", "aspetta", "lavora", "inattivo"]
RIPETIZIONI_LOOP = 3                                       # stessa chiamata identica N volte dall'ultima domanda = loop
NON_LOOP = ("TodoWrite", "TaskUpdate", "TaskCreate", "TaskList", "TaskGet")
NOMI = {"loop": "in loop", "errore": "errori ripetuti", "permesso": "aspetta un permesso", "fermo": "fermo", "aspetta": "aspetta te", "lavora": "lavora", "inattivo": "inattivo"}
_cache = {}


def casa(): return Path(os.environ.get("PLANCIA_HOME") or Path.home() / ".plancia")


def registrati():
    out = []
    for f in (casa() / "progetti.json", Path.home() / ".lavagna" / "progetti.json"):      # anche i progetti registrati dalla vecchia Lavagna
        try: out += [p for p in json.loads(f.read_text(encoding="utf-8")) if os.path.isdir(p) and p not in out]
        except Exception: pass
    return out


def _salva_reg(lst):
    casa().mkdir(parents=True, exist_ok=True); f = casa() / "progetti.json"
    tmp = f.with_suffix(".tmp"); tmp.write_text(json.dumps(sorted(set(lst)), indent=1), encoding="utf-8"); os.replace(tmp, f)


def registra(p):
    p = str(Path(p).resolve()); r = registrati()
    if p not in r: _salva_reg(r + [p])


def _recenti():
    """Cartelle di lavoro delle sessioni Claude/Copilot modificate nelle ultime ORE_RECENTI ore."""
    lim = time.time() - ORE_RECENTI * 3600; out = set()
    cc = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(S.HOME, ".claude")
    for d in glob.glob(os.path.join(cc, "projects", "*")):
        fs = [f for f in glob.glob(os.path.join(d, "*.jsonl")) if os.path.getmtime(f) > lim]
        if fs:
            c = S.cwd_claude(max(fs, key=os.path.getmtime))
            if c and os.path.isdir(c): out.add(os.path.realpath(c))
    for w in glob.glob(os.path.join(S.HOME, ".copilot", "session-state", "*", "workspace.yaml")):
        ev = os.path.join(os.path.dirname(w), "events.jsonl")
        if os.path.isfile(ev) and os.path.getmtime(ev) > lim:
            m = re.search(r"^cwd:\s*(.+)$", open(w, errors="replace").read(), re.M)
            if m and os.path.isdir(m.group(1).strip("'\" ")): out.add(os.path.realpath(m.group(1).strip("'\" ")))
    return out


def progetti():
    """Radici dei progetti: se la cartella di una sessione sta dentro un progetto con .factory/, conta il progetto."""
    out = set()
    for p in set(registrati()) | _recenti():
        q = Path(p); rad = next((x for x in [q, *q.parents] if (x / ".factory").is_dir()), q)
        if str(rad) not in ("/", str(Path.home())): out.add(str(rad))
    return sorted(out)


def _testo(c):
    if isinstance(c, str): return c
    if isinstance(c, list): return " ".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _firma(nome, inp):
    try: s = json.dumps(inp, sort_keys=True, ensure_ascii=False) if not isinstance(inp, str) else inp
    except Exception: s = str(inp)
    return "%s %s" % (nome, s[:400])


def _loop(firme, err_uguali):
    """Ripetizione identica = loop: stessa chiamata N volte, o lo stesso errore 2+ volte."""
    k, n = max(firme.items(), key=lambda x: x[1], default=("", 0))
    if n >= RIPETIZIONI_LOOP:
        nome, _, inp = k.partition(" ")
        try: d = json.loads(inp); inp = d.get("command") or d.get("file_path") or d.get("pattern") or d.get("path") or inp
        except Exception: pass
        return "ripete %s %s (%d volte)" % (nome, lib.redigi(str(inp), 70), n)
    e, ne = max(err_uguali.items(), key=lambda x: x[1], default=("", 0))
    if ne >= 2 and e: return "stesso errore %d volte: %s" % (ne, lib.redigi(e, 90))
    return ""


def _ts_utc(s):
    import calendar
    try: return calendar.timegm(time.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S"))
    except Exception: return None


def _oggi(ts): return str(ts or "")[:10] == time.strftime("%Y-%m-%d") or str(ts or "")[:10] == time.strftime("%Y-%m-%d", time.gmtime())


def stato_claude(f):
    """Stato di una sessione Claude Code dalla trascrizione (con cache su mtime+dimensione)."""
    k = (f, os.path.getmtime(f), os.path.getsize(f))
    if k in _cache: return dict(_cache[k], eta=int(time.time() - k[1]))
    pend, ultimo, testo, errori, err_txt, tok, modello, prompt_ts, domanda, rami = {}, None, "", [], "", 0, "", None, "", S.Rami()
    firme, err_uguali, dom_agente, amb = {}, {}, {}, []
    for l in open(f, encoding="utf-8", errors="replace"):
        try: d = json.loads(l)
        except Exception: continue
        m = d.get("message")
        if not isinstance(m, dict) or d.get("isSidechain"): continue
        c = m.get("content")
        if d.get("type") == "assistant":
            ultimo = "assistant_tool" if isinstance(c, list) and any(isinstance(b, dict) and b.get("type") == "tool_use" for b in c) else "assistant_text"
            for b in c if isinstance(c, list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    pend[b.get("id")] = b.get("name")
                    if b.get("name") == "AskUserQuestion": dom_agente[b.get("id")] = lib.redigi((((b.get("input") or {}).get("questions") or [{}])[0] or {}).get("question") or "ti ha fatto una domanda", 140)
                    if b.get("name") == "ExitPlanMode": dom_agente[b.get("id")] = "propone un piano e aspetta la tua approvazione"
                    if b.get("name") not in NON_LOOP and not str(b.get("name", "")).startswith("mcp__plancia"):
                        k2 = _firma(b.get("name"), b.get("input")); firme[k2] = firme.get(k2, 0) + 1
                    if b.get("name") in ("Task", "Agent"): rami.lancio(b)
            t = _testo(c).strip()
            if t: testo = t
            if t and not any(isinstance(b, dict) and b.get("type") == "tool_use" for b in c if isinstance(c, list)): rami.testo_finale()
            u = m.get("usage") or {}
            if _oggi(d.get("timestamp")): tok += u.get("input_tokens", 0) + u.get("output_tokens", 0) + u.get("cache_creation_input_tokens", 0)
            modello = m.get("model") or modello
        elif d.get("type") == "user":
            res = [b for b in c if isinstance(b, dict) and b.get("type") == "tool_result"] if isinstance(c, list) else []
            for b in res:
                for x in S.problemi_ambiente(_testo(b.get("content")) or str(b.get("content"))[:4000]):
                    if x not in amb: amb.append(x)
                pend.pop(b.get("tool_use_id"), None); dom_agente.pop(b.get("tool_use_id"), None); rami.risultato(b.get("tool_use_id"), b.get("is_error"))
                if b.get("is_error"):
                    errori.append(d.get("timestamp")); err_txt = _testo(b.get("content")) or str(b.get("content"))[:200]
                    ke = err_txt.strip()[:120]; err_uguali[ke] = err_uguali.get(ke, 0) + 1
            g = S.testo_grezzo(m)
            if res: ultimo = "tool_result"
            elif S.ritorno_subagente(g): rami.ritorno(g); ultimo = "tool_result"           # un sotto-agente ha consegnato: l'agente principale riprende
            elif S.testo_utente(m): ultimo = "prompt"; prompt_ts = d.get("timestamp"); errori = []; domanda = S.testo_utente(m); testo = ""; rami.prompt(); firme, err_uguali = {}, {}      # errori e risposta contati dall'ultimo prompt
    r = {"fonte": "claude", "id": os.path.basename(f)[:8], "ultimo": ultimo, "in_sospeso": list(pend.values())[-1:] , "errori": len(errori),
         "errore_testo": lib.redigi(err_txt, 160), "risposta": lib.redigi_testo(testo), "domanda": lib.redigi_testo(domanda, 300), "domanda_ts": prompt_ts, "sotto_agenti": [lib.redigi(x, 80) for x in rami.in_corso()], "loop": _loop(firme, err_uguali), "domanda_agente": list(dom_agente.values())[-1] if dom_agente else "", "ambiente": amb[-4:],
         "token_oggi": tok, "modello": modello, "file": f, "mtime": k[1], "chiusa": False}
    _cache[k] = r
    return dict(r, eta=int(time.time() - k[1]))


def stato_copilot(f):
    k = (f, os.path.getmtime(f), os.path.getsize(f))
    if k in _cache: return dict(_cache[k], eta=int(time.time() - k[1]))
    pend, ultimo, testo, errori, err_txt, tok, modello, domanda, chiusa = {}, None, "", 0, "", 0, "", "", False
    firme, err_uguali = {}, {}
    for l in open(f, encoding="utf-8", errors="replace"):
        try: d = json.loads(l)
        except Exception: continue
        t, x = str(d.get("type") or ""), d.get("data") or {}
        if t == "user.message" and S.copilot_sub(x, [v for v in pend.values() if str(v).lower() in S.SUB_TOOL]): ultimo = "assistant_tool"; continue   # sotto-agente: non e la tua domanda
        if t == "user.message": ultimo = "prompt"; errori = 0; domanda = str(x.get("content") or ""); testo = ""; chiusa = False; firme, err_uguali = {}, {}
        elif t in ("session.end", "session.shutdown", "session.ended"): chiusa = True
        elif t == "tool.execution_start":
            pend[x.get("toolCallId") or len(pend)] = x.get("toolName"); ultimo = "assistant_tool"
            k2 = _firma(x.get("toolName"), x.get("arguments") or x.get("toolArgs")); firme[k2] = firme.get(k2, 0) + 1
        elif t == "tool.execution_complete":
            pend.pop(x.get("toolCallId"), None); ultimo = "tool_result"
            if x.get("success") is False or x.get("error"):
                errori += 1; err_txt = str(x.get("error") or (x.get("result") or {}).get("content") or "")[:200]; ke = err_txt.strip()[:120]; err_uguali[ke] = err_uguali.get(ke, 0) + 1
        elif t.startswith("assistant.message"):
            if x.get("content"): testo = str(x["content"])
            ultimo = "assistant_tool" if x.get("toolRequests") else "assistant_text"
        elif t in ("assistant.turn_end", "session.idle"): ultimo = "assistant_text"
        elif t == "session.usage_record":
            u = x.get("usage") or {}; modello = u.get("model") or modello
            if _oggi(d.get("timestamp")): tok += u.get("inputTokens", 0) + u.get("outputTokens", 0) + u.get("cacheWriteTokens", 0)
    r = {"fonte": "copilot", "id": os.path.basename(os.path.dirname(f))[:8], "ultimo": ultimo, "in_sospeso": list(pend.values())[-1:], "errori": errori,
         "errore_testo": lib.redigi(err_txt, 160), "risposta": lib.redigi_testo(testo), "domanda": lib.redigi_testo(domanda, 300), "loop": _loop(firme, err_uguali),
         "token_oggi": tok, "modello": modello, "file": f, "mtime": k[1], "chiusa": chiusa}
    _cache[k] = r
    return dict(r, eta=int(time.time() - k[1]))


def processi(rad):
    """Quanti claude / copilot sono aperti con cartella dentro il progetto (Linux /proc; altrove None = non so)."""
    if os.environ.get("PLANCIA_NO_PROC") or not os.path.isdir("/proc/self"): return None
    n = {"claude": 0, "copilot": 0}; rad = os.path.realpath(rad)
    for pid in os.listdir("/proc"):
        if not pid.isdigit(): continue
        try:
            cmd = open("/proc/%s/cmdline" % pid, "rb").read().split(b"\0"); cwd = os.path.realpath(os.readlink("/proc/%s/cwd" % pid))
        except Exception: continue
        if not (cwd == rad or cwd.startswith(rad + os.sep)): continue
        nomi = [os.path.basename(x.decode(errors="ignore")) for x in cmd[:3] if x]
        for k in n:
            if k in nomi or any(x.startswith(k + "-") or x == k + ".js" for x in nomi): n[k] += 1; break
    return n


def classifica(s, notifica_ts=0):
    """Stato leggibile di una sessione: regole fisse, nessun LLM."""
    e, u = s["eta"], s["ultimo"]
    if s.get("domanda_agente") and s["in_sospeso"]: return "aspetta"                       # ti ha fatto una domanda o chiede di approvare un piano
    if s.get("loop") and e < FERMO_S and s["ultimo"] != "assistant_text": return "loop"
    if s["errori"] >= 3: return "errore"
    if s["in_sospeso"] and u == "assistant_tool":
        lungo = any(x in ("Bash", "Task", "Agent", "bash", "shell") for x in s["in_sospeso"])      # comandi lunghi: non e per forza un permesso
        if notifica_ts >= s["mtime"] - 2 or (not lungo and e > LAVORA_S and e < FERMO_S): return "permesso"
        return "lavora" if e < FERMO_S else "fermo"
    if u in ("prompt", "tool_result"): return "lavora" if e < LAVORA_S * 3 else "fermo"
    if u == "assistant_text" and s.get("sotto_agenti") and e < FERMO_S: return "lavora"           # aspetta i suoi sotto-agenti, non te
    if u == "assistant_text": return "aspetta" if e < INATTIVO_S else "inattivo"
    return "inattivo"


def _f(n): return "%.1fM" % (n / 1e6) if n >= 1e6 else "%.0fk" % (n / 1e3) if n >= 1e3 else str(n)


def _eta(s): return "%ds" % s if s < 90 else "%d min" % (s // 60) if s < 5400 else "%d ore" % (s // 3600) if s < 48 * 3600 else "%d giorni" % (s // 86400)


def scheda(rad, soglia_token=None):
    """Una scheda per progetto: sessioni recenti con stato, task/piano se c'e .factory, punti di attenzione."""
    os.environ["FACTORY_ROOT"] = rad
    soglia_token = soglia_token or int(os.environ.get("PLANCIA_SOGLIA_TOKEN", "3000000"))
    trovate, _ = S.trova_sessioni(rad)
    lim = time.time() - ORE_RECENTI * 3600
    try:
        from . import archivio as A
        lim = max(lim, A.da())                                          # dopo "plancia archivia": solo il lavoro nuovo
    except Exception: pass
    eventi = lib.leggi_righe("eventi.jsonl", 2000) if (Path(rad) / ".factory").is_dir() else []
    notif = {}
    for ev in eventi:
        if ev.get("tipo") == "hook:Notification":
            try: notif[ev.get("sessione", "")] = time.mktime(time.strptime(ev["ts"], "%Y-%m-%dT%H:%M:%S"))
            except Exception: pass
    fine = {}
    for ev in eventi:
        if ev.get("tipo", "").lower() == "hook:sessionend" and ev.get("sessione"): fine[ev["sessione"][:8]] = ev.get("ts", "")
    sess = []
    for k, f in trovate:
        if os.path.getmtime(f) < lim: continue
        try: s = stato_claude(f) if k == "claude" else stato_copilot(f)
        except Exception: continue
        s["stato"] = classifica(s, max((v for sid, v in notif.items() if sid and s["id"] and sid.startswith(s["id"][:8])), default=0)); s["eta_txt"] = _eta(s["eta"]); s.pop("file", None)
        if s["id"][:8] in fine: s["chiusa"] = True
        sess.append(s)
    try:                                                              # agenti senza trascrizione (chat di VS Code): stato dagli eventi degli hook
        from . import richieste as RQ
        for r in RQ.da_eventi(eventi if len(eventi) >= 300 else lib.leggi_righe("eventi.jsonl", 2000)):
            a = r["attivita"][-1] if r["attivita"] else None; fine = _ts_utc(r["fine"]) or time.time(); e = int(time.time() - fine)
            pend = a and a["esito"] == "in corso" and a["tipo"] != "sotto-agente"   # un sotto-agente che gira non e un permesso
            chiede = pend and a["tipo"] in ("comando", "web") and not a.get("bg")          # in VS Code questi passano dal tuo "Allow"
            st = "aspetta" if r["finita"] else ("permesso" if pend and (e > LAVORA_S or (chiede and e >= ATTESA_OK_S)) else ("lavora" if e < 6 * 60 else "fermo"))
            sess.append({"fonte": r["fonte"], "id": r["sessione"], "ultimo": None, "in_sospeso": [a["tipo"]] if pend else [], "errori": r["errori"], "errore_testo": "",
                         "risposta": "", "domanda": r["domanda"], "attesa": lib.redigi(a["cosa"], 140) if pend else "", "sotto_agenti": [], "loop": "", "domanda_agente": "", "ambiente": r.get("ambiente") or [], "token_oggi": 0, "modello": "",
                         "mtime": fine, "eta": e, "eta_txt": _eta(e), "stato": st, "chiusa": e > 2 * 3600, "da_hook": True})
    except Exception: pass
    pr = processi(rad)
    if pr is not None:                                            # tante sessioni aperte quanti processi vivi: le piu recenti
        for fonte in ("claude", "copilot"):                            # (le sessioni da hook non hanno processo: restano come sono)
            for i, s in enumerate(sorted([x for x in sess if x["fonte"] == fonte and not x["chiusa"]], key=lambda x: -x["mtime"])):
                if i >= pr[fonte]: s["chiusa"] = True
    for s in sess:
        if s["chiusa"] or s["eta"] > 2 * 3600: s["chiusa"] = True; s["stato"] = "chiusa"
    aperte = sorted([s for s in sess if not s["chiusa"]], key=lambda s: (ORDINE.index(s["stato"]), s["eta"]))
    chiuse = sorted([s for s in sess if s["chiusa"]], key=lambda s: s["eta"])
    att = []
    for s in aperte:
        if s["stato"] == "loop": att.append(("loop", "%s in loop: %s — interrompilo (Esc) e cambia approccio" % (s["fonte"], s["loop"])))
        elif s["stato"] == "aspetta" and s.get("domanda_agente"): att.append(("domanda", "%s ti ha fatto una domanda: %s — rispondi nel terminale" % (s["fonte"], s["domanda_agente"])))
        elif s["stato"] == "errore": att.append(("errore", "%s: %d errori di strumenti dall'ultima domanda — %s" % (s["fonte"], s["errori"], s["errore_testo"][:90])))
        elif s["stato"] == "permesso": att.append(("permesso", "la chat (%s) aspetta il tuo Allow per: %s · da %s" % (s["fonte"], s.get("attesa") or ", ".join(x for x in s["in_sospeso"] if x) or "un'azione", s["eta_txt"])))
        elif s["stato"] == "fermo": att.append(("fermo", "%s: nessun segno di vita da %s (%s)" % (s["fonte"], s["eta_txt"], ", ".join(x for x in s["in_sospeso"] if x) or "dopo la domanda")))
    vis = set()
    for s in aperte + chiuse[:2]:
        for cosa, come in s.get("ambiente") or []:
            if cosa not in vis: vis.add(cosa); att.append(("ambiente", "ambiente: %s — %s" % (cosa, come)))
    neg = [e for e in eventi if e.get("tipo") == "guardia_negata" and _oggi(e.get("ts"))]
    if neg: att.append(("guardia", "guardia: %s negat%s oggi, ultima: %s" % ("1 azione" if len(neg) == 1 else "%d azioni" % len(neg), "a" if len(neg) == 1 else "e", (neg[-1].get("messaggio") or "").split(". Chiedi")[0][:90])))
    tok = sum(s["token_oggi"] for s in sess)
    if tok > soglia_token: att.append(("token", "consumo alto oggi: %s token (soglia %s)" % (_f(tok), _f(soglia_token))))
    task = None
    if (Path(rad) / ".factory").is_dir():
        try:
            from . import task as T, piano_modello as M
            cur = (lib.task_corrente() or {}).get("task_id"); t = T.stati_task().get(cur) if cur else None
            if t and t["stato"] not in T.CHIUSE + ("ESEGUITO",):
                task = {"id": t["id"], "stato": t["stato"], "titolo": t["titolo"], "analisi": t.get("analisi", False)}
                if t["piano"]:
                    st = lib.leggi(t["piano"])["steps"]; task["fatti"] = sum(M.canon(x.get("stato")) in ("FATTO", "VERIFICATO", "NON_NECESSARIO") for x in st); task["passi"] = len(st)
                    bl = [x["id"] for x in st if M.canon(x.get("stato")) == "BLOCCATO"]
                    if bl: att.append(("bloccato", "task %s: passi bloccati %s" % (t["id"], ", ".join(bl[:5]))))
        except Exception: pass
    if not task and aperte:
        pf = S.piano_da_sessioni([S.leggi_sessione(f, False) for k, f in trovate[:1] if k == "claude" and os.path.getmtime(f) > lim])
        if pf: task = {"id": "(lista dell'agente)", "stato": "", "titolo": pf["task"], "fatti": sum(x["stato"] in ("FATTO",) for x in pf["steps"]), "passi": len(pf["steps"])}
    peso = {"loop": -1, "errore": 0, "domanda": 1, "ambiente": 2, "permesso": 1, "fermo": 2, "bloccato": 2, "guardia": 3, "aspetta": 4, "token": 5}
    att.sort(key=lambda a: peso.get(a[0], 9))
    stato = aperte[0]["stato"] if aperte else "inattivo"
    try: piano = stato_piano(rad, aperte)
    except Exception: piano = None
    ultima = None
    try:                                                                  # l'ultima richiesta, anche di settimane fa: per capire al volo dove eri rimasto
        try: from . import richieste as RQ
        except ImportError: import richieste as RQ
        u = (RQ.tutte(rad, 1) or [None])[0]
        if u:
            ep = RQ._ts(u.get("fine") or u.get("inizio")) or 0
            ultima = {"domanda": lib.redigi_testo(u.get("domanda") or "", 300), "fonte": u.get("fonte"), "finita": bool(u.get("finita")), "eta_txt": _eta(int(time.time() - ep)) if ep else "",
                      "quando": time.strftime("%d/%m %H:%M", time.localtime(ep)) if ep else "", "modifiche": len(u.get("file") or []), "errori": u.get("errori") or 0, "risposta": lib.redigi_testo(u.get("risposta") or "", 1200)}
    except Exception: pass
    return {"piano": piano, "ultima": ultima, "radice": rad, "nome": Path(rad).name, "stato": stato, "stato_txt": NOMI[stato] if aperte else "nessun agente aperto", "sessioni": aperte[:4], "chiuse": [{k: s[k] for k in ("fonte", "id", "eta_txt", "domanda", "token_oggi")} for s in chiuse[:6]],
            "processi": pr, "attenzione": [{"tipo": a, "testo": b} for a, b in att[:6]],
            "token_oggi": tok, "token_txt": _f(tok), "task": task, "plancia": (Path(rad) / ".factory").is_dir()}


def tutte(soglia_token=None):
    vecchio = os.environ.get("FACTORY_ROOT")
    try: sc = [scheda(p, soglia_token) for p in progetti()]
    finally:
        if vecchio is None: os.environ.pop("FACTORY_ROOT", None)
        else: os.environ["FACTORY_ROOT"] = vecchio
    sc.sort(key=lambda x: (ORDINE.index(x["stato"]), -max([0] + [s["mtime"] for s in x["sessioni"]])))
    for x in sc:
        for s in x["sessioni"]: s.pop("mtime", None)
    return {"aggiornato": time.strftime("%Y-%m-%d %H:%M:%S"), "progetti": sc, "conteggi": {k: sum(1 for x in sc if x["stato"] == k) for k in ORDINE}}


def main(a):
    if a[:1] == ["aggiungi"]: registra(a[1] if len(a) > 1 else os.getcwd()); print("registrato"); return 0
    if a[:1] == ["togli"] and len(a) > 1: _salva_reg([p for p in registrati() if p != str(Path(a[1]).resolve())]); print("tolto"); return 0
    if a[:1] in (["-h"], ["--help"]): print(__doc__); return 0
    d = tutte()
    if "--json" in a: print(json.dumps(d, ensure_ascii=False, indent=1)); return 0
    if not d["progetti"]: print("nessun progetto: lavora con un agente in un progetto, oppure `plancia progetti aggiungi`"); return 0
    for p in d["progetti"]:
        t = p["task"]; tt = ("%s %s%s" % (t["id"], t["stato"], " %s/%s" % (t.get("fatti"), t.get("passi")) if t.get("passi") else "")) if t else "-"
        print("%-12s %-22s %-28s token oggi %s" % (p["stato_txt"][:12], p["nome"][:22], tt[:28], p["token_txt"]))
        for x in p["attenzione"][:3]: print("    ! " + x["testo"][:110])
    return 0


if __name__ == "__main__": sys.exit(main(sys.argv[1:]))


def stato_piano(rad, aperte):
    """Il piano dell'ultima richiesta: in_costruzione (l'agente lavora e non l'ha ancora scritto) / pronto / nessuno (risposta diretta)."""
    fac = Path(rad) / ".factory"
    if not fac.is_dir(): return None
    try: from . import piano_modello as M
    except ImportError: import piano_modello as M
    pr = None
    for e in reversed(lib.leggi_righe("eventi.jsonl", 600)):
        if str(e.get("tipo", "")).lower() in ("hook:userpromptsubmit", "hook:userpromptsubmitted"): pr = e.get("ts"); break
    try: tp = time.mktime(time.strptime(pr, "%Y-%m-%dT%H:%M:%S")) if pr else 0
    except Exception: tp = 0
    ult, ue = None, 0
    for f in (fac / "piani").glob("*.json"):
        try: d = json.loads(f.read_text(encoding="utf-8"))
        except Exception: continue
        ep = max(d.get("creato_epoch") or 0, f.stat().st_mtime)               # un piano esteso con "aggiungi" vale per la richiesta che lo ha esteso
        if ep > ue: ult, ue = d, ep
    lavora = any(s["stato"] in ("lavora", "permesso") for s in aperte)
    if ult and (not tp or ue < tp) and not lavora and time.time() - ue > 6 * 3600:          # piano vecchio, nessuna domanda nuova: non e "pronto", e storia
        return {"stato": "vecchio", "titolo": ult.get("task", "")[:90], "eta_txt": _eta(int(time.time() - ue))}
    if ult and ue >= tp:
        st = [s for s in ult.get("steps", [])]
        c = lambda *k: sum(M.canon(s.get("stato")) in k for s in st)
        return {"stato": "pronto", "titolo": ult.get("task", "")[:90], "passi": len(st), "fatti": c("FATTO", "VERIFICATO", "NON_NECESSARIO"),
                "in_corso": c("IN_CORSO"), "bloccati": c("BLOCCATO"), "voto": (ult.get("qualita") or {}).get("voto"), "eta_txt": _eta(int(time.time() - ue))}
    if tp and lavora and time.time() - tp < 20 * 60: return {"stato": "in_costruzione", "eta_txt": _eta(int(time.time() - tp))}
    if tp: return {"stato": "nessuno", "precedente": ult.get("task", "")[:60] if ult else None}
    return None

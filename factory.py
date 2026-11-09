#!/usr/bin/env python3
"""Plancia: piano, task, guardie, handoff, salute e pannello per qualsiasi progetto, con Claude Code, Copilot (CLI e VS Code) e ogni host MCP.
  plancia init [--modo leggera|governata] [--piano obbligatorio|consigliato] [--scrivi]   prepara il progetto (senza --scrivi mostra soltanto cosa farebbe)
           leggera (default): guardie + osservazione, ~0 token per l'agente. governata: in piu l'agente scrive piano/task (regola + MCP)
  plancia contesto [--scrivi]   mappa del progetto senza LLM (.factory/CONTESTO.md): l'agente la legge invece di esplorare
  plancia metodo [--globale] [--scrivi]   installa la skill plancia-metodo (come affrontare ogni richiesta senza fronzoli ne loop)
  plancia prove [N|verifica N|rapporto]   batteria di prove su un progetto vero, senza toccare la logica
  plancia diagnosi         zip da mandare a chi ti supporta (struttura, configurazioni, eventi, errori; nessun codice sorgente)
  plancia strumenti        skill, server MCP, hook, istruzioni e plugin del progetto, con proposte
  plancia skill-progetto   crea la skill del progetto con i comandi di build/test verificati (--scrivi)
  plancia controlla        controlla l'installazione e dice cosa manca e come sistemarlo
  plancia scollega         toglie dal progetto hook, regola e MCP dell'installazione classica (per passare al plugin) (--scrivi)
  plancia archivia         mette da parte lo storico (piani, eventi, prove) in .factory/archivio/ e riparte pulito
  plancia progetti         tutti i progetti: chi lavora, chi aspetta te, errori, fermi, consumo (anche nel pannello, scheda Progetti)
  plancia piano nuovo "Titolo" "A: ..." "B: ... <- A"   l'agente scrive il piano della richiesta (il pannello lo disegna)
  plancia passo <id> [fatto|errore "motivo"|saltato]   aggiorna un passo (senza stato = inizia)
  plancia piano ...        piano del task (stati, dipendenze, blocchi, evidenze, validatore)            -> piano --help
  plancia task ...         DRAFT -> CONFERMATO -> IN_ESECUZIONE -> ESEGUITO -> VERIFICATO               -> task --help
  plancia policy ...       guardie: file protetti, comandi vietati, sola lettura                         -> policy --help
  plancia handoff          scrive .factory/STATE.md per la prossima sessione o per un collega
  plancia salute           controlli del progetto
  plancia pannello         apre la plancia nel browser (--esporta f.html per un file da condividere)
  plancia mcp              server MCP (lo avvia VS Code / Claude Code / Copilot, non la persona)
Progetto = cartella corrente (o la prima sopra che ha .factory/); FACTORY_ROOT lo forza. Senza installazione: python factory.py ..."""
import json, os, shlex, sys
from pathlib import Path

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI))
from fcore import store, piano, task, handoff, pannello, policy, panoramica, contesto, metodo  # noqa: E402

REGOLA_INIZIO, REGOLA_FINE = "<!-- plancia:inizio -->", "<!-- plancia:fine -->"
VECCHIO = "lava" + "gna"                                                         # nome precedente: per aggiornare i progetti gia preparati
REGOLA = """%s
## Plancia (piano visibile ai colleghi)
Per ogni richiesta con piu di un passo (anche una sola analisi): la PRIMA azione e scrivere il piano; non leggere file ne rispondere prima.
Prima di esplorare leggi `.factory/CONTESTO.md` (mappa del progetto). Metodo: skill `plancia-metodo`.
Se hai gli strumenti MCP `plancia_*` usa quelli; altrimenti il comando `%s ...`.
1. Sola analisi o domanda (nessun file del progetto da modificare): `task apri <id> "titolo" --analisi` (MCP: analisi=true). Nessuna conferma: `task avvia`, lavora, `task eseguito`.
2. Modifiche ai file: `task apri <id> "titolo"` con i passi (id, testo in italiano semplice, dipende_da, chi), poi aspetta la conferma: `task conferma <id> "<frase della persona>"`, `task avvia <id>`.
3. Mentre lavori: `piano passo <id-passo> in_corso|fatto|bloccato "una frase"`. Un passo bloccato dice causa e prossimo passo.
4. Richiesta nuova a meta lavoro: `piano evento "<richiesta>" --applica` (non rinumerare i passi).
5. A fine lavoro: `task eseguito <id>`, poi `handoff`. VERIFICATO lo dichiara solo la persona. Scrivere dentro .factory/ non richiede conferma; richieste di un solo passo non richiedono task.
6. Se un'azione viene negata dalla Plancia (file protetto, comando vietato) non aggirarla: spiega e chiedi alla persona.
%s
"""
HOOK_CLAUDE = ("UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop", "Notification", "SessionEnd")
HOOK_COPILOT = ("sessionStart", "userPromptSubmitted", "preToolUse", "postToolUse", "sessionEnd")


REGOLA_MINI = """%s
## Plancia
For any request that is not a pure question, your FIRST action is the plan (before reading files): `%s piano nuovo "<title>" "A: <step>" "B: <step> <- A" ...`.
Each step = one action on an exact file/module/command from .factory/CONTESTO.md, with a check: "B: <verb> <object> => <check>". 3-5 steps for analysis, 6-12 for a change (baseline tests BEFORE changing, one step per file, callers, docs, verification vs baseline, summary). Independent steps get `<-` alone (parallel branches). If the Plancia says "Improve it now", rewrite once with `piano nuovo --new`. Sub-agents never write plans; the parent marks their steps. Close every step.
In VS Code chat use the MCP tools plancia_piano_nuovo / plancia_passo / plancia_piano_aggiungi instead of the terminal. Then `plancia passo <id>` when starting, `plancia passo <id> fatto "<result in a few words>"` / `errore "<cause>"`; new work found mid-way: `plancia piano aggiungi "E: ... <- B"`. Details: skill plancia-metodo. Reply in the user's language.
%s
"""


def blocco(mini=False): return (REGOLA_MINI if mini else REGOLA) % (REGOLA_INIZIO, store.comando(), REGOLA_FINE)


def aggiungi_regola(f, scrivi, mini=False):
    t = f.read_text(encoding="utf-8") if f.exists() else ""; b = blocco(mini)
    t = t.replace("<!-- %s:inizio -->" % VECCHIO, REGOLA_INIZIO).replace("<!-- %s:fine -->" % VECCHIO, REGOLA_FINE)   # regola della vecchia Lavagna: si aggiorna
    if REGOLA_INIZIO in t:
        i, j = t.index(REGOLA_INIZIO), t.index(REGOLA_FINE) + len(REGOLA_FINE)
        if t[i:j] == b.strip(): return "regola Plancia gia aggiornata in " + f.name
        if not scrivi: return "regola gia presente in %s (verra aggiornata)" % f.name
        f.write_text(t[:i] + b.strip() + t[j:], encoding="utf-8"); return "regola aggiornata in " + f.name
    if scrivi: f.write_text(t + ("\n" if t and not t.endswith("\n") else "") + b, encoding="utf-8")
    return ("aggiunta " + ("la regola minima del piano (~60 token per sessione) " if mini else "") + "a " if scrivi else "aggiungerei a ") + f.name


def _nostro(x): s = json.dumps(x); return "plancia hook" in s or "lavagna hook" in s or "factory.py\\\" hook" in s or "factory.py hook" in s   # anche hook della vecchia Lavagna


def _json(p):
    try: return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception: raise SystemExit("%s non e JSON valido: correggilo a mano, non lo sovrascrivo" % p) from None


def _salva_json(p, d):
    if p.exists(): p.with_name(p.name + ".bak").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def init_hook(r, scrivi, out, modo="governata"):
    cmd = store.comando() + " hook"; evs = list(HOOK_CLAUDE)                     # UserPromptSubmit in leggera registra solo l'ora (0 token)
    cs = r / ".claude" / "settings.json"; d = _json(cs); h = d.setdefault("hooks", {})
    for ev in HOOK_CLAUDE:
        h[ev] = [x for x in h.get(ev, []) if not _nostro(x)] + ([{"hooks": [{"type": "command", "command": "%s %s" % (cmd, ev), "timeout": 15}]}] if ev in evs else [])
        if not h[ev]: h.pop(ev)
    out.append(("scritti" if scrivi else "scriverei") + " hook Claude Code in .claude/settings.json (" + ", ".join(evs) + ")")
    if scrivi: _salva_json(cs, d)
    cf = r / ".github" / "hooks" / "plancia.json"
    out.append(("scritto" if scrivi else "scriverei") + " .github/hooks/plancia.json (hook Copilot CLI / cloud agent)")
    if scrivi:
        _salva_json(cf, {"version": 1, "hooks": {ev: [{"type": "command", "bash": "%s %s" % (cmd, ev), "powershell": "%s %s" % (cmd, ev), "timeoutSec": 15}] for ev in HOOK_COPILOT}})
        vecchio = r / ".github" / "hooks" / "factory-plancia.json"
        if vecchio.exists(): vecchio.unlink(); out.append("rimosso il vecchio .github/hooks/factory-plancia.json")
        v2 = r / ".github" / "hooks" / (VECCHIO + ".json")
        if v2.exists():
            out.append(("rimosso" if scrivi else "rimuoverei") + " il vecchio .github/hooks/%s.json" % VECCHIO)
            if scrivi: v2.unlink()


def scollega(r, scrivi, out):
    """Toglie dal progetto l'installazione classica (hook, regola, MCP) per passare al plugin: nel repository non resta nulla della Plancia."""
    cs = r / ".claude" / "settings.json"
    if cs.exists():
        d = _json(cs); h = d.get("hooks") or {}; tolti = 0
        for ev in list(h):
            nuovi = [x for x in h[ev] if not _nostro(x)]; tolti += len(h[ev]) - len(nuovi)
            if nuovi: h[ev] = nuovi
            else: h.pop(ev)
        if tolti:
            if not h: d.pop("hooks", None)
            out.append(("tolti" if scrivi else "toglierei") + " %d hook da .claude/settings.json" % tolti)
            if scrivi:
                if d: _salva_json(cs, d)
                else: cs.unlink()
    for n in ("plancia.json", VECCHIO + ".json", "factory-plancia.json"):
        f = r / ".github" / "hooks" / n
        if f.exists():
            out.append(("rimosso" if scrivi else "rimuoverei") + " .github/hooks/" + n)
            if scrivi: f.unlink()
    for f in (r / "AGENTS.md", r / "CLAUDE.md"):
        if f.exists():
            t0 = f.read_text(encoding="utf-8").replace("<!-- %s:inizio -->" % VECCHIO, REGOLA_INIZIO).replace("<!-- %s:fine -->" % VECCHIO, REGOLA_FINE)
            if REGOLA_INIZIO in t0:
                if scrivi: f.write_text(t0, encoding="utf-8")
                togli_regola(f, scrivi, out)
                if scrivi and f.name == "CLAUDE.md" and f.read_text(encoding="utf-8").strip() in ("", "@AGENTS.md") and not (r / "AGENTS.md").exists(): f.unlink()
    togli_mcp(r, scrivi, out)
    if not out: out.append("niente da togliere: il progetto non ha l'installazione classica")


def init_mcp_piano(r, scrivi, out):
    parti = [x.strip('"') for x in shlex.split(store.comando(), posix=os.name != "nt")] + ["mcp"]
    vs = r / ".vscode" / "mcp.json"; d = _json(vs)
    d.setdefault("servers", {}).pop(VECCHIO, None)
    d["servers"]["plancia"] = {"type": "stdio", "command": parti[0], "args": parti[1:], "env": {"FACTORY_ROOT": "${workspaceFolder}", "PLANCIA_MCP": "piano"}}
    out.append(("scritto" if scrivi else "scriverei") + " .vscode/mcp.json: 3 strumenti del piano per la chat di VS Code (plancia_piano_nuovo, plancia_passo, plancia_piano_aggiungi)")
    if scrivi: _salva_json(vs, d)


def togli_mcp(r, scrivi, out):
    for f, k in ((r / ".vscode" / "mcp.json", "servers"), (r / ".mcp.json", "mcpServers")):
        d = _json(f)
        for nome in ("plancia", VECCHIO):
            if nome in d.get(k, {}):
                out.append(("tolto" if scrivi else "toglierei") + " il server MCP %s da %s (in modalita leggera non serve e costerebbe token)" % (nome, f.relative_to(r)))
                if scrivi: d[k].pop(nome); _salva_json(f, d)


def togli_regola(f, scrivi, out):
    t = f.read_text(encoding="utf-8") if f.exists() else ""
    if REGOLA_INIZIO in t:
        out.append(("tolta" if scrivi else "toglierei") + " la regola Plancia da %s (in modalita leggera l'agente non la legge: zero token)" % f.name)
        if scrivi:
            i, j = t.index(REGOLA_INIZIO), t.index(REGOLA_FINE) + len(REGOLA_FINE); f.write_text((t[:i].rstrip("\n") + "\n" + t[j:].lstrip("\n")).lstrip("\n"), encoding="utf-8")


def init_mcp(r, scrivi, out):
    parti = [x.strip('"') for x in shlex.split(store.comando(), posix=os.name != "nt")] + ["mcp"]
    srv = {"command": parti[0], "args": parti[1:]}
    vs = r / ".vscode" / "mcp.json"; d = _json(vs); d.setdefault("servers", {})["plancia"] = {"type": "stdio", **srv, "env": {"FACTORY_ROOT": "${workspaceFolder}"}}
    cl = r / ".mcp.json"; e = _json(cl); e.setdefault("mcpServers", {})["plancia"] = srv
    out.append(("scritti" if scrivi else "scriverei") + " server MCP in .vscode/mcp.json (Copilot Chat in VS Code) e .mcp.json (Claude Code)")
    if scrivi: _salva_json(vs, d); _salva_json(cl, e)


def cmd_init(a):
    r = store.radice(); scrivi = "--scrivi" in a; out = ["progetto: %s" % r, "comando plancia: %s" % store.comando()]
    modo = a[a.index("--modo") + 1] if "--modo" in a and a.index("--modo") + 1 < len(a) else ("governata" if any(x in a for x in ("--mcp",)) else (store.config().get("modo") or "leggera"))
    if modo not in ("leggera", "governata"): print("--modo leggera|governata"); return 2
    out.append("modalita: %s" % modo + ("  (guardie + osservazione, l'agente non spende token per la plancia)" if modo == "leggera" else "  (l'agente scrive piano e task: costa qualche token in piu)"))
    if not (r / ".factory").is_dir():
        out.append(("creata" if scrivi else "creerei") + " la cartella .factory/")
        if scrivi: (r / ".factory").mkdir()
    gi = r / ".factory" / ".gitignore"
    if scrivi and (r / ".factory").is_dir() and not gi.exists(): gi.write_text("eventi.jsonl\nhandoff.jsonl\n_stato/\nSTATE.md\nRIPRENDERE.md\n", encoding="utf-8")   # eventi locali: mai in git
    pn = a[a.index("--piano") + 1] if "--piano" in a and a.index("--piano") + 1 < len(a) else (store.config().get("piano") or "obbligatorio")
    if pn not in ("obbligatorio", "consigliato"): print("--piano obbligatorio|consigliato"); return 2
    out.append("piano: %s" % pn + ("  (l'agente non puo modificare file finche non ha scritto il piano della richiesta)" if pn == "obbligatorio" else "  (la skill lo chiede, nessun blocco)"))
    if scrivi: (r / ".factory" / "config.json").write_text(json.dumps({"modo": modo, "piano": pn}, indent=1), encoding="utf-8")
    if not (r / ".factory" / "policy.json").exists():
        out.append(("creata" if scrivi else "creerei") + " .factory/policy.json (guardie: file protetti, comandi vietati)")
        if scrivi:
            import contextlib, io
            with contextlib.redirect_stdout(io.StringIO()): policy.main(["init", "--scrivi"])
    agents, claude = r / "AGENTS.md", r / "CLAUDE.md"
    if modo == "leggera":
        togli_mcp(r, scrivi, out)
        if pn == "obbligatorio": init_mcp_piano(r, scrivi, out)   # chat di VS Code: piano con 3 strumenti MCP (niente conferme del terminale)
        if pn == "obbligatorio":                                   # una regola minima, letta da Claude (via @AGENTS.md) e da Copilot: il piano arriva per primo
            if claude.exists() and REGOLA_INIZIO in claude.read_text(encoding="utf-8") and "@AGENTS.md" in claude.read_text(encoding="utf-8"): togli_regola(claude, scrivi, out)
            out.append(aggiungi_regola(agents, scrivi, mini=True))
            if not claude.exists():
                out.append(("creato" if scrivi else "creerei") + " CLAUDE.md con @AGENTS.md")
                if scrivi: claude.write_text("@AGENTS.md\n", encoding="utf-8")
            elif "@AGENTS.md" not in claude.read_text(encoding="utf-8"): out.append(aggiungi_regola(claude, scrivi, mini=True))
        else: togli_regola(agents, scrivi, out); togli_regola(claude, scrivi, out)
    elif claude.exists() and "@AGENTS.md" in claude.read_text(encoding="utf-8") and not agents.exists(): out.append(aggiungi_regola(claude, scrivi))
    else:
        out.append(aggiungi_regola(agents, scrivi))               # AGENTS.md: letto da Copilot (CLI e VS Code) e da Claude Code via @AGENTS.md
        if not claude.exists():
            out.append(("creato" if scrivi else "creerei") + " CLAUDE.md con @AGENTS.md")
            if scrivi: claude.write_text("@AGENTS.md\n", encoding="utf-8")
        elif "@AGENTS.md" not in claude.read_text(encoding="utf-8"): out.append(aggiungi_regola(claude, scrivi))
    init_hook(r, scrivi, out, modo)                                  # guardie sempre: costano zero token finche non negano
    if "--no-metodo" not in a: metodo.installa(False, scrivi, out)   # come affrontare le richieste: l'agente la carica solo quando serve
    cf = r / ".factory" / "CONTESTO.md"
    if not cf.exists() or "--contesto" in a:
        out.append(("scritta" if scrivi else "scriverei") + " la mappa del progetto in .factory/CONTESTO.md (senza LLM: l'agente non deve esplorare per capire il progetto)")
        if scrivi: cf.write_text(contesto.mappa(r), encoding="utf-8")
    if modo == "governata" and ("--mcp" in a or "--tutto" in a): init_mcp(r, scrivi, out)
    if scrivi: panoramica.registra(r); out.append("progetto registrato nella panoramica (plancia progetti)")
    if not scrivi: out.append("\n(prova a vuoto: aggiungi --scrivi per applicare)")
    print("\n".join(x for x in out if x)); return 0


def cmd_salute(a):
    d = pannello.stato_pannello(False)["salute"]; print("Salute: " + d["stato"])
    for c in d["controlli"]: print("  %-10s %-26s %s" % (c["stato"], c["nome"][:26], c["dettaglio"][:90]))
    return 0 if d["stato"] != "KO" else 1


def main(a):
    if not a or a[0] in ("-h", "--help", "help"): print(__doc__); return 0 if a else 2
    if a[0] in ("--version", "versione"):
        from fcore import mcp; print("plancia " + mcp.VERSIONE); return 0
    c, r = a[0], a[1:]
    mod = {"piano": piano, "task": task, "handoff": handoff, "pannello": pannello, "policy": policy}.get(c)
    if mod and r[:1] in (["-h"], ["--help"]): print(mod.__doc__); return 0
    if mod: return mod.main(r)
    if c == "progetti": return panoramica.main(r)
    if c == "contesto": return contesto.main(r)
    if c == "passo": return piano.passo_breve(r)
    if c == "prove":
        from fcore import prove; return prove.main(r)
    if c in ("strumenti", "skill-progetto"):
        from fcore import strumenti
        return strumenti.main(([c] if c == "skill-progetto" else []) + r)
    if c == "controlla":
        from fcore import controlla
        return controlla.main(r)
    if c == "scollega":
        out = []; scollega(store.radice(), "--scrivi" in r, out)
        print("\n".join(out) + ("" if "--scrivi" in r else "\n(prova a vuoto: aggiungi --scrivi)")); return 0
    if c == "archivia":
        from fcore import archivio
        return archivio.archivia("--prova" not in r)
    if c == "diagnosi":
        from fcore import diagnosi; return diagnosi.main(r)
    if c == "metodo": return metodo.main(r)
    if c == "esporta": return pannello.main(["--esporta"] + (r or ["plancia.html"]))
    if c == "salute": return cmd_salute(r)
    if c == "init": return cmd_init(r)
    if c == "hook":
        from fcore import hook; return hook.main(r)
    if c == "mcp":
        from fcore import mcp; return mcp.serve(main)
    print(__doc__); return 2


def cli():
    for s in (sys.stdout, sys.stderr):                                    # Windows: console non UTF-8
        try: s.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__": cli()

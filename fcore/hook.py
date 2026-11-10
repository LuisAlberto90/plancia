"""Hook per Claude Code, Copilot CLI e chat di VS Code: scrive un evento in .factory/eventi.jsonl. Mai bloccante: qualunque errore -> exit 0, nessun output.
Salva in forma ridotta e senza segreti la domanda (300 caratteri) e cosa fa ogni strumento (file o comando): serve a vedere agenti senza trascrizione leggibile
(chat di VS Code). .factory/eventi.jsonl e locale (in .gitignore). Fuori da un progetto con .factory/ non fa nulla."""
import json, os, sys
from pathlib import Path


def _fonte(d):
    """Chi chiama l'hook: Claude Code (CLAUDE_PROJECT_DIR), chat di VS Code (processo dell'estensione, non un terminale), Copilot CLI."""
    if os.environ.get("CLAUDE_PROJECT_DIR"): return "claude"
    if os.environ.get("VSCODE_PID") and os.environ.get("TERM_PROGRAM") != "vscode": return "vscode"
    if "toolName" in d or "sessionId" in d: return "copilot"
    return "agente"


def _plugin_sessione(d, ev, rad, store):
    """Plugin: all'inizio della sessione la Plancia si accende (pannello, mappa) e l'agente riceve la regola del piano. Una volta per sessione."""
    from fcore import auto
    try:
        c = auto.CASA(); c.mkdir(parents=True, exist_ok=True)
        (c / "ultimo.json").write_text(json.dumps({"progetto": str(rad)}), encoding="utf-8")      # per il server MCP del plugin: su quale progetto scrivere il piano
    except Exception: pass
    sid = str(d.get("session_id") or d.get("sessionId") or "")[:12]
    f = store.dir_() / "_stato" / "regola_data.json"
    try: viste = json.loads(f.read_text(encoding="utf-8"))
    except Exception: viste = []
    if str(ev).lower() == "sessionstart": auto.avvia_pannello(); auto.mappa_se_manca(rad); auto.togli_vecchia_skill()
    if sid and sid in viste:                                              # messaggi successivi della stessa chat: promemoria minimo (~30 token), la regola intera l'ha gia
        if str(ev).lower() != "sessionstart" and (store.config().get("piano") or "obbligatorio") == "obbligatorio":
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "[Plancia] New message. Unless it is a pure question: same work as before -> plancia_piano_aggiungi; different work -> plancia_piano_nuovo with \"nuovo\": true. Plan before reading files."}}, ensure_ascii=False))
        return
    if str(ev).lower() != "sessionstart": auto.avvia_pannello(); auto.mappa_se_manca(rad); auto.togli_vecchia_skill()
    try: f.parent.mkdir(parents=True, exist_ok=True); f.write_text(json.dumps((viste + [sid])[-50:]), encoding="utf-8")
    except Exception: pass
    if (store.config().get("piano") or "obbligatorio") != "obbligatorio": return
    nome = "SessionStart" if str(ev).lower() == "sessionstart" else "UserPromptSubmit"
    print(json.dumps({"hookSpecificOutput": {"hookEventName": nome, "additionalContext": auto.regola(store.comando())}}, ensure_ascii=False))


def main(a):
    try:
        plugin = "--plugin" in a; a = [x for x in a if x != "--plugin"]
        nome = a[0] if a else "evento"
        raw = sys.stdin.buffer.read().decode("utf-8", "replace") if not sys.stdin.isatty() else ""
        d = json.loads(raw) if raw.strip() else {}
        cwd = d.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get("COPILOT_PROJECT_DIR") or os.getcwd()
        p = Path(cwd).resolve()
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        ev = d.get("hook_event_name") or d.get("hookEventName") or nome
        if plugin:                                                            # installata come plugin: ogni progetto si prepara da solo, senza toccare i suoi file
            from fcore import auto
            auto.scrivi_boot()
            rad, nuovo = auto.radice_progetto(p)
            if not rad: return 0
            if auto.ha_hook_propri(rad): return 0                             # installazione classica nel progetto: registra lei, niente doppioni
            if nuovo: auto.prepara(rad)
        else:
            fr = os.environ.get("FACTORY_ROOT")
            rad = Path(fr).resolve() if fr and (Path(fr) / ".factory").is_dir() else next((x for x in [p, *p.parents] if (x / ".factory").is_dir()), None)
            if not rad: return 0
        os.environ["FACTORY_ROOT"] = str(rad)
        from fcore import store
        if plugin and str(ev).lower() in ("sessionstart", "userpromptsubmit", "userpromptsubmitted"):
            _plugin_sessione(d, ev, rad, store)
        if ev in ("PreToolUse", "preToolUse"):                                # guardia: unico caso in cui l'hook puo negare
            from fcore import policy
            strum = d.get("tool_name") or d.get("toolName")
            arg = d.get("tool_input") if "tool_input" in d else d.get("toolArgs")
            ok, mot = policy.verifica_strumento(strum, arg)
            if ok and policy.e_scrittura(strum, arg) and policy.piano_mancante(): ok, mot = False, policy.msg_piano()
            if ok:
                if _fonte(d) == "vscode":                                       # VS Code: serve sapere quando parte uno strumento (sotto-agenti, permessi, guardia attiva)
                    from fcore import richieste as RQ
                    a2 = arg
                    if isinstance(a2, str):
                        try: a2 = json.loads(a2)
                        except Exception: a2 = {"command": a2}
                    tp, cosa = RQ._azione(strum, a2 if isinstance(a2, dict) else {}, str(Path(cwd)))
                    store.evento("hook:PreToolUse", "hook", sessione=str(d.get("session_id") or d.get("sessionId") or "")[:12], fonte="vscode", strumento=strum, cosa="%s|%s" % (tp, cosa) if tp else None)
                return 0
            store.evento("guardia_negata", "policy", strumento=strum, messaggio=store.redigi(mot))
            if d.get("hook_event_name"): print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "[Plancia] " + mot}}, ensure_ascii=False))
            else: print(json.dumps({"permissionDecision": "deny", "permissionDecisionReason": "[Plancia] " + mot}, ensure_ascii=False))
            return 0
        fonte = _fonte(d)
        strum = d.get("tool_name") or d.get("toolName"); arg = d.get("tool_input") if "tool_input" in d else d.get("toolArgs")
        cosa = esito = None; amb = None
        if strum and str(ev).lower() in ("pretooluse", "posttooluse"):
            from fcore import richieste as RQ
            if isinstance(arg, str):
                try: arg = json.loads(arg)
                except Exception: arg = {"command": arg}
            tp, cosa = RQ._azione(strum, arg if isinstance(arg, dict) else {}, str(Path(cwd)))
            cosa = "%s|%s" % (tp, cosa) if tp else None
            if str(ev).lower() == "posttooluse":
                rs = d.get("tool_response") or d.get("toolResult") or {}
                esito = "errore" if isinstance(rs, dict) and (rs.get("is_error") or rs.get("error") or rs.get("success") is False or rs.get("resultType") in ("failure", "error")) else "ok"
                from fcore import sessioni as S_
                amb = S_.problemi_ambiente(json.dumps(rs, ensure_ascii=False)[:20000] if not isinstance(rs, str) else rs[:20000])
            elif fonte != "vscode": return 0                                       # PreToolUse ammesso: si registra solo per VS Code (serve per "aspetta un permesso")
        firma = [str(ev).lower(), str(strum or ""), str(cosa or "")]                # VS Code puo lanciare lo stesso hook da .claude e da .github
        ult = (store.leggi_righe("eventi.jsonl", 1) or [{}])[-1]
        if [str(ult.get("tipo", "")).lower().replace("hook:", ""), str(ult.get("strumento") or ""), str(ult.get("cosa") or "")] == firma:
            import time as _t
            try:
                if abs(_t.time() - _t.mktime(_t.strptime(ult.get("ts", ""), "%Y-%m-%dT%H:%M:%S"))) <= 2: return 0
            except Exception: pass
        store.evento("hook:" + str(ev), "hook", sessione=str(d.get("session_id") or d.get("sessionId") or "")[:12], fonte=fonte,
                     strumento=strum, cosa=cosa, esito=esito, ambiente=[list(x) for x in amb] if amb else None, testo=store.redigi(d.get("prompt") or d.get("userPrompt") or "", 300) or None)
        if ev == "UserPromptSubmit" and store.modo() == "governata":
            from fcore import task
            cur = (store.task_corrente() or {}).get("task_id"); t = task.stati_task().get(cur) if cur else None
            fy = store.comando()
            if t and t["stato"] not in task.CHIUSE:
                ctx = '[Plancia] Task corrente %s (%s). Tieni aggiornato il piano: %s piano passo <id> in_corso|fatto|bloccato "frase". Richiesta nuova a meta lavoro: piano evento "<richiesta>" --applica.' % (cur, t["stato"], fy)
            else:
                ctx = '[Plancia] Nessun piano aperto. Se la richiesta ha piu di un passo (anche una sola analisi), la PRIMA azione e scrivere il piano, prima di leggere file o rispondere: %s task apri <id-breve> "titolo", poi compila .factory/task/<id>/piano.json (passi con id, testo, dipende_da, chi). Aggiorna i passi con piano passo. Se non puoi eseguire comandi usa TaskCreate/TaskUpdate.' % fy
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": ctx}}, ensure_ascii=False))
    except Exception: pass
    return 0


if __name__ == "__main__": sys.exit(main(sys.argv[1:]))

"""Richieste fatte agli agenti, ricostruite dalle trascrizioni (zero token): domanda, durata, token, file modificati, comandi, sotto-agenti, risposta.
Base per le schede Richieste, Piano (piano dell'ultima richiesta) e Riprendere."""
import json, os, re, time
try: from . import store as lib, sessioni as S, policy as PO
except ImportError: import store as lib, sessioni as S, policy as PO

MARCATORE = re.compile(r"\b(?:plancia|factory\.py)\s+(?:piano\s+nuovo\b|passo\s+[A-Za-z0-9][\w.-]{0,15}(?:\s+(?:fatto|ok|errore|bloccato|ko|saltato|non_necessario|aspetta|inizia|in_corso|via)\b)?)")
NORMALE_1 = re.compile(r"(^|[;&|]\s*)(diff|grep|egrep|rg|cmp|test|\[)\b")
GRAVE = re.compile(r"(?i)error|traceback|exception|not found|denied|no such file|fatal|failed")
SCRIVONO = ("Write", "Edit", "MultiEdit", "NotebookEdit", "edit", "create", "write", "str_replace_editor", "apply_patch")
_cache = {}


def _ts(s):
    import calendar
    try: return calendar.timegm(time.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S"))
    except Exception: return None


def _conta(vecchio, nuovo):
    """Righe aggiunte e tolte tra due testi (solo conteggi, nessun contenuto salvato)."""
    import difflib
    a, b = str(vecchio or "").splitlines(), str(nuovo or "").splitlines()
    ag = tl = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag in ("replace", "delete"): tl += i2 - i1
        if tag in ("replace", "insert"): ag += j2 - j1
    return ag, tl


def _righe(n, i):
    """{file: [aggiunte, tolte]} per una modifica fatta con Edit/Write/MultiEdit o apply_patch. Vuoto se non si capisce."""
    if not isinstance(i, dict): return {}
    nl = str(n or "").lower(); f = i.get("file_path") or i.get("path") or i.get("filePath")
    try:
        if nl in ("edit", "str_replace", "str_replace_editor") and f and ("new_string" in i or "new_str" in i):
            return {f: list(_conta(i.get("old_string", i.get("old_str", "")), i.get("new_string", i.get("new_str", ""))))}
        if nl == "multiedit" and f:
            t = [0, 0]
            for e in i.get("edits") or []:
                a, d = _conta(e.get("old_string"), e.get("new_string")); t[0] += a; t[1] += d
            return {f: t}
        if nl in ("write", "create", "create_file") and f and isinstance(i.get("content", i.get("file_text")), str):
            return {f: [len(str(i.get("content", i.get("file_text"))).splitlines()), 0]}
        if nl == "apply_patch":
            out, cur = {}, None
            for l in str(i.get("input") or i.get("patch") or "").splitlines():
                m = re.match(r"\*\*\* (?:Update|Add|Delete) File:[ \t]*(.+?)\s*$", l)
                if m: cur = m.group(1); out[cur] = [0, 0]; continue
                if cur and l.startswith("+") and not l.startswith("+++"): out[cur][0] += 1
                elif cur and l.startswith("-") and not l.startswith("---"): out[cur][1] += 1
            return out
    except Exception: return {}
    return {}


def _somma(r, cwd, n, i):
    for f, (a, d) in _righe(n, i).items():
        f = str(f)
        if cwd and os.path.isabs(f):
            try: f = os.path.relpath(f, cwd)
            except Exception: pass
        f = f.replace("\\", "/"); t = r["righe"].setdefault(f, [0, 0]); t[0] += a; t[1] += d


def _nuova(domanda, ts, fonte, sid):
    return {"domanda": lib.redigi_testo(domanda, 20000), "inizio": ts, "fine": ts, "fonte": fonte, "sessione": sid, "token_lavoro": 0, "token_riletti": 0, "ragionamento": 0, "token_in": 0, "token_out": 0, "token_scritti": 0,
            "strumenti": {}, "file": [], "comandi": [], "errori": 0, "sotto_agenti": 0, "risposta": "", "rami": None, "attivita": [], "finita": False, "_id": {}, "_passo": None, "piano_scritto": False, "ambiente": [], "righe": {}}


PROVA = re.compile(r"(?i)\b(pytest|jest|karma|vitest|unittest|run_tests|mvnw?(\.cmd)?\b.*\b(test|verify|package|install|compile)|gradlew?(\.bat)?\s+.*\b(test|build|check)|npm\s+(run\s+)?(test|build|lint)|pnpm\s+(run\s+)?(test|build|lint)|yarn\s+(test|build|lint)|ng\s+(test|build|lint)|tsc|ruff|flake8|mypy|eslint|dotnet\s+(test|build)|cargo\s+(test|build|check)|go\s+(test|build|vet)|make\s+(test|check|build)|python\S*\s+\S*tests?\S*)\b")
SOLO_DOC = re.compile(r"(?i)\.(md|txt|csv|png|svg|lock)$|(^|/)\.factory/")


def _verifica(att):
    """Dopo l'ultima modifica al codice l'agente ha provato qualcosa (test, build, lint)? Dai fatti registrati, zero token.
    {'modifiche': quante, 'stato': 'ok' | 'fallita' | 'manca'} oppure None se non ha toccato codice."""
    mod = [i for i, a in enumerate(att) if a.get("tipo") == "modifica" and any(not SOLO_DOC.search(f.strip()) for f in re.sub(r" \(con un comando\)$", "", str(a.get("cosa") or "")).split(", ") if f.strip())]
    if not mod: return None
    cmd = [a for a in att[mod[-1] + 1:] if a.get("tipo") == "comando"]; dopo = [a for a in cmd if a.get("prova")]
    dubbio = [a for a in cmd if str(a.get("cosa") or "").endswith("…") and not re.match(r"(?i)^\s*(git|ls|dir|cd|cat|type|echo|get-content|get-childitem)\b", str(a.get("cosa") or ""))]   # comando accorciato: non si vede cosa lanciava
    return {"modifiche": len(mod), "stato": ("fallita" if dopo[-1].get("esito") == "errore" else "ok") if dopo else ("incerto" if dubbio else "manca")}


def _chiudi(r, rami):
    if r is None: return None
    r["rami"] = rami.passi() if rami.r else None
    a, b = _ts(r["inizio"]), _ts(r["fine"]); r["durata_s"] = int(b - a) if a and b and b >= a else None
    r["risposta"] = lib.redigi_testo(r["risposta"], 1200); r["file"] = r["file"][-12:]; r["righe"] = {k: v for k, v in list(r.get("righe", {}).items())[-12:]}; r["comandi"] = r["comandi"][-8:]
    dp = r.pop("_dal_piano", None); r["fuori_piano"] = [a for a in r["attivita"][dp:] if not a.get("passo") and a["tipo"] == "modifica"] if dp is not None else []
    r.pop("_pend", None)
    for a in r["attivita"]:
        if a.get("tipo") == "comando": a["prova"] = bool(a.get("prova")) or bool(PROVA.search(a.get("cmd") or a.get("cosa") or ""))
        a.pop("cmd", None)
    r["verifica"] = _verifica(r["attivita"])
    r.pop("_id", None); r.pop("_passo", None); r["attivita"] = r["attivita"][-60:]
    return r


def _segna(r, cmd):
    """`plancia piano nuovo ...` = piano scritto; `plancia passo X [inizia]` = da qui le azioni sono del passo X."""
    m = re.search(r"\bpasso\s+([A-Za-z0-9][\w.-]{0,15})(?:\s+(\w+))?", cmd)
    if re.search(r"\bpiano\s+nuovo\b", cmd): r["piano_scritto"] = True; r["_passo"] = None; r["_dal_piano"] = len(r["attivita"])
    elif m:
        st = (m.group(2) or "inizia").lower(); chiude = st in ("fatto", "ok", "errore", "bloccato", "ko", "saltato", "non_necessario", "aspetta")
        if chiude and r["piano_scritto"]:                 # azioni dal piano in poi senza passo: sono del passo che si chiude ora
            for a in r["attivita"][r.get("_dal_piano", 0):]:
                if not a.get("passo"): a["passo"] = m.group(1)
        r["_passo"] = None if chiude else m.group(1)


SHELL_N = ("bash", "shell", "powershell", "run_in_terminal", "runinterminal", "terminal")
LEGGE_N = ("read", "view", "read_file", "readfile", "get_file", "open_file")
CERCA_N = ("grep", "glob", "search", "grep_search", "file_search", "semantic_search", "list_dir", "find")


def _azione(n, i, cwd):
    """Una riga leggibile per una chiamata di strumento (Claude Code, Copilot CLI, chat di VS Code): (tipo, cosa)."""
    i = i if isinstance(i, dict) else {}; nl = str(n or "").lower()
    f = i.get("file_path") or i.get("notebook_path") or i.get("path") or i.get("filePath")
    if not f and isinstance(i.get("files"), list) and i["files"]: f = ", ".join(str(x if isinstance(x, str) else (x or {}).get("path") or (x or {}).get("filePath") or "") for x in i["files"][:3])
    if f and cwd and os.path.isabs(str(f)):
        try: f = os.path.relpath(f, cwd).replace("\\", "/")
        except Exception: pass
    if nl in SHELL_N:
        cmd = i.get("command") or i.get("cmd") or ""
        if re.match(r"^\s*(plancia|lavagna|(?:py|python3?)\s+\S*factory\.py\"?)\s+(piano|passo)\b", cmd): return "plancia", cmd
        w = PO.scritture(cmd)
        if w: return "modifica", ", ".join(w[:3]) + " (con un comando)"
        return "comando", lib.redigi(cmd, 90)
    if not f and nl == "apply_patch":                                   # VS Code: il file sta dentro la patch
        fs = re.findall(r"(?m)^\*\*\* (?:Update|Add|Delete) File:[ \t]*(.+?)[ \t]*\r?$", str(i.get("input") or i.get("patch") or ""))
        if fs:
            f = ", ".join(fs[:3])
            if cwd:
                try: f = ", ".join((os.path.relpath(x, cwd) if os.path.isabs(x) else x).replace("\\", "/") for x in fs[:3])
                except Exception: pass
    if nl in LEGGE_N: return "leggi", f or "file"
    if n in SCRIVONO or any(x in nl for x in ("edit", "write", "replace", "create_file", "insert", "apply_patch", "str_replace")): return "modifica", f or "file"
    if nl in CERCA_N or "search" in nl: return "cerca", lib.redigi(i.get("pattern") or i.get("query") or i.get("includePattern") or "", 60)
    if nl in ("vscode_askquestions", "askquestions"): return "domanda", lib.redigi(str(((i.get("questions") or [{}])[0] or {}).get("question") or i.get("question") or ""), 120)
    if n in ("Task", "Agent") or nl in S.SUB_TOOL: return "sotto-agente", lib.redigi(i.get("description") or i.get("prompt") or "", 70)
    if n == "AskUserQuestion": return "domanda", lib.redigi(((i.get("questions") or [{}])[0] or {}).get("question") or "", 120)
    if n == "ExitPlanMode": return "piano", "propone un piano e aspetta la tua approvazione"
    if n in ("WebFetch", "WebSearch") or "fetch" in nl: return "web", lib.redigi(i.get("url") or i.get("query") or "", 70)
    if n in ("TodoWrite", "TaskCreate", "TaskUpdate", "ToolSearch") or nl in ("manage_todo_list", "todowrite"): return None, None
    if re.match(r"^(mcp_+)?(plancia|lavagna)[-_]", nl):
        return "plancia", "passo " + str(i.get("id") or "") + " " + str(i.get("stato") or "") if "passo" in nl else ("piano aggiungi" if "aggiungi" in nl else "piano nuovo")
    return "altro", n


def da_claude(f):
    k = (f, os.path.getmtime(f), os.path.getsize(f))
    if k in _cache: return _cache[k]
    sid = os.path.basename(f)[:8]; out, r, rami = [], None, S.Rami(); visti = set()
    for l in open(f, encoding="utf-8", errors="replace"):
        try: d = json.loads(l)
        except Exception: continue
        m = d.get("message")
        if not isinstance(m, dict) or d.get("isSidechain"): continue
        ts = d.get("timestamp"); c = m.get("content")
        if d.get("type") == "user":
            for b in c if isinstance(c, list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    rami.risultato(b.get("tool_use_id"), b.get("is_error"))
                    if r:
                        for x in S.problemi_ambiente(S.testo_grezzo({"content": b.get("content")}) or str(b.get("content"))[:4000]):
                            if list(x) not in r["ambiente"]: r["ambiente"].append(list(x))
                    if r and b.get("is_error"): r["errori"] += 1
                    if r and b.get("tool_use_id") in r["_id"]:
                        a = r["attivita"][r["_id"][b["tool_use_id"]]]
                        if a["tipo"] != "sotto-agente" or not a.get("bg"):
                            testo = S.testo_grezzo({"content": b.get("content")}) or str(b.get("content") or "")
                            a["esito"] = "errore" if b.get("is_error") else "ok"
                            if b.get("is_error"):
                                if a["tipo"] == "comando" and NORMALE_1.search(a.get("cmd", "")) and not GRAVE.search(testo):
                                    a["esito"] = "ok"; a["nota"] = "uscita 1 da diff/grep: differenze o nessuna corrispondenza, non e un errore"; r["errori"] -= 1
                                else: a["errore"] = lib.redigi(testo.strip().splitlines()[-1] if testo.strip() else "errore senza messaggio", 200)
            g = S.testo_grezzo(m)
            if S.ritorno_subagente(g):
                rami.ritorno(g)
                if r:
                    ap = [a for a in r["attivita"] if a["tipo"] == "sotto-agente" and a["esito"] == "in corso"]
                    if ap: next((a for a in ap if a["cosa"] and a["cosa"].lower() in g.lower()), ap[0])["esito"] = "ok"
                continue
            t = S.testo_utente(m)
            if t:
                if r: out.append(_chiudi(r, rami))
                rami.prompt(); rami.ult = []; r = _nuova(t, ts, "claude", sid)
            elif r and ts: r["fine"] = ts
            continue
        if d.get("type") != "assistant" or r is None: continue
        if ts: r["fine"] = ts
        u, mid = m.get("usage") or {}, m.get("id")
        if u and mid not in visti:
            visti.add(mid); r["token_lavoro"] += u.get("input_tokens", 0) + u.get("output_tokens", 0) + u.get("cache_creation_input_tokens", 0)
            r["token_in"] += u.get("input_tokens", 0); r["token_out"] += u.get("output_tokens", 0); r["token_scritti"] += u.get("cache_creation_input_tokens", 0)
            r["token_riletti"] += u.get("cache_read_input_tokens", 0); r["ragionamento"] += (u.get("output_tokens_details") or {}).get("thinking_tokens", 0)
        usa = False
        for b in c if isinstance(c, list) else []:
            if not isinstance(b, dict): continue
            if b.get("type") == "text" and b.get("text", "").strip(): r["risposta"] = b["text"]
            if b.get("type") != "tool_use": continue
            usa = True; n = b.get("name", "?"); i = b.get("input") or {}; r["strumenti"][n] = r["strumenti"].get(n, 0) + 1
            tp, cosa = _azione(n, i, d.get("cwd")); _somma(r, d.get("cwd"), n, i)
            if tp == "plancia": _segna(r, cosa); continue
            if n in ("Bash", "bash", "shell"):
                for mk in MARCATORE.finditer(i.get("command") or ""): _segna(r, mk.group(0))    # `cd x; plancia passo D; pytest` -> il resto e del passo D
            if tp == "modifica" and n in ("Bash", "bash", "shell"):
                for w in PO.scritture(i.get("command") or ""):
                    if w not in r["file"]: r["file"].append(w)
            if tp: r["_id"][b.get("id")] = len(r["attivita"]); r["attivita"].append({"tipo": tp, "cosa": cosa, "esito": "in corso", "ts": ts, "bg": bool(i.get("run_in_background")), "passo": r["_passo"], "cmd": str(i.get("command") or "")[:400]})
            if n in ("Task", "Agent"): rami.lancio(b); r["sotto_agenti"] += 1
            if n in SCRIVONO and (i.get("file_path") or i.get("notebook_path")):
                p = (os.path.relpath(i.get("file_path") or i.get("notebook_path"), d.get("cwd") or "/") if os.path.isabs(str(i.get("file_path") or i.get("notebook_path"))) else (i.get("file_path") or i.get("notebook_path"))).replace("\\", "/")
                if p not in r["file"]: r["file"].append(p)
            if n == "Bash" and i.get("command"): r["comandi"].append(lib.redigi(i["command"], 90))
        if not usa and any(isinstance(b, dict) and b.get("type") == "text" and b.get("text", "").strip() for b in (c if isinstance(c, list) else [])):
            rami.testo_finale()
            if not any(a["esito"] == "in corso" for a in r["attivita"]): r["finita"] = True
        elif usa: r["finita"] = False
    if r: out.append(_chiudi(r, rami))
    _cache[k] = out
    return out


def da_copilot(f):
    k = (f, os.path.getmtime(f), os.path.getsize(f))
    if k in _cache: return _cache[k]
    sid = os.path.basename(os.path.dirname(f))[:8]; out, r, rami, subs = [], None, S.Rami(), set()
    for l in open(f, encoding="utf-8", errors="replace"):
        try: d = json.loads(l)
        except Exception: continue
        t, x, ts = str(d.get("type") or ""), d.get("data") or {}, d.get("timestamp")
        if t == "user.message":
            if r and S.copilot_sub(x, subs):                               # prompt di un sotto-agente: resta nella tua richiesta
                r["sotto_agenti"] += 1; r["attivita"].append({"tipo": "sotto-agente", "cosa": lib.redigi(str(x.get("content") or ""), 90), "esito": "ok", "ts": ts, "passo": r["_passo"]}); continue
            if r: out.append(_chiudi(r, rami))
            r = _nuova(str(x.get("content") or ""), ts, "copilot", sid); subs.clear(); continue
        if t in ("subagent.started", "subagent.start"): subs.add(x.get("toolCallId") or x.get("agentId") or len(subs)); continue
        if t in ("subagent.completed", "subagent.failed", "subagent.end"): subs.discard(x.get("toolCallId") or x.get("agentId")); continue
        if r is None: continue
        if ts: r["fine"] = ts
        if t.startswith("assistant.message") and x.get("content"): r["risposta"] = str(x["content"])
        elif t == "tool.execution_start":
            n = x.get("toolName") or "?"; r["strumenti"][n] = r["strumenti"].get(n, 0) + 1; a = x.get("arguments") or x.get("toolArgs") or {}
            if isinstance(a, str):
                try: a = json.loads(a)
                except Exception: a = {"command": a}
            tp, cosa = _azione(n, a, None); _somma(r, None, n, a)
            if tp == "plancia": _segna(r, cosa); continue
            if tp == "sotto-agente": subs.add(x.get("toolCallId"))
            if tp: r["_id"][x.get("toolCallId")] = len(r["attivita"]); r["attivita"].append({"tipo": tp, "cosa": cosa, "esito": "in corso", "ts": ts, "passo": r["_passo"]}); r["finita"] = False
            if any(s in n.lower() for s in ("edit", "create", "write")) and isinstance(a, dict) and (a.get("path") or a.get("file_path")):
                p = a.get("path") or a.get("file_path")
                if p not in r["file"]: r["file"].append(p)
            if n.lower() in ("bash", "shell", "powershell") and isinstance(a, dict) and a.get("command"): r["comandi"].append(lib.redigi(a["command"], 90))
        elif t == "tool.execution_complete":
            subs.discard(x.get("toolCallId"))
            err = x.get("success") is False or bool(x.get("error"))
            if err: r["errori"] += 1
            if x.get("toolCallId") in r["_id"]: r["attivita"][r["_id"][x["toolCallId"]]]["esito"] = "errore" if err else "ok"
        elif t in ("assistant.turn_end", "session.idle"): r["finita"] = not subs      # finisce solo quando i sotto-agenti sono tornati
        elif t == "session.usage_record":
            u = x.get("usage") or {}; r["token_lavoro"] += u.get("inputTokens", 0) + u.get("outputTokens", 0) + u.get("cacheWriteTokens", 0)
            r["token_in"] += u.get("inputTokens", 0); r["token_out"] += u.get("outputTokens", 0); r["token_scritti"] += u.get("cacheWriteTokens", 0)
            r["token_riletti"] += u.get("cacheReadTokens", 0); r["ragionamento"] += u.get("reasoningTokens", 0)
    if r: out.append(_chiudi(r, rami))
    _cache[k] = out
    return out


def _eventi(rad):
    f = os.path.join(str(rad), ".factory", "eventi.jsonl"); out = []
    try:
        with open(f, encoding="utf-8", errors="replace") as h:
            for l in h.readlines()[-3000:]:
                try: out.append(json.loads(l))
                except Exception: pass
    except Exception: pass
    return out


def _utc(ts_locale):
    try: return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.mktime(time.strptime(str(ts_locale)[:19], "%Y-%m-%dT%H:%M:%S"))))
    except Exception: return ts_locale


SENZA_TRASCRIZIONE = ("vscode", "agente")


def da_eventi(eventi):
    """Richieste di agenti senza trascrizione leggibile (chat di VS Code e altri), dagli eventi degli hook."""
    per, out, subp = {}, [], {}
    for e in eventi:
        if e.get("origine") != "hook" or e.get("fonte") not in SENZA_TRASCRIZIONE: continue
        sid = e.get("sessione") or e.get("fonte"); tp = str(e.get("tipo", "")).lower(); ts = _utc(e.get("ts"))
        r = per.get(sid); sub = subp.setdefault(sid, 0)
        if tp in ("hook:userpromptsubmit", "hook:userpromptsubmitted"):
            if r and (sub > 0 or _sembra_subagente(e.get("testo") or "", r)):              # prompt di un sotto-agente: fa parte della richiesta in corso
                r["sotto_agenti"] += 1; r["attivita"].append({"tipo": "sotto-agente", "cosa": lib.redigi(e.get("testo") or "", 90), "esito": "in corso", "ts": ts, "passo": r["_passo"]}); continue
            if r: r["finita"] = True; out.append(_chiudi(r, S.Rami()))
            r = per[sid] = _nuova(e.get("testo") or "(domanda nella chat)", ts, e.get("fonte"), str(sid)[:8]); r["risposta"] = "(la risposta e nella chat dell'agente)"
            continue
        if r is None: continue
        r["fine"] = ts
        if tp in ("hook:posttooluse", "hook:pretooluse") and e.get("cosa"):
            kind, _, cosa = e["cosa"].partition("|"); n = e.get("strumento") or "?"
            if kind == "plancia": _segna(r, cosa); continue
            if kind == "sotto-agente":
                subp[sid] = max(0, subp.get(sid, 0) + (1 if tp == "hook:pretooluse" else -1))
                if tp == "hook:posttooluse":
                    ap = [a for a in r["attivita"] if a["tipo"] == "sotto-agente" and a["esito"] == "in corso"]
                    if ap: ap[0]["esito"] = "ok"
                    continue
            if tp == "hook:pretooluse":
                r["_pend"] = {"tipo": kind, "cosa": cosa, "esito": "in corso", "ts": ts, "passo": r["_passo"]}; continue
            r.pop("_pend", None); r["strumenti"][n] = r["strumenti"].get(n, 0) + 1
            r["attivita"].append({"tipo": kind, "cosa": cosa, "esito": e.get("esito") or "ok", "ts": ts, "passo": r["_passo"], "prova": bool(e.get("prova"))}); r["finita"] = False
            if e.get("esito") == "errore": r["errori"] += 1
            for x in e.get("ambiente") or []:
                if list(x) not in r["ambiente"]: r["ambiente"].append(list(x))
            if kind == "modifica":
                for f in cosa.replace(" (con un comando)", "").split(", "):
                    if f and f not in r["file"]: r["file"].append(f)
            if kind == "comando": r["comandi"].append(cosa)
        elif tp in ("hook:stop", "hook:sessionend", "hook:agentstop"): r["finita"] = True
    ora = time.time()
    for sid, r in per.items():
        if r.get("_pend"): r["attivita"].append(r.pop("_pend"))
        fine = _ts_utc(r["fine"])                                         # VS Code non manda "fine risposta": silenzio di un minuto senza strumenti in corso = finita
        if not r["finita"] and fine and ora - fine > SILENZIO_FINE and not subp.get(sid) and not any(a["esito"] == "in corso" and a["tipo"] != "sotto-agente" for a in r["attivita"][-1:]): r["finita"] = True; r["fine_dedotta"] = True
        out.append(_chiudi(r, S.Rami()))
    return out


SILENZIO_FINE = 60


def _ts_utc(s):
    import calendar
    try: return calendar.timegm(time.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S"))
    except Exception: return None


def _sembra_subagente(testo, r):
    """Dati vecchi senza PreToolUse: un prompt che arriva a pochi secondi da un altro, mentre la richiesta e aperta e c'e un piano a rami, e di un sotto-agente."""
    a, b = _ts_utc(r["fine"]), _ts_utc(r["inizio"])
    return bool(r["piano_scritto"] and not r["finita"] and a and b and a - b < 600 and re.search(r"(?i)\b(branch|ramo|read-only task|subagent|sotto-agente)\b", testo))


def tutte(rad, limite=40):
    trovate, _ = S.trova_sessioni(str(rad)); out = []
    try: out += [(str(r["inizio"] or ""), n, r) for n, r in enumerate(da_eventi(_eventi(rad)))]
    except Exception: pass
    for k, f in trovate:
        try: rr = da_claude(f) if k == "claude" else da_copilot(f)
        except Exception: continue
        out += [(str(r["inizio"] or ""), n, r) for n, r in enumerate(rr)]
    out.sort(key=lambda x: (x[0], x[1]), reverse=True)                 # a parita di orario conta l'ordine nella sessione
    try:
        from fcore import archivio as A
    except ImportError:
        from . import archivio as A
    d0 = A.da()
    if d0: out = [x for x in out if (_ts(x[0]) or 0) >= d0]            # dopo "plancia archivia" il vecchio non si mostra
    return [x[2] for x in out[:limite]]


def riprendere(rich, eventi=None):
    """Riassunto per riprendere il lavoro (tu domani o un collega), solo dai fatti registrati."""
    if not rich: return None
    oggi = [r for r in rich if str(r["inizio"] or "")[:10] == rich[0]["inizio"][:10]] if rich[0]["inizio"] else rich[:5]
    file = []
    for r in oggi:
        for f in r["file"]:
            if f not in file: file.append(f)
    ult = rich[0]
    righe = ["# Riprendere il lavoro", "", "Generato dalla Plancia dalle sessioni degli agenti (nessun LLM). Data: %s" % time.strftime("%Y-%m-%d %H:%M"), "",
             "## Ultima richiesta", "- Domanda: " + ult["domanda"].splitlines()[0][:200] if ult["domanda"] else "- Domanda: -",
             "- Agente: %s, sessione %s" % (ult["fonte"], ult["sessione"]), "- Esito: " + (ult["risposta"].strip().splitlines()[0][:240] if ult["risposta"].strip() else "nessuna risposta registrata"), ""]
    righe += ["## Richieste di oggi (%d)" % len(oggi)] + ["- %s %s" % ((r["inizio"] or "")[11:16], r["domanda"].splitlines()[0][:120] if r["domanda"] else "") for r in oggi[:12]] + [""]
    righe += ["## File modificati oggi"] + (["- `%s`" % f for f in file[:25]] or ["- nessuno"]) + [""]
    neg = [e for e in (eventi or []) if e.get("tipo") == "guardia_negata"]
    if neg: righe += ["## Azioni bloccate dalle guardie"] + ["- %s %s" % (e.get("ts", "")[11:16], (e.get("messaggio") or "").split(". Chiedi")[0]) for e in neg[-5:]] + [""]
    righe += ["## Per ripartire", "- Apri l'agente nella cartella del progetto e incolla: \"Leggi .factory/RIPRENDERE.md e .factory/CONTESTO.md, poi continua da: <cosa vuoi fare>\"."]
    return "\n".join(righe) + "\n"

"""Sessioni degli assistenti (Claude Code e Copilot CLI): consumo, strumenti, hook, e piano ricavato da TaskCreate/TodoWrite.
Sola lettura: ~/.claude/projects/<cartella>/*.jsonl e ~/.copilot/session-state/*/events.jsonl. Nessun hook necessario."""
import glob, json, os, re, time

HOME = os.path.expanduser("~")
STATI = {"da_fare": "DA_FARE", "pending": "DA_FARE", "in_corso": "IN_CORSO", "in_progress": "IN_CORSO", "fatto": "FATTO", "completed": "FATTO",
         "verificato": "VERIFICATO", "problema": "BLOCCATO", "bloccato": "BLOCCATO", "aspetta_utente": "BLOCCATO", "aspetta": "BLOCCATO", "non_necessario": "NON_NECESSARIO"}


def stato(s): return STATI.get(str(s or "").lower(), "da_fare")


def slug(p): return re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(p))


def testo_utente(m):
    c = m.get("content")
    if isinstance(c, list): c = " ".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
    if not isinstance(c, str): return ""
    c = re.sub(r"<system-reminder>.*?</system-reminder>", "", c, flags=re.S).strip()
    return "" if c.startswith("<") else c


AMBIENTE = [(re.compile(r"No module named ['\"]?([\w.]+)"), "manca il modulo Python %s", "pip install %s (nel venv del progetto)"),
            (re.compile(r"could not import ['\"]([\w.]+)['\"]"), "manca il modulo Python %s (test saltati)", "pip install %s (nel venv del progetto)"),
            (re.compile(r"(?:^|\s)([\w.-]+): command not found|command not found: ([\w.-]+)"), "manca il comando %s", "installa %s"),
            (re.compile(r"(?:The term )?'([\w.-]+)' is not recognized as (?:the name of a cmdlet|an internal or external command)"), "manca il comando %s", "installa %s o aggiungilo al PATH"),
            (re.compile(r"JAVA_HOME (?:is not set|environment variable is not defined)"), "JAVA_HOME non impostato (Java mancante)", "installa un JDK e imposta JAVA_HOME"),
            (re.compile(r"externally-managed-environment"), "pip di sistema bloccato (Debian/Ubuntu)", "python3 -m venv .venv && . .venv/bin/activate, poi pip install nel venv"),
            (re.compile(r"(?:Connection refused|could not connect to server|Failed to establish a new connection)"), "un servizio non risponde (connessione rifiutata)", "avvia il servizio o controlla host e porta")]


def problemi_ambiente(testo):
    """Problemi di ambiente nel risultato di un comando: [(cosa, come)] senza doppioni."""
    out = []
    for rx, cosa, come in AMBIENTE:
        for m in rx.finditer(testo or ""):
            g = next((x for x in m.groups() if x), "") if m.groups() else ""
            k = (cosa % g if "%s" in cosa else cosa, come % g.split(".")[0] if "%s" in come else come)
            if k not in out: out.append(k)
    return out


RITORNO = re.compile(r"^(Another Claude session sent a message|<agent-message|\[Subagent hand-back\])")
def ritorno_subagente(t): return bool(t) and bool(RITORNO.search(t.strip()))


def testo_grezzo(m):
    c = m.get("content")
    if isinstance(c, list): c = " ".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
    return c if isinstance(c, str) else ""


class Rami:
    """Sotto-agenti lanciati dall'ultima domanda: ogni lancio e un ramo (IN_CORSO -> FATTO quando consegna), piu un passo finale che li unisce.
    Funziona senza TaskCreate: si legge solo la trascrizione (zero token)."""
    def __init__(s): s.r, s.ult, s.fine = [], [], False
    def prompt(s):
        if s.r: s.ult, s.fine_ult = s.r, s.fine
        s.r, s.fine = [], False
    def lancio(s, b):
        i = b.get("input") or {}
        s.r.append({"id": b.get("id"), "testo": str(i.get("description") or i.get("subagent_type") or "sotto-agente")[:100], "bg": bool(i.get("run_in_background")), "stato": "IN_CORSO"})
    def risultato(s, tid, err):
        for x in s.r:
            if x["id"] == tid and not x["bg"]: x["stato"] = "BLOCCATO" if err else "FATTO"
    def ritorno(s, testo):
        ap = [x for x in s.r if x["stato"] == "IN_CORSO" and x["bg"]]
        if ap: next((x for x in ap if x["testo"].lower() in testo.lower()), ap[0])["stato"] = "FATTO"
    def testo_finale(s):
        if s.r and all(x["stato"] != "IN_CORSO" for x in s.r): s.fine = True
    def in_corso(s): return [x["testo"] for x in s.r if x["stato"] == "IN_CORSO"]
    def passi(s):
        r, fine = (s.r, s.fine) if s.r else (s.ult, getattr(s, "fine_ult", False))
        if not r: return None
        st = [{"id": "R%d" % (n + 1), "testo": x["testo"], "dipende_da": [], "chi": "agente", "stato": x["stato"], "dettaglio": "sotto-agente" + (" in background" if x["bg"] else "")} for n, x in enumerate(r)]
        tutti = all(x["stato"] != "IN_CORSO" for x in r)
        st.append({"id": "FINE", "testo": "Risposta finale: unisce i risultati dei rami", "dipende_da": [x["id"] for x in st], "chi": "agente", "stato": "FATTO" if fine else ("IN_CORSO" if tutti else "DA_FARE")})
        return st


def leggi_sessione(f, prompt=True):
    visti, turni, tools, todos, prompts, modelli, usati, tasks, rami = set(), [], {}, None, [], {}, set(), {}, Rami()
    for l in open(f, encoding="utf-8", errors="replace"):
        try: d = json.loads(l)
        except Exception: continue
        m = d.get("message")
        if not isinstance(m, dict) or d.get("isSidechain"): continue
        if d.get("type") == "user":
            for b in m.get("content") if isinstance(m.get("content"), list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_result": rami.risultato(b.get("tool_use_id"), b.get("is_error"))
            g = testo_grezzo(m)
            if ritorno_subagente(g): rami.ritorno(g); continue
            t = testo_utente(m)
            if t:
                rami.prompt()
                if prompt: prompts.append({"ts": d.get("timestamp"), "testo": t[:140]})
        if d.get("type") != "assistant": continue
        cc = m.get("content") if isinstance(m.get("content"), list) else []
        if any(isinstance(b, dict) and b.get("type") == "text" and b.get("text", "").strip() for b in cc) and not any(isinstance(b, dict) and b.get("type") == "tool_use" for b in cc): rami.testo_finale()
        for b in m.get("content") if isinstance(m.get("content"), list) else []:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                if b.get("id") in usati: continue  # la stessa chiamata compare su piu righe
                usati.add(b.get("id")); tools[b["name"]] = tools.get(b["name"], 0) + 1; i = b.get("input") or {}
                if b["name"] in ("Task", "Agent"): rami.lancio(b)
                if b["name"] == "TaskCreate": tasks[str(len(tasks) + 1)] = {"content": i.get("subject", ""), "status": "pending", "dip": []}
                if b["name"] == "TaskUpdate" and str(i.get("taskId")) in tasks:
                    t = tasks[str(i["taskId"])]; t["status"] = i.get("status") or t["status"]; t["content"] = i.get("subject") or t["content"]
                    t["dip"] = sorted(set(t["dip"]) | {str(x) for x in i.get("addBlockedBy") or []})
                if b["name"] == "TodoWrite": todos = (b.get("input") or {}).get("todos")
        u, mid = m.get("usage"), m.get("id") or d.get("uuid")
        if not u or mid in visti: continue
        visti.add(mid)
        t = {"ts": d.get("timestamp"), "modello": m.get("model", "?"), "effort": d.get("effort") or "", "in": u.get("input_tokens", 0), "out": u.get("output_tokens", 0),
             "cache_r": u.get("cache_read_input_tokens", 0), "cache_w": u.get("cache_creation_input_tokens", 0), "pensiero": (u.get("output_tokens_details") or {}).get("thinking_tokens", 0)}
        turni.append(t); modelli[t["modello"]] = modelli.get(t["modello"], 0) + t["in"] + t["out"] + t["cache_w"]
    return {"id": os.path.basename(f)[:8], "mtime": os.path.getmtime(f), "turni": turni, "strumenti": tools, "todos": todos, "prompts": prompts[-5:], "modelli": modelli, "tasks": tasks, "rami": rami.passi(), "fonte": "claude", "hooks": {}}


def base(p): return re.sub(r"[\\/]+", "/", str(p)).rstrip("/").split("/")[-1].lower()


def cwd_claude(f):
    for l in open(f, encoding="utf-8", errors="replace"):
        try: c = json.loads(l).get("cwd")
        except Exception: continue
        if c: return c


def trova_sessioni(root, cartelle_claude=None, cartelle_copilot=None):
    """Ritorna ([(fonte, percorso)], [dove ho cercato]). Cerca prima per percorso esatto, poi per nome della cartella (utile con cartelle condivise/VM)."""
    out, cercato = [], []
    for cd in cartelle_claude or [os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(HOME, ".claude")]:
        pr = os.path.join(cd, "projects"); cercato.append(pr)
        fs = glob.glob(os.path.join(pr, slug(root), "*.jsonl"))
        if not fs:
            for d in glob.glob(os.path.join(pr, "*")):
                j = sorted(glob.glob(os.path.join(d, "*.jsonl")), key=os.path.getmtime)
                if j and cwd_claude(j[-1]) and base(cwd_claude(j[-1])) == base(root): fs += j
        out += [("claude", f) for f in fs]
    for cd in cartelle_copilot or [os.path.join(HOME, ".copilot")]:
        ss = os.path.join(cd, "session-state"); cercato.append(ss)
        for w in glob.glob(os.path.join(ss, "*", "workspace.yaml")):
            m = re.search(r"^cwd:\s*(.+)$", open(w, errors="replace").read(), re.M)
            ev = os.path.join(os.path.dirname(w), "events.jsonl")
            if m and os.path.isfile(ev) and base(m.group(1).strip("'\" ")) == base(root): out.append(("copilot", ev))
    out.sort(key=lambda x: os.path.getmtime(x[1]), reverse=True)
    return [x for k in ('claude', 'copilot') for x in [y for y in out if y[0] == k][:5]], cercato


def ultima_cartella():
    """Cartella dell'ultima sessione (Claude o Copilot) su questa macchina: serve quando si lancia la plancia da una cartella senza sessioni."""
    c = []
    for f in glob.glob(os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(HOME, ".claude"), "projects", "*", "*.jsonl")): c.append((os.path.getmtime(f), f, "claude"))
    for w in glob.glob(os.path.join(HOME, ".copilot", "session-state", "*", "workspace.yaml")): c.append((os.path.getmtime(w), w, "copilot"))
    for _, f, k in sorted(c, reverse=True)[:30]:
        if k == "claude": p = cwd_claude(f)
        else:
            m = re.search(r"^cwd:\s*(.+)$", open(f, encoding="utf-8", errors="replace").read(), re.M); p = m and m.group(1).strip("'\" ")
        if p and os.path.isdir(p): return p


def leggi_copilot(f, prompt=True):
    turni, tools, prompts, modelli, hooks = [], {}, [], {}, {}
    for l in open(f, encoding="utf-8", errors="replace"):
        try: d = json.loads(l)
        except Exception: continue
        t, x = d.get("type"), d.get("data") or {}
        if t == "session.usage_record":
            u = x.get("usage") or {}
            r = {"ts": d.get("timestamp"), "modello": u.get("model", "?"), "effort": "", "in": u.get("inputTokens", 0), "out": u.get("outputTokens", 0),
                 "cache_r": u.get("cacheReadTokens", 0), "cache_w": u.get("cacheWriteTokens", 0), "pensiero": u.get("reasoningTokens", 0)}
            turni.append(r); modelli[r["modello"]] = modelli.get(r["modello"], 0) + r["in"] + r["out"] + r["cache_w"]
        elif t == "tool.execution_start": tools[x.get("toolName")] = tools.get(x.get("toolName"), 0) + 1
        elif t == "hook.start": hooks[x.get("hookType")] = hooks.get(x.get("hookType"), 0) + 1
        elif t == "user.message" and prompt and x.get("content"): prompts.append({"ts": d.get("timestamp"), "testo": str(x["content"])[:140]})
    return {"id": os.path.basename(os.path.dirname(f))[:8], "fonte": "copilot", "mtime": os.path.getmtime(f), "turni": turni, "strumenti": tools, "todos": None,
            "prompts": prompts[-5:], "modelli": modelli, "tasks": {}, "hooks": hooks}

def piano_da_sessioni(sess):
    """Piano di ripiego se non c'e un piano scritto: TaskCreate/TaskUpdate (Claude Code) o TodoWrite dell'ultima sessione che ne ha uno."""
    for s in sess:
        if s.get("tasks"):
            return {"task": "Attivita della sessione %s" % s["id"], "fonte": "TaskCreate", "steps": [
                {"id": k, "testo": t["content"], "dipende_da": t["dip"], "chi": "agente", "stato": stato(t["status"])} for k, t in s["tasks"].items()]}
        if s.get("rami"):
            return {"task": "Lavoro diviso in rami (sotto-agenti) · sessione %s" % s["id"], "fonte": "sotto-agenti", "steps": s["rami"]}
        if s.get("todos"):
            return {"task": "Attivita della sessione %s" % s["id"], "fonte": "TodoWrite", "steps": [
                {"id": str(i + 1), "testo": t.get("content", ""), "dipende_da": [str(i)] if i else [], "chi": "agente", "stato": stato(t.get("status"))} for i, t in enumerate(s["todos"])]}
    return None


def leggi_tutto(root, prompt=True, cc=None, cp=None):
    """-> (sessioni, dove_ho_cercato). Ogni sessione: id, fonte, turni, strumenti, hook, modelli, prompt."""
    trovate, cercato = trova_sessioni(root, cc, cp)
    return [leggi_copilot(f, prompt) if k == "copilot" else leggi_sessione(f, prompt) for k, f in trovate], cercato


def totali(sess):
    return {k: sum(t[k] for s in sess for t in s["turni"]) for k in ("in", "out", "cache_r", "cache_w", "pensiero")}


SUB_TOOL = ("task", "agent", "runsubagent", "run_subagent", "execution_subagent", "subagent")


def copilot_sub(x, sub_aperti):
    """Copilot CLI: un user.message di un sotto-agente (non tuo). Segni espliciti o un sotto-agente lanciato e non ancora tornato."""
    return bool(x.get("parentToolCallId") or x.get("agentId") or x.get("subagentId") or x.get("source") in ("subagent", "agent") or sub_aperti)

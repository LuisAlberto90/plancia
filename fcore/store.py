"""Archivio del nucleo: tutto vive in <progetto>/.factory/. Solo libreria standard (PyYAML opzionale, solo per leggere piani .yaml).
Root del progetto: variabile FACTORY_ROOT, altrimenti la prima cartella (da quella corrente verso l'alto) che contiene .factory/, altrimenti la cartella corrente."""
import datetime, glob, json, os, re, time, uuid
from pathlib import Path

SEGRETI = [re.compile(r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key)\b(\s*[:=]\s*)\S+"), re.compile(r"(?i)(postgres(?:ql)?|mysql|mariadb|mongodb)://\S+:\S+@\S+")]
PIANI_DEFAULT = [".factory/task/*/piano.json", ".factory/task/*/piano.yaml", ".factory/piani/*.json", ".factory/piani/*.yaml", ".plancia/piano.json", "piano.json", "piano.yaml"]


def radice():
    e = os.environ.get("FACTORY_ROOT")
    if e: return Path(e).resolve()
    p = Path.cwd().resolve()
    for d in [p, *p.parents]:
        if (d / ".factory").is_dir(): return d
    return p


def comando():
    """Come hook, regole e MCP richiamano la plancia: PLANCIA_CMD, altrimenti `plancia` se installata, altrimenti python + factory.py."""
    import shutil, sys
    if os.environ.get("PLANCIA_CMD"): return os.environ["PLANCIA_CMD"]
    me = Path(sys.argv[0]).resolve() if sys.argv and sys.argv[0] else None
    if me and me.is_file() and me.suffix != ".py":                       # lanciata come comando installato (anche con altro nome)
        w = shutil.which(me.name)
        return me.name if w and Path(w).resolve() == me else str(me)     # nome corto solo se nel PATH c'e proprio questa
    w = shutil.which("plancia")
    try:
        if w and "from factory import" in Path(w).read_text(errors="ignore")[:2000]: return "plancia"      # e la nostra, non un omonimo
    except Exception: pass
    fy = Path(__file__).resolve().parent.parent / "factory.py"
    if os.name == "nt":                                                   # Windows aziendale: niente .exe in cartella utente, si passa da py
        return 'py "%s"' % fy if shutil.which("py") else '"%s" "%s"' % (sys.executable, fy)
    return 'python3 "%s"' % fy


def dir_(): return radice() / ".factory"


def config():
    try: return json.loads((dir_() / "config.json").read_text(encoding="utf-8"))
    except Exception: return {}


def modo():
    """leggera = la plancia osserva e protegge, l'agente non spende token per lei; governata = l'agente scrive piano e task (regola + MCP)."""
    c = config(); return c.get("modo") or ("governata" if (radice() / "AGENTS.md").exists() and "plancia:inizio" in (radice() / "AGENTS.md").read_text(encoding="utf-8", errors="ignore") else "leggera")
def stato_dir(): return dir_() / "_stato"
def ora(): return datetime.datetime.now().isoformat(timespec="seconds")


def redigi(s, n=240):
    s = str(s or "")
    for r in SEGRETI: s = r.sub(lambda m: (m.group(1) + (m.group(2) if m.lastindex and m.lastindex >= 2 else "") + "<redatto>") if m.lastindex else "<redatto>", s)
    s = " ".join(s.split()); return s[:n] + ("…" if len(s) > n else "")


def redigi_testo(s, n=1500):
    """Come redigi ma conserva gli a capo (per mostrare domande e risposte leggibili)."""
    s = str(s or "")
    for r in SEGRETI: s = r.sub(lambda m: (m.group(1) + (m.group(2) if m.lastindex and m.lastindex >= 2 else "") + "<redatto>") if m.lastindex else "<redatto>", s)
    s = "\n".join(l.rstrip() for l in s.strip().splitlines()); s = __import__("re").sub(r"\n{3,}", "\n\n", s)
    return s[:n] + ("…" if len(s) > n else "")


# ---- righe append-only (registro, eventi, handoff)
def scrivi_riga(nome, obj):
    d = dir_(); d.mkdir(parents=True, exist_ok=True)
    try:
        if nome == "eventi.jsonl" and (d / nome).stat().st_size > 8_000_000: os.replace(d / nome, d / "eventi-vecchi.jsonl")     # il registro non cresce all'infinito: tengo l'ultimo pezzo
    except OSError: pass
    with open(d / nome, "a", encoding="utf-8") as f: f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def leggi_righe(nome, ultime=None):
    p = dir_() / nome
    if not p.exists(): return []
    out = []
    if ultime:                                                             # serve solo la coda: non rileggo un file che cresce a ogni azione
        try:
            with open(p, "rb") as f:
                f.seek(0, 2); n = f.tell(); k = min(n, ultime * 2500 + 65536); f.seek(n - k); b = f.read()
            tx = b.decode("utf-8", errors="replace")
            if k < n: tx = tx.split("\n", 1)[1] if "\n" in tx else ""
        except Exception: tx = p.read_text(encoding="utf-8", errors="replace")
    else: tx = p.read_text(encoding="utf-8", errors="replace")
    for l in tx.splitlines():
        try: out.append(json.loads(l))
        except Exception: pass
    return out[-ultime:] if ultime else out


# ---- stato (json atomico)
def carica(nome, default=None):
    try: return json.loads((stato_dir() / nome).read_text(encoding="utf-8"))
    except Exception: return default


def salva(nome, obj):
    d = stato_dir(); d.mkdir(parents=True, exist_ok=True); tmp = d / (nome + ".%d.tmp" % os.getpid())
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8"); os.replace(tmp, d / nome)


def task_corrente(): return carica("task_corrente.json")


def evento(tipo, origine="piano", **kw):
    """Evento append-only in .factory/eventi.jsonl (mai bloccante: chi chiama non deve fallire per colpa del registro)."""
    try:
        t = task_corrente() or {}
        e = {"id": "EV-" + time.strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:4], "ts": ora(), "tipo": tipo, "origine": origine, "task_id": t.get("task_id"), **{k: v for k, v in kw.items() if v is not None}}
        scrivi_riga("eventi.jsonl", e); return e
    except Exception: return None


# ---- piani (.json nativo, .yaml se c'e PyYAML)
def normalizza(d):
    """Accetta anche il formato semplice (titolo/passi) e il vecchio .plancia/piano.json."""
    d = d or {}
    if "steps" not in d and "passi" in d: d["steps"] = d.pop("passi")
    d.setdefault("steps", [])
    if "task" not in d and d.get("titolo"): d["task"] = d["titolo"]
    for s in d["steps"]:
        s["id"] = str(s.get("id"))
        s["dipende_da"] = [str(x) for x in s.get("dipende_da") or []]
    return d


def leggi(p):
    p = Path(p); t = p.read_text(encoding="utf-8")
    if p.suffix == ".json": return normalizza(json.loads(t))
    try: import yaml
    except ImportError: raise RuntimeError("il piano %s e in YAML: installa PyYAML (pip install pyyaml) oppure usa un piano .json" % p.name) from None
    return normalizza(yaml.safe_load(t))


def scrivi(p, d):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True); tmp = Path(str(p) + ".%d.tmp" % os.getpid())
    if p.suffix == ".json": tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        import yaml; tmp.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
    os.replace(tmp, p)


def percorsi_piani():
    """Schemi dei piani da cercare: quelli di default + .factory/percorsi.json {"piani": ["lavori/*/piano.yaml"]}."""
    extra = []
    try: extra = json.loads((dir_() / "percorsi.json").read_text(encoding="utf-8")).get("piani", [])
    except Exception: pass
    return PIANI_DEFAULT + list(extra)


def trova_piani():
    r = radice(); out = []
    for pat in percorsi_piani():
        out += [Path(f) for f in glob.glob(str(r / pat)) if os.path.isfile(f)]
    return sorted(set(out), key=lambda f: f.stat().st_mtime, reverse=True)


def piano_attivo():
    p = os.environ.get("FACTORY_PIANO") or (carica("piano_attivo.json", {}) or {}).get("piano")
    return Path(p) if p and Path(p).exists() else None

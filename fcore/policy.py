#!/usr/bin/env python3
"""Guardie: file protetti, comandi vietati, modalita sola lettura. Regole in .factory/policy.json (unite ai default).
  policy mostra                         regole attive
  policy verifica --file PATH           l'agente potrebbe scrivere questo file?   exit 0 = ammesso, 3 = negato
  policy verifica --comando "CMD"       l'agente potrebbe eseguire questo comando?
  policy init [--scrivi]                crea .factory/policy.json con i default (da adattare al progetto)
Gli hook PreToolUse (Claude Code) e preToolUse (Copilot) chiamano la stessa verifica e negano l'azione con il motivo.
Le guardie fermano gli errori dell'agente, non sostituiscono permessi di sistema o credenziali read-only."""
import fnmatch, json, re, sys
from pathlib import Path
try: from . import store as lib
except ImportError: import store as lib

DEFAULT = {
    "sola_lettura": False,
    "protetti": [".env", ".env.*", "**/.env", "**/.env.*", "**/*.pem", "**/*.key", "**/id_rsa*", "**/secrets/**", "**/credentials*", ".factory/policy.json", ".factory/registro.jsonl", ".git/**"],
    "comandi_vietati": [r"\brm\s+-[a-z]*r[a-z]*f?\s+(/|~|\*|\.\s*$)", r"\bgit\s+push\b.*(--force|-f\b)", r"\bgit\s+reset\s+--hard", r"(?i)\bdrop\s+(table|database|schema)\b",
                        r"(?i)\btruncate\s+(table\s+)?\w", r"(?i)\bdelete\s+from\s+\w+\s*(;|$)", r"\bmkfs\b", r"\bdd\s+if=", r"(?i)curl[^|]*\|\s*(ba)?sh"],
    "ammessi_in_sola_lettura": [r"^\s*(plancia|python3?\s+\S*factory\.py)\b", r"^\s*(ls|cat|head|tail|grep|rg|find|git\s+(status|log|diff|show)|pwd|wc)\b"],
}
SCRITTURA = ("write", "edit", "multiedit", "notebookedit", "create", "str_replace", "insert", "apply_patch", "replace", "delete", "move", "rename")
SHELL = ("bash", "shell", "powershell", "run_in_terminal", "terminal", "exec")
CHIAVI_FILE = ("file_path", "path", "filePath", "notebook_path", "target", "destination")


def regole():
    r = json.loads(json.dumps(DEFAULT))
    try:
        u = json.loads((lib.dir_() / "policy.json").read_text(encoding="utf-8"))
        for k, v in u.items():
            if k.endswith("_aggiungi") and isinstance(v, list): r.setdefault(k[:-9], []).extend(v)
            else: r[k] = v
    except FileNotFoundError: pass
    except Exception as e: r["_errore"] = "policy.json illeggibile: %s" % e      # regole default restano attive
    return r


def _rel(f):
    root = lib.radice(); p = Path(f)
    p = (root / p) if not p.is_absolute() else p
    try: return p.resolve().relative_to(root.resolve()).as_posix()
    except ValueError: return None                                         # fuori dal progetto


def _in_analisi():
    try:
        from . import task as T
        cur = (lib.task_corrente() or {}).get("task_id"); t = T.stati_task().get(cur) if cur else None
        return bool(t and t.get("analisi") and t["stato"] not in T.CHIUSE + ("ESEGUITO",))
    except Exception: return False


def verifica_file(f, r=None):
    r = r or regole()
    if r.get("sola_lettura"): return False, "progetto in sola lettura (.factory/policy.json): nessuna modifica ai file"
    rel = _rel(f)
    if rel is not None and not rel.startswith(".factory/") and _in_analisi():
        return False, "task corrente di sola analisi: nessuna modifica ai file. Per modificare apri un task normale (task apri <id>) e chiedi conferma"
    if rel is None: return (True, "") if r.get("scrittura_fuori_progetto", True) else (False, "file fuori dal progetto: %s" % f)
    for pat in r.get("protetti", []):
        if fnmatch.fnmatch(rel, pat) or (pat.startswith("**/") and fnmatch.fnmatch(rel, pat[3:])) or ("/" not in pat and fnmatch.fnmatch(Path(rel).name, pat)):
            return False, "file protetto (%s): %s. Chiedi alla persona di farlo lei o di cambiare .factory/policy.json" % (pat, rel)
    return True, ""


PY_PATH = re.compile(r"""\b\w+\s*=\s*(?:Path\()?['"]([\w./~-]+\.\w{1,6})['"]""")
PY_OPEN = re.compile(r"""open\(\s*['"]([^'"]+)['"]\s*,\s*['"][wax]""")


def scritture(c):
    """File che un comando di shell scrive (euristica: sed -i, > >>, tee, cp/mv destinazione, script Python con open(...,'w') / write_text)."""
    c = c or ""; out = []
    for m in re.finditer(r"(?:^|[\s;&|])(?:>>?|\btee\s+(?:-a\s+)?)\s*([^\s;&|<>]+)", c):
        if not m.group(1).startswith("&") and m.group(1) not in ("/dev/null", "/dev/stderr", "/dev/stdout"): out.append(m.group(1))
    for m in re.finditer(r"\bsed\s+(?:-[a-zA-Z]*i[a-zA-Z.]*\S*|--in-place\S*)\s+(?:-e\s+)?(?:'[^']*'|\"[^\"]*\"|\S+)\s+([^\s;&|]+)", c): out.append(m.group(1))
    for m in re.finditer(r"\b(?:cp|mv|install)\s+(?:-\S+\s+)*\S+\s+([^\s;&|]+)", c): out.append(m.group(1))
    if re.search(r"\bpython3?\b|\bnode\b", c) and re.search(r"open\([^)]*['\"][wax]['\"]|write_text|writeFileSync|\.write\(", c):
        out += PY_OPEN.findall(c)
        if not PY_OPEN.findall(c): out += PY_PATH.findall(c)
    vis = []
    for x in out:
        x = x.strip("'\"")
        if x and x not in vis: vis.append(x)
    return vis


def verifica_comando(c, r=None):
    r = r or regole(); c = c or ""
    for pat in r.get("comandi_vietati", []):
        if re.search(pat, c): return False, "comando vietato dalla policy (%s). Proponilo alla persona invece di eseguirlo" % pat
    if r.get("sola_lettura") and not any(re.search(p, c) for p in r.get("ammessi_in_sola_lettura", [])):
        return False, "progetto in sola lettura: ammessi solo comandi di lettura (.factory/policy.json)"
    for f in scritture(c):                                            # scritture nascoste nei comandi (redirezioni, sed -i, script Python)
        ok, mot = verifica_file(f, r)
        if not ok: return False, mot + " (scrittura fatta con un comando)"
    return True, ""


def e_scrittura(nome, args):
    """La chiamata modifica file del progetto? (strumenti di modifica, o comandi con scritture). Le scritture in .factory/ non contano."""
    n = (nome or "").lower(); args = args or {}
    if isinstance(args, str):
        try: args = json.loads(args)
        except Exception: args = {"command": args}
    if any(s == n or n.endswith(s) for s in SHELL) or ("command" in args and not any(k in args for k in CHIAVI_FILE)):
        fs = scritture(str(args.get("command") or ""))
    elif any(s in n for s in SCRITTURA):
        fs = [args[k] for k in CHIAVI_FILE if isinstance(args.get(k), str)] + [x if isinstance(x, str) else (x or {}).get("path") for x in args.get("files", []) if x] or ["?"]
    else: return False
    return any(not (str(_rel(f) or "")).startswith(".factory/") for f in fs if f)


def piano_mancante():
    """Piano obbligatorio: c'e una domanda della persona dopo l'ultimo piano scritto? (fail open se non si sa)."""
    if (lib.config().get("piano") or "obbligatorio") != "obbligatorio": return False
    ev = lib.leggi_righe("eventi.jsonl", 400); pr = None
    for e in reversed(ev):
        if e.get("tipo") in ("hook:UserPromptSubmit", "hook:userPromptSubmitted"): pr = e.get("ts"); break
    if not pr: return False
    import time as _t
    try: tp = _t.mktime(_t.strptime(pr, "%Y-%m-%dT%H:%M:%S"))
    except Exception: return False
    for f in list((lib.dir_() / "piani").glob("*.json")) + list((lib.dir_() / "task").glob("*/piano.*")):
        try:
            if f.stat().st_mtime >= tp: return False
        except Exception: pass
    return True


MSG_PIANO = ('write the plan of this request before editing files (the user follows it as a graph): tool plancia_piano_nuovo '
             '(or {cmd} piano nuovo "<title>" "A: <verb> <file/module/command> => <check>" "B: ... <- A"), then plancia_passo A / A fatto "<result>". Then retry this edit.')


def msg_piano():
    return MSG_PIANO.format(cmd=lib.comando())


def verifica_strumento(nome, args):
    """Decide su una chiamata di strumento di Claude Code o Copilot. Ritorna (ammesso, motivo)."""
    n = (nome or "").lower(); args = args or {}
    if isinstance(args, str):
        try: args = json.loads(args)
        except Exception: args = {"command": args}
    if any(s == n or n.endswith(s) for s in SHELL) or "command" in args and not any(k in args for k in CHIAVI_FILE):
        return verifica_comando(str(args.get("command") or args.get("cmd") or args.get("script") or ""))
    if any(s in n for s in SCRITTURA):
        files = [args[k] for k in CHIAVI_FILE if isinstance(args.get(k), str)] + [e.get("path") for e in args.get("edits", []) if isinstance(e, dict) and e.get("path")] \
            + [x if isinstance(x, str) else (x or {}).get("path") or (x or {}).get("filePath") for x in args.get("files", []) if x]
        for f in files:
            ok, mot = verifica_file(f)
            if not ok: return False, mot
    return True, ""


def main(a):
    if not a: print(__doc__); return 2
    if a[0] == "mostra": print(json.dumps(regole(), indent=1, ensure_ascii=False)); return 0
    if a[0] == "init":
        p = lib.dir_() / "policy.json"
        if p.exists(): print("esiste gia: %s" % p); return 0
        if "--scrivi" not in a: print("creerei %s (aggiungi --scrivi)" % p); return 0
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"sola_lettura": False, "protetti_aggiungi": [], "comandi_vietati_aggiungi": [], "scrittura_fuori_progetto": True}, indent=1), encoding="utf-8")
        print("scritto %s (i default restano attivi; *_aggiungi estende le liste)" % p); return 0
    if a[0] == "verifica":
        if "--file" in a: ok, mot = verifica_file(a[a.index("--file") + 1])
        elif "--comando" in a: ok, mot = verifica_comando(a[a.index("--comando") + 1])
        else: print("policy verifica --file PATH | --comando \"CMD\""); return 2
        print("AMMESSO" if ok else "NEGATO: " + mot); return 0 if ok else 3
    print(__doc__); return 2


if __name__ == "__main__": sys.exit(main(sys.argv[1:]))


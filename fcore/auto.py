"""Modalita plugin: installi la Plancia una volta (plugin di VS Code, Copilot CLI o Claude Code) e funziona in ogni progetto.
Nessun file del progetto viene toccato: .factory/ si crea da sola al primo uso ed e esclusa da git solo in locale (.git/info/exclude).
La regola del piano non va in AGENTS.md: la riceve l'agente all'inizio della sessione dall'hook (SessionStart)."""
import json, os, subprocess, sys, time
from pathlib import Path

SEGNI = (".git", "pom.xml", "package.json", "pyproject.toml", "build.gradle", "build.gradle.kts", "angular.json", "go.mod", "Cargo.toml", "requirements.txt", "setup.py")
CASA = lambda: Path(os.environ.get("PLANCIA_HOME") or Path.home() / ".plancia")


def radice_progetto(p):
    """Il progetto che contiene la cartella p: la prima cartella con .factory/, altrimenti con .git o un file di build. Mai la home o la radice del disco."""
    p = Path(p).resolve(); home = Path.home().resolve()
    for d in [p, *p.parents]:
        if (d / ".factory").is_dir(): return d, False
    for d in [p, *p.parents]:
        if d == home or d.parent == d: break
        if any((d / s).exists() for s in SEGNI): return d, True
    return None, False


def prepara(rad):
    """Prepara il progetto senza toccare i suoi file: .factory/ con configurazione, guardie e mappa; esclusa da git in locale."""
    fac = rad / ".factory"; fac.mkdir(exist_ok=True)
    (fac / ".gitignore").write_text("*\n", encoding="utf-8")
    if not (fac / "config.json").exists(): (fac / "config.json").write_text(json.dumps({"modo": "leggera", "piano": "obbligatorio", "plugin": True}, indent=1), encoding="utf-8")
    ex = rad / ".git" / "info" / "exclude"
    try:
        if (rad / ".git").is_dir() and ".factory/" not in (ex.read_text(encoding="utf-8") if ex.exists() else ""):
            ex.parent.mkdir(parents=True, exist_ok=True)
            with open(ex, "a", encoding="utf-8") as h: h.write("\n.factory/\n")
    except Exception: pass
    os.environ["FACTORY_ROOT"] = str(rad)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from fcore import policy, panoramica
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        if not (fac / "policy.json").exists(): policy.main(["init", "--scrivi"])
    panoramica.registra(rad)


def mappa_se_manca(rad):
    if (rad / ".factory" / "CONTESTO.md").exists(): return
    from fcore import contesto
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        try: contesto.main(["--scrivi"])
        except Exception: pass


def ha_hook_propri(rad):
    """Il progetto ha gia gli hook della Plancia (installazione classica): il plugin non deve registrare due volte."""
    for f in (rad / ".claude" / "settings.json", rad / ".github" / "hooks" / "plancia.json"):
        try:
            t = f.read_text(encoding="utf-8")
            if " hook" in t and ("factory.py" in t or "plancia" in t): return True
        except Exception: pass
    return False


def regola(cmd):
    return ("[Plancia] For any request that is not a pure question, your FIRST action is the plan, before reading files: "
            "tool plancia_piano_nuovo (or `%s piano nuovo \"<title>\" \"A: <verb> <exact file/module/command> => <check>\" \"B: ... <- A\"`). "
            "Use names and build/test commands from .factory/CONTESTO.md. 3-5 steps for analysis, 6-12 for a change: baseline tests before changing, one step per file, "
            "callers, docs, verification vs baseline, summary. Independent steps get `<-` alone (parallel branches). Mark steps with plancia_passo "
            "(start, then fatto \"<result>\" / errore \"<cause>\" / saltato \"<why>\"). Sub-agents never write plans. Edits are blocked until the plan exists. "
            "Protected files (.env, keys, .git) and dangerous commands are blocked: never work around a block." % cmd)


def pannello_acceso(porta=8780):
    import socket
    s = socket.socket(); s.settimeout(0.3)
    try: s.connect(("127.0.0.1", porta)); return True
    except Exception: return False
    finally: s.close()


def avvia_pannello():
    """La Plancia sempre pronta su http://127.0.0.1:8780, senza aprire finestre."""
    if os.environ.get("PLANCIA_NO_PANNELLO"): return
    if pannello_acceso():
        try:                                                              # c'e una Plancia piu vecchia (prima dell'aggiornamento)? le chiedo il posto
            import urllib.request
            from fcore import mcp as _m
            with urllib.request.urlopen("http://127.0.0.1:8780/api/versione", timeout=1) as r: v = json.loads(r.read().decode()).get("versione") or ""  # noqa: S310  # nosec B310
            vt = lambda s: tuple(int(x) for x in s.split(".") if x.isdigit())
            if not vt(v) or vt(v) >= vt(_m.VERSIONE): return
            try: urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8780/api/lascia?v=" + _m.VERSIONE, headers={"X-Plancia": "1"}), timeout=1).read()  # noqa: S310  # nosec B310
            except Exception: _ferma_vecchio()                             # versioni prima della 0.16.2 non sanno farsi da parte
            for _ in range(15):
                time.sleep(0.2)
                if not pannello_acceso(): break
        except Exception: return
    fy = str(Path(__file__).resolve().parent.parent / "factory.py")
    kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "cwd": str(Path.home())}
    if os.name == "nt": kw["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000      # DETACHED_PROCESS | NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    else: kw["start_new_session"] = True
    try: subprocess.Popen([sys.executable, fy, "pannello", "--no-browser"], **kw)
    except Exception: pass


def _ferma_vecchio():
    """Chiude solo i pannelli Plancia/Lavagna dell'utente (processo python con 'factory.py' e 'pannello' nella riga di comando)."""
    try:
        if os.name == "nt":
            ps = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*factory.py*pannello*' -and $_.ProcessId -ne $PID } "
                  "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True, timeout=15, creationflags=0x08000000)
        else:
            me = os.getpid()
            for d in os.listdir("/proc"):
                if not d.isdigit() or int(d) == me: continue
                try: cmd = open("/proc/%s/cmdline" % d, "rb").read().replace(b"\0", b" ").decode("utf-8", "replace")
                except Exception: continue
                if "factory.py" in cmd and " pannello" in cmd and os.stat("/proc/" + d).st_uid == os.getuid(): os.kill(int(d), 15)
    except Exception: pass


BOOT = '''"""Plancia: avvio stabile degli hook (scritto da Plancia, si rigenera da solo). Trova la cartella della Plancia e passa l'evento."""
import os, sys, glob
from pathlib import Path
h = Path(__file__).resolve().parent
cand = []
try: cand.append((h / "root.txt").read_text(encoding="utf-8").strip())
except Exception: pass
cand += [os.environ.get(k, "") for k in ("PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT", "COPILOT_PLUGIN_ROOT")]
home = str(Path.home())
cand += sorted(glob.glob(os.path.join(home, ".copilot", "installed-plugins", "*", "plancia*")) + glob.glob(os.path.join(home, ".copilot", "installed-plugins", "_direct", "*")))
cand += [os.path.join(home, "plancia"), "C:\\\\Strumenti\\\\plancia"]
for c in cand:
    if c and os.path.isfile(os.path.join(c, "factory.py")) and os.path.isdir(os.path.join(c, "fcore")):
        sys.path.insert(0, c); sys.argv = [os.path.join(c, "factory.py")] + sys.argv[1:]
        from fcore import hook
        sys.exit(hook.main(sys.argv[1:] + ["--plugin"]))
sys.exit(0)
'''


def togli_vecchia_skill():
    """La skill della vecchia Lavagna fa doppione con quella del plugin: la tolgo (solo se e proprio la nostra)."""
    import shutil
    for d in (Path.home() / ".claude" / "skills" / "lavagna-metodo", Path.home() / ".copilot" / "skills" / "lavagna-metodo"):
        try:
            if (d / "SKILL.md").exists() and "# Lavagna method" in (d / "SKILL.md").read_text(encoding="utf-8", errors="ignore"): shutil.rmtree(d, ignore_errors=True)
        except Exception: pass


def scrivi_boot():
    """~/.plancia/hook.py e root.txt: gli hook di Copilot CLI e VS Code chiamano questo file fisso, che sa dove sta la Plancia (anche dopo un aggiornamento)."""
    try:
        c = CASA(); c.mkdir(parents=True, exist_ok=True); root = str(Path(__file__).resolve().parent.parent)
        if not (c / "root.txt").exists() or (c / "root.txt").read_text(encoding="utf-8").strip() != root: (c / "root.txt").write_text(root, encoding="utf-8")
        if not (c / "hook.py").exists() or (c / "hook.py").read_text(encoding="utf-8") != BOOT: (c / "hook.py").write_text(BOOT, encoding="utf-8")
    except Exception: pass

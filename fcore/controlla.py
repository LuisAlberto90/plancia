"""plancia controlla  — controlla l'installazione e dice in italiano cosa manca e come sistemarlo."""
import json, os, socket, sys
from pathlib import Path


def _ok(v, testo, come=""): return (bool(v), testo, come)


def controlli():
    h = Path.home(); qui = Path(__file__).resolve().parent.parent; out = []
    out.append(_ok(sys.version_info >= (3, 9), "Python %d.%d (%s)" % (sys.version_info[0], sys.version_info[1], sys.executable), "serve Python 3.9 o piu recente"))
    try: v = json.loads((qui / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")).get("version")
    except Exception: v = None
    out.append(_ok(True, "Plancia %s in %s" % (v or "?", qui)))
    copie = [str(p.parent.parent) for b in (h / ".copilot" / "installed-plugins", h / ".vscode" / "agent-plugins", h / ".claude" / "plugins")
             if b.is_dir() for p in b.rglob("auto.py") if p.parent.name == "fcore" and (p.parent.parent / "factory.py").exists()]
    out.append(_ok(len(copie) <= 1, "copie del plugin trovate: %d" % len(copie) + ("" if len(copie) <= 1 else " (" + "; ".join(copie[:3]) + ")"),
                   "piu copie possono essere versioni diverse: aggiornale tutte (git pull) o tieni solo quella che usi"))
    boot = h / ".plancia" / "hook.py"
    out.append(_ok(boot.exists(), "gli hook sono gia partiti almeno una volta" if boot.exists() else "gli hook non sono ancora mai partiti",
                   "VS Code: Ctrl+Shift+P > Developer: Reload Window, poi una CHAT NUOVA dentro la cartella di un progetto; se ancora niente: View > Output > 'GitHub Copilot Chat Hooks'"))
    s = socket.socket(); s.settimeout(0.5)
    try: s.connect(("127.0.0.1", 8780)); su = True
    except Exception: su = False
    finally: s.close()
    out.append(_ok(su, "pannello acceso su http://127.0.0.1:8780" if su else "pannello spento", '%s "%s" pannello --sfondo' % ("py" if os.name == "nt" else "python3", qui / "factory.py")))
    try: pr = json.loads((h / ".plancia" / "progetti.json").read_text(encoding="utf-8"))
    except Exception: pr = []
    out.append(_ok(bool(pr), "progetti conosciuti: %d" % len(pr) + (" (" + ", ".join(Path(p).name for p in pr[:5]) + ")" if pr else ""),
                   "apri in VS Code la cartella di un progetto (con .git o pom.xml/package.json/pyproject.toml) e fai una domanda all'agente"))
    return out


def main(a):
    tutto_ok = True
    for ok, testo, come in controlli():
        print(("OK   " if ok else "NO   ") + testo)
        if not ok and come: print("     -> " + come)
        tutto_ok &= ok
    print("\nTutto a posto." if tutto_ok else "\nSistema le righe NO dall'alto: spesso la prima risolve anche le altre.")
    return 0 if tutto_ok else 1

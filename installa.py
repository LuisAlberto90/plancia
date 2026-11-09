#!/usr/bin/env python3
"""Prepara la Plancia in un progetto con un doppio clic (Installa-in-un-progetto.cmd / .sh) o trascinandoci sopra la cartella.
Non installa niente: usa questa cartella della Plancia con `py`/`python3`. Passi: init --scrivi, mappa del progetto, skill per tutti i progetti, poi apre il pannello.
  py installa.py [CARTELLA_PROGETTO] [--no-pannello]"""
import os, subprocess, sys
from pathlib import Path

QUI = Path(__file__).resolve().parent
FY = QUI / "factory.py"


def scegli_cartella():
    if os.environ.get("PLANCIA_NON_INTERATTIVO"): return None
    try:
        import tkinter as tk
        from tkinter import filedialog
        r = tk.Tk(); r.withdraw(); r.attributes("-topmost", True)
        d = filedialog.askdirectory(title="Plancia: scegli la cartella del progetto (quella che apri in VS Code)")
        r.destroy(); return d or None
    except Exception:
        try: return input("Cartella del progetto (quella che apri in VS Code): ").strip().strip('"') or None
        except EOFError: return None


def lancia(args, cwd):
    print("\n> plancia " + " ".join(args)); sys.stdout.flush()
    return subprocess.call([sys.executable, str(FY)] + args, cwd=cwd, env=dict(os.environ, FACTORY_ROOT=str(cwd)))


def main(a):
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass
    pos = [x for x in a if not x.startswith("--")]
    d = Path(pos[0]).expanduser() if pos else (lambda x: Path(x) if x else None)(scegli_cartella())
    if not d or not d.is_dir(): print("Nessuna cartella valida scelta: niente da fare."); return 2
    d = d.resolve()
    if d == QUI or QUI in d.parents: print("Hai scelto la cartella della Plancia stessa: scegli quella del progetto."); return 2
    if "--archivia" in a:
        rc = lancia(["archivia"], d); print("\nFatto: il pannello mostra solo il lavoro da adesso. Il vecchio e in .factory\\archivio."); return rc
    if "--diagnosi" in a:
        rc = lancia(["diagnosi"], d)
        if os.name == "nt" and not os.environ.get("PLANCIA_NON_INTERATTIVO"): os.startfile(str(d / ".factory"))  # noqa: S606 - apre la cartella con lo zip
        print("\nManda lo zip diagnosi-....zip che trovi in %s" % (d / ".factory")); return rc
    print("Plancia -> progetto: %s" % d)
    (d / ".factory").mkdir(exist_ok=True)
    rc = lancia(["init", "--scrivi"], d) or lancia(["contesto", "--scrivi"], d) or lancia(["metodo", "--globale", "--scrivi"], d)
    if rc: print("\nQualcosa non e andato: copia le righe sopra e mandale a chi ti supporta."); return rc
    print("\nFatto. In VS Code: 1) attiva gli hook della chat (Impostazioni, cerca 'hooks'); 2) apri .vscode/mcp.json e premi Start su 'plancia'; 3) apri una chat nuova in modalita Agent.")
    if "--no-pannello" in a or os.environ.get("PLANCIA_NON_INTERATTIVO"): return 0
    print("\nApro il pannello (chiudi questa finestra per fermarlo)...")
    return lancia(["pannello"], d)


if __name__ == "__main__":
    rc = main(sys.argv[1:])
    if os.name == "nt" and not os.environ.get("PLANCIA_NON_INTERATTIVO"):
        try: input("\nPremi Invio per chiudere...")
        except EOFError: pass
    sys.exit(rc)

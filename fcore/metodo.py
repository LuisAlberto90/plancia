"""Skill `plancia-metodo`: come affrontare ogni richiesta con il percorso piu corto e corretto (niente fronzoli, niente loop).
  plancia metodo                  mostra dove la installerebbe
  plancia metodo --scrivi         nel progetto: .claude/skills/plancia-metodo/ (letta da Claude Code e da Copilot CLI / VS Code)
  plancia metodo --globale --scrivi   per tutti i progetti: ~/.claude/skills/ (la leggono sia Claude Code sia Copilot: una copia sola)
  plancia metodo --mostra         stampa la skill
La skill pesa poco: l'agente vede solo la descrizione finche non serve."""
import sys
from pathlib import Path
try: from . import store as lib
except ImportError: import store as lib

SKILL = Path(__file__).resolve().parent.parent / "skills" / "plancia-metodo" / "SKILL.md"


def destinazioni(globale, agenti=("claude", "copilot")):
    if globale:                                                         # ~/.claude/skills lo leggono Claude Code e Copilot: con "tutti e due" una copia sola, altrimenti VS Code la vede doppia
        sc = ["claude"] if len(agenti) > 1 else [a for a in ("claude", "copilot") if a in agenti]
        return [Path.home() / ("." + a) / "skills" / "plancia-metodo" for a in sc]
    return [lib.radice() / ".claude" / "skills" / "plancia-metodo"]


def installa(globale=False, scrivi=False, out=None, agenti=("claude", "copilot")):
    out = out if out is not None else []; t = SKILL.read_text(encoding="utf-8")
    for d in destinazioni(globale, agenti):
        f = d / "SKILL.md"; uguale = f.exists() and f.read_text(encoding="utf-8") == t
        out.append(("skill plancia-metodo gia aggiornata in %s" if uguale else ("scritta" if scrivi else "scriverei") + " la skill plancia-metodo in %s") % d)
        if scrivi and not uguale: d.mkdir(parents=True, exist_ok=True); f.write_text(t, encoding="utf-8")
        v = d.parent / ("lava" + "gna-metodo")                                # la skill della vecchia Lavagna: doppione da togliere
        if v.is_dir() and (v / "SKILL.md").exists() and "# Lavagna method" in (v / "SKILL.md").read_text(encoding="utf-8", errors="ignore"):
            out.append(("tolta" if scrivi else "toglierei") + " la vecchia skill %s" % v.name)
            if scrivi: import shutil; shutil.rmtree(v, ignore_errors=True)
    return out


def main(a):
    if a[:1] in (["-h"], ["--help"]): print(__doc__); return 0
    if "--mostra" in a: print(SKILL.read_text(encoding="utf-8")); return 0
    out = installa("--globale" in a, "--scrivi" in a)
    if "--scrivi" not in a: out.append("(prova a vuoto: aggiungi --scrivi)")
    print("\n".join(out)); return 0


if __name__ == "__main__": sys.exit(main(sys.argv[1:]))

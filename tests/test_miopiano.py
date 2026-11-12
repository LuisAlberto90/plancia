"""Il mio piano: impostazioni di Copilot validate, limiti di Claude dalla statusline, installazione prudente (a vuoto di default, senza perdere la statusline di prima), esportazione senza testi."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
Q = Path(__file__).resolve().parent.parent
ok = ko = 0
def check(c, m):
    global ok, ko
    if c: ok += 1
    else: ko += 1; print("KO", m)
home = Path(tempfile.mkdtemp()); os.environ["PLANCIA_HOME"] = str(home / ".plancia"); os.environ["HOME"] = os.environ["USERPROFILE"] = str(home)
sys.path.insert(0, str(Q))
from fcore import miopiano as M, consumi as C

d = M.impostazioni(); check(d["copilot"]["piano"] == "" and not d["claude"]["auto"], "piano: vuoto di default")
check(M.salva({"copilot": {"piano": "business", "usati": 267.9}})["ok"] and M.impostazioni()["copilot"]["tetto"] == 1900 and M.impostazioni()["copilot"]["usati"] == 267.9, "piano: Business ha il suo tetto e si rilegge")
check(M.salva({"copilot": {"piano": "custom", "tetto": 5000}})["ok"] and M.impostazioni()["copilot"]["tetto"] == 5000, "piano: Personalizzato usa il tetto scritto")
check(M.impostazioni()["copilot"]["prezzi"]["aggiornato_al"] and "ciclo" in M.impostazioni()["copilot"], "piano: data dei prezzi e ciclo UTC nel pannello")
for brutto in ({"copilot": {"piano": "x"}}, {"copilot": {"tetto": -1}}, {"copilot": {"usati": "abc"}}, "no"):
    try: M.salva(brutto); check(False, "piano: rifiuta %s" % brutto)
    except ValueError: check(True, "piano: rifiuta valori fuori misura")
sl = home / "sl.py"; sl.write_text(M.STATUSLINE, encoding="utf-8")
r = subprocess.run([sys.executable, str(sl)], input=json.dumps({"rate_limits": {"five_hour": {"used_percentage": 6, "resets_at": 5}, "seven_day": {"used_percentage": 19.5, "resets_at": 9}}}), capture_output=True, text=True, env=os.environ)
check(r.returncode == 0 and "5h 6%" in r.stdout and M.impostazioni()["claude"]["sette_giorni"]["pct"] == 19.5, "statusline: salva i limiti e stampa una riga")
r = subprocess.run([sys.executable, str(sl)], input="non json", capture_output=True, text=True, env=os.environ); check(r.returncode == 0, "statusline: mai bloccante con input strano")
sp = home / ".claude" / "settings.json"; sp.parent.mkdir(parents=True); sp.write_text(json.dumps({"statusLine": {"type": "command", "command": "echo mia"}, "x": 1}), encoding="utf-8")
o = []; M.installa(False, o); check(json.loads(sp.read_text())["statusLine"]["command"] == "echo mia", "installa: a vuoto non scrive nulla")
o = []; M.installa(True, o); c = json.loads(sp.read_text()); check("statusline.py" in c["statusLine"]["command"] and c["x"] == 1 and (home / ".plancia" / "statusline_next.txt").read_text() == "echo mia" and M.statusline_installata(), "installa: imposta la statusline e conserva la precedente")
r = subprocess.run([sys.executable, str(home / ".plancia" / "statusline.py")], input=json.dumps({"rate_limits": {}}), capture_output=True, text=True, env=os.environ); check("mia" in r.stdout, "statusline: richiama quella di prima")
o = []; M.installa(True, o, rimuovi=True); check(json.loads(sp.read_text())["statusLine"]["command"] == "echo mia", "rimuovi: ripristina la statusline di prima")
f = home / "e.json"; C.righe = lambda radici, giorni=90: {"righe": [{"d": "segreto", "ti": "titolo segreto"}], "progetti": [{"nome": "Cliente-X", "radice": "/x"}]}
import fcore.panoramica as PN; PN.progetti = lambda: []
C.esporta([str(f)]); t = f.read_text(encoding="utf-8"); check("segreto" not in t and "Cliente-X" not in t, "consumi-esporta: nessun testo e nessun nome di progetto")
print("%d ok, %d KO" % (ok, ko)); sys.exit(1 if ko else 0)

"""Modello per richiesta, skill usate, aggregazione per modello, proposte «impara dai prompt» (skill da migliorare / ampliare / creare)."""
import sys, tempfile
from pathlib import Path
Q = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Q))
ok = ko = 0
def check(c, m):
    global ok, ko
    if c: ok += 1
    else: ko += 1; print("KO", m)
from fcore import richieste as R, consumi as C, pattern as P

r = R._nuova("x", "t", "claude", "s")
R._mod(r, "claude-sonnet-4-5-20250929", 100, 5000, 40); R._mod(r, "claude-opus-4-1", 10, 0, 5); R._mod(r, "", 1, 0, 1)
check(r["modelli"]["claude-sonnet-4-5-20250929"] == [100, 5000, 40] and "?" in r["modelli"], "modello: i token vanno al modello che li ha prodotti")
R._skill(r, "Skill", {"skill": "plugin:plancia-metodo"}); R._skill(r, "Read", {"file_path": "C:\\p\\.claude\\skills\\foo\\SKILL.md"})
check(r["skills"] == ["plancia-metodo", "foo"], "skill usata: dallo strumento Skill e dalla lettura di SKILL.md")
check(C.nome_modello("claude-sonnet-4-5-20250929") == "claude-sonnet-4-5" and C.nome_modello("") == "non dichiarato" and C.nome_modello("copilot/gpt-5") == "gpt-5", "nome modello leggibile")

d = Path(tempfile.mkdtemp()); (d / ".factory").mkdir()
rich = [dict(R._nuova("Run the integration tests for the orders module and report failures %d" % i, "2026-11-0%dT10:00:00" % (i + 1), "claude", "s%d" % i), modelli={"claude-sonnet-4-5": [1000, 0, 100]}) for i in range(4)]
R.tutte = lambda rad, n=0: rich
sk = d / ".claude" / "skills" / "integration-tests"; sk.mkdir(parents=True)
(sk / "SKILL.md").write_text("---\nname: integration-tests\ndescription: Run integration tests orders module report failures\n---\nSteps.\n", encoding="utf-8")
P._C.clear(); cand, _ = P.analizza(d)
c = [x for x in cand if x["id"].startswith("cand-ricorrente")]
check(c and "va migliorata" in c[0]["titolo"] and "integration-tests" in c[0]["azione"]["testo"] if c and c[0].get("azione") else bool(c and "integration-tests" in c[0]["prompt"] and "va migliorata" in c[0]["titolo"]), "skill che copre ma richiesta ripetuta: proposta di migliorarla")
(sk / "SKILL.md").unlink(); sk.rmdir(); P._C.clear(); cand, _ = P.analizza(d)
c = [x for x in cand if x["id"].startswith("cand-ricorrente")]
check(c and "va migliorata" not in c[0]["titolo"] and "Create a project skill" in c[0]["prompt"], "nessuna skill vicina: proposta di crearne una")
C._C.clear(); d2 = C.consumi([d], 0); m = d2["totali"]["modelli"]
check(len(m) == 1 and m[0]["modello"] == "claude-sonnet-4-5" and m[0]["richieste"] == 4 and m[0]["lavoro"] == 4000 and d2["progetti"][0]["top"] == [] or d2["progetti"][0]["modelli"][0]["richieste"] == 4, "consumi: totale per modello")
print("%d ok, %d KO" % (ok, ko)); sys.exit(1 if ko else 0)

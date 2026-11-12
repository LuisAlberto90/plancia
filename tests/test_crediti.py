"""Crediti AI di Copilot: calcolo per modello, tier long context per chiamata, modello senza prezzo, reset mensile a mezzanotte UTC."""
import sys, calendar
from pathlib import Path
Q = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Q))
ok = ko = 0
def check(c, m):
    global ok, ko
    if c: ok += 1
    else: ko += 1; print("KO", m)
from fcore import crediti as K, richieste as R

near = lambda a, b: abs(a - b) < 1e-9
r = K.calcola("GPT-6 Luna", 100_000, 0, 0, 0); check(near(r["crediti"], 1.0), "crediti: 100K input GPT-6 Luna a 0,10 $/1M = 1 credito")
r = K.calcola("GPT-6 Luna", 300_000, 0, 0, 0); check(r["lungo"] and near(r["crediti"], 300_000 * 0.20 / 1e6 / 0.01), "tier: GPT-6 Luna oltre 272K usa 0,20 $/1M")
r = K.calcola("gpt-6-luna", 1000, 5000, 0, 200); check(near(r["crediti"], 0.025) and r["parti"][1] == 0.005, "crediti: input + cache letta + output, nome del log normalizzato")
r = K.calcola("claude-haiku-5.5", 90_000, 0, 0, 0); check(near(r["crediti"], 0.9) and not r["lungo"], "crediti: Claude Haiku 5.5 sotto 100K = tier base")
r = K.calcola("claude-haiku-5.5", 100_000, 0, 0, 0); check(not r["lungo"], "tier: esattamente 100K resta base (soglia: sopra)")
r = K.calcola("claude-haiku-5.5", 100_001, 0, 0, 0); check(r["lungo"] and near(r["crediti"], 100_001 * 0.50 / 1e6 / 0.01), "tier: oltre 100K scatta long context (0,50 $/1M)")
r = K.calcola("claude-haiku-5.5", 60_000, 30_000, 20_000, 0); check(r["lungo"], "tier: la soglia conta input + cache letta + cache scritta della chiamata")
r = K.calcola("GPT-6.1 Sol", 0, 200_000, 0, 0); check(near(r["crediti"], 2.0), "crediti: cache letta di GPT-6.1 Sol a 0,10 $/1M")
r = K.calcola("Claude Sonnet 5.5", 0, 0, 1_000_000, 0); check(near(r["crediti"], 250.0), "crediti: cache scritta Claude Sonnet 5.5 a 2,50 $/1M")
r = K.calcola("GPT-5.4 nano", 0, 0, 1_000_000, 0); check(near(r["crediti"], 0.0), "crediti: modello senza prezzo di cache write = 0")
r = K.calcola("modello-inventato", 1000, 0, 0, 10); check(r.get("mancante") == "modello-inventato" and "crediti" not in r, "modello sconosciuto: prezzo mancante, nessun numero inventato")
acc = K.nuovo(); K.aggiungi(acc, "gpt-6-luna", 1000, 0, 0, 0); K.aggiungi(acc, "boh", 5000, 0, 0, 0); K.aggiungi(acc, "claude-haiku-5.5", 200_000, 0, 0, 0)
check(acc["lunghe"] == 1 and "boh" in acc["mancanti"] and acc["mancanti"]["boh"] == 5000 and acc["c"] > 0, "accumulo: tier per chiamata, mancanti a parte")
check(all(m["nome"] for m in K.tabella()["m"].values()) and len({m["nome"] for m in K.tabella()["m"].values()}) >= 28, "tabella: tutti i modelli della pagina GitHub")
mt = K.meta(); check(mt["aggiornato_al"] and mt["fonte"].startswith("https://docs.github.com") and mt["giorni"] is not None, "tabella: fonte e data")
t = lambda *a: calendar.timegm(a)
check(K.ciclo_utc(t(2026, 11, 12, 10, 0, 0)) == (t(2026, 11, 1, 0, 0, 0), t(2026, 12, 1, 0, 0, 0)), "ciclo: novembre")
check(K.ciclo_utc(t(2026, 11, 30, 23, 59, 59))[1] == t(2026, 12, 1, 0, 0, 0) and K.ciclo_utc(t(2026, 12, 1, 0, 0, 0))[0] == t(2026, 12, 1, 0, 0, 0), "ciclo: a mezzanotte UTC del 1° inizia il mese nuovo")
check(K.ciclo_utc(t(2026, 12, 31, 23, 0, 0))[1] == t(2027, 1, 1, 0, 0, 0), "ciclo: dicembre passa all'anno dopo")
q = R._nuova("x", "t", "copilot", "s"); q["crediti"] = K.nuovo(); K.aggiungi(q["crediti"], "gpt-6-luna", 1000, 5000, 0, 200)
from fcore import consumi as C
c = C._cr_campi(dict(q, fonte="copilot")); check(c["cr"] == 0.025 and c["cd"][0] == [1000, 5000, 0, 200] and C._cr_campi(dict(q, fonte="claude")) == {}, "righe: Copilot ha crediti e dettaglio, Claude no")
print("%d ok, %d KO" % (ok, ko)); sys.exit(1 if ko else 0)

"""Crediti AI di GitHub Copilot, calcolati dai token e dai prezzi per modello (fcore/prezzi_copilot.json, da GitHub Docs "Models and pricing").
1 credito = 0,01 dollari. Crediti = somma di token x prezzo per 1M (input, cache letta, cache scritta, output) / 1M / 0,01. Scelta del tier long context PER CHIAMATA.
Modello senza prezzo in tabella -> `mancante`: mai indovinare. E una STIMA: l'unica fonte vera dell'uso e github.com/settings/billing (Copilot Business: la pagina del tuo account/organizzazione)."""
import json, re, time
from pathlib import Path

PERCORSO = Path(__file__).resolve().parent / "prezzi_copilot.json"
_T = {}


def _chiave(n):
    n = re.sub(r"-20\d{6}$", "", str(n or "").strip().lower())
    n = re.sub(r"^(copilot|github)[/:]", "", n)
    return re.sub(r"[^a-z0-9]", "", n)


def tabella():
    """Tabella dei prezzi: {chiave normalizzata: modello}. Letta una volta."""
    if not _T:
        try: d = json.loads(PERCORSO.read_text(encoding="utf-8"))
        except Exception: d = {"modelli": []}
        _T["meta"] = {k: v for k, v in d.items() if k != "modelli"}; _T["m"] = {}
        for m in d.get("modelli", []):
            _T["m"][_chiave(m["nome"])] = m
            for a in m.get("alias") or []: _T["m"][_chiave(a)] = m
    return _T


def meta():
    """Fonte, data di verifica, età in giorni (per l'avviso oltre 60 giorni)."""
    m = dict(tabella()["meta"])
    try: m["giorni"] = int((time.time() - time.mktime(time.strptime(m["aggiornato_al"], "%Y-%m-%d"))) // 86400)
    except Exception: m["giorni"] = None
    m["vecchia"] = m["giorni"] is None or m["giorni"] > 60
    return m


def prezzo(modello, prompt_totale):
    """Prezzi (input, cached, cache_write, output) per 1M di token per questo modello e questa chiamata; None se non in tabella. Secondo elemento: True se scatta il long context."""
    m = tabella()["m"].get(_chiave(modello))
    if not m: return None, False
    lc = m.get("long_context")
    if lc and prompt_totale > m.get("soglia", 1 << 62): r, lungo = lc, True
    else: r, lungo = m, False
    return tuple(float(r.get(k) or 0) for k in ("input", "cached", "cache_write", "output")), lungo


def calcola(modello, inp, cached, cache_write, out):
    """Una chiamata: {crediti, token:[i,c,w,o], parti:[crediti per voce], lungo} oppure {mancante: modello}."""
    t = [int(inp or 0), int(cached or 0), int(cache_write or 0), int(out or 0)]
    p, lungo = prezzo(modello, t[0] + t[1] + t[2])
    if p is None: return {"mancante": str(modello or "") or "?", "token": t}
    parti = [t[i] * p[i] / 1e6 / tabella()["meta"].get("dollari_per_credito", 0.01) for i in range(4)]
    return {"crediti": sum(parti), "token": t, "parti": parti, "lungo": lungo}


def nuovo():
    return {"c": 0.0, "t": [0, 0, 0, 0], "k": [0.0, 0.0, 0.0, 0.0], "mancanti": {}, "lunghe": 0, "approx": 0}


def aggiungi(acc, modello, inp, cached, cache_write, out, approx=False):
    """Somma una chiamata a `acc` (vedi nuovo()). Chiamata senza prezzo: non conta crediti, i suoi token vanno in `mancanti`."""
    r = calcola(modello, inp, cached, cache_write, out)
    if "mancante" in r:
        acc["mancanti"][r["mancante"]] = acc["mancanti"].get(r["mancante"], 0) + sum(r["token"]); return
    acc["c"] += r["crediti"]; acc["lunghe"] += 1 if r["lungo"] else 0
    for i in range(4): acc["t"][i] += r["token"][i]; acc["k"][i] += r["parti"][i]
    if approx: acc["approx"] = 1


def ciclo_utc(ora):
    """(inizio, fine) del mese di Copilot che contiene `ora` (epoch): reset il 1 del mese alle 00:00 UTC."""
    t = time.gmtime(ora); y, m = t.tm_year, t.tm_mon
    import calendar
    ini = calendar.timegm((y, m, 1, 0, 0, 0)); y2, m2 = (y + 1, 1) if m == 12 else (y, m + 1)
    return ini, calendar.timegm((y2, m2, 1, 0, 0, 0))

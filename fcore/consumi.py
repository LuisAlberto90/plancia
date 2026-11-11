"""Consumi per progetto: quanti token hanno usato gli agenti, progetto per progetto, giorno per giorno e richiesta per richiesta.
Solo lettura delle trascrizioni gia presenti sul PC (Claude Code, Copilot CLI): zero token, nessuna rete.
Limite onesto: la chat di VS Code non fornisce i token alla Plancia, quindi quelle richieste si contano ma non si misurano."""
import os, time
from pathlib import Path
try: from . import richieste as RQ
except ImportError: import richieste as RQ

_C = {}
TOP = 5


def _taglio(giorni):
    """Data (AAAA-MM-GG, ora locale) da cui contare: 0 = tutto, 1 = solo oggi, N = ultimi N giorni compreso oggi."""
    if not giorni: return ""
    return time.strftime("%Y-%m-%d", time.localtime(time.time() - (giorni - 1) * 86400))


def _progetto(rad, da):
    rich = RQ.tutte(rad, 5000)
    p = {"radice": str(rad), "nome": Path(rad).name, "richieste": 0, "misurate": 0, "non_misurabili": 0, "lavoro": 0, "riletti": 0, "ragionamento": 0,
         "fonti": {}, "giorni": {}, "top": [], "ultimo": ""}
    for r in rich:
        g = str(r.get("inizio") or "")[:10]
        if da and g < da: continue
        lav = int(r.get("token_lavoro") or 0); ril = int(r.get("token_riletti") or 0); rag = int(r.get("ragionamento") or 0)
        mis = (lav + ril) > 0; f = r.get("fonte") or "?"
        p["richieste"] += 1; p["misurate" if mis else "non_misurabili"] += 1
        p["lavoro"] += lav; p["riletti"] += ril; p["ragionamento"] += rag
        ff = p["fonti"].setdefault(f, {"richieste": 0, "misurate": 0, "lavoro": 0, "riletti": 0}); ff["richieste"] += 1; ff["misurate"] += 1 if mis else 0; ff["lavoro"] += lav; ff["riletti"] += ril
        gg = p["giorni"].setdefault(g, {"giorno": g, "richieste": 0, "lavoro": 0}); gg["richieste"] += 1; gg["lavoro"] += lav
        if mis: p["top"].append({"domanda": (r.get("domanda") or "").strip().split("\n")[0][:110], "lavoro": lav, "riletti": ril, "inizio": str(r.get("inizio") or "")[:16].replace("T", " "), "fonte": f})
        if g and g > p["ultimo"]: p["ultimo"] = g
    p["top"] = sorted(p["top"], key=lambda x: -x["lavoro"])[:TOP]
    p["giorni"] = sorted(p["giorni"].values(), key=lambda x: x["giorno"])
    return p


def consumi(radici, giorni=7):
    """-> {periodo, da, progetti:[...ordinati per token di lavoro], totali}. Un progetto che non si legge viene saltato, mai un errore."""
    chiave = (tuple(sorted(str(r) for r in radici)), giorni); ora = time.time()
    if chiave in _C and ora - _C[chiave][0] < 60: return _C[chiave][1]
    da = _taglio(giorni); out = []; vecchio = os.environ.get("FACTORY_ROOT")
    try:
        for r in radici:
            os.environ["FACTORY_ROOT"] = str(r)
            try: out.append(_progetto(r, da))
            except Exception: continue
    finally:
        if vecchio is None: os.environ.pop("FACTORY_ROOT", None)
        else: os.environ["FACTORY_ROOT"] = vecchio
    out.sort(key=lambda p: (-p["lavoro"], -p["richieste"], p["nome"].lower()))
    for p in out: p["fonti"] = [dict(fonte=k, **v) for k, v in sorted(p["fonti"].items(), key=lambda kv: -kv[1]["lavoro"])]
    tot = {k: sum(p[k] for p in out) for k in ("richieste", "misurate", "non_misurabili", "lavoro", "riletti", "ragionamento")}
    tot["progetti_attivi"] = sum(1 for p in out if p["richieste"])
    d = {"giorni": giorni, "da": da, "progetti": out, "totali": tot, "calcolato": time.strftime("%H:%M:%S")}
    _C[chiave] = (ora, d)
    return d

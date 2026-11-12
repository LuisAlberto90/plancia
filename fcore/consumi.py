"""Consumi per progetto: quanti token hanno usato gli agenti, progetto per progetto, giorno per giorno e richiesta per richiesta.
Solo lettura di cio che e gia sul PC (Claude Code, Copilot CLI, chat di VS Code): zero token, nessuna rete.
Onesta: Claude Code e Copilot CLI danno i token reali; la chat di VS Code li da solo a volte, altrimenti si STIMANO dal testo (marcato "stima").
La Plancia stessa non usa token: costa solo il testo che inietta nel contesto dell'agente, calcolato in `peso_plancia`."""
import json, os, time
from pathlib import Path
try: from . import richieste as RQ
except ImportError: import richieste as RQ
try: from . import vscodechat as VC, crediti as CRD
except ImportError: import vscodechat as VC, crediti as CRD

_C = {}
TOP = 5


def nome_modello(n):
    """Nome leggibile: toglie prefissi e data finale (claude-sonnet-4-5-20250929 -> claude-sonnet-4-5); vuoto -> 'non dichiarato'."""
    import re
    n = str(n or "").strip()
    if n in ("", "?"): return "non dichiarato"
    n = re.sub(r"^(copilot|github)[/:]", "", n, flags=re.I)
    return re.sub(r"-20\d{6}$", "", n)


def _taglio(giorni):
    """Data (AAAA-MM-GG, ora locale) da cui contare: 0 = tutto, 1 = solo oggi, N = ultimi N giorni compreso oggi."""
    if not giorni: return ""
    return time.strftime("%Y-%m-%d", time.localtime(time.time() - (giorni - 1) * 86400))


def peso_plancia(rad, sessioni, richieste):
    """Quanto costa la Plancia in token (stima, 4 caratteri = 1 token): e solo il testo che inietta nel contesto dell'agente.
    La Plancia in se gira sul PC e non usa token. Ritorna le voci e il totale 'iniettato' per questo periodo."""
    try:
        from fcore import auto, mcp
    except ImportError:
        import auto, mcp
    t = lambda x: max(1, len(x) // 4)
    regola = t(auto.regola("plancia")); prome = t("[Plancia] New message. Unless it is a pure question: same work as before -> plancia_piano_aggiungi; different work -> plancia_piano_nuovo with \"nuovo\": true. Plan before reading files.")
    schema = t(json.dumps(mcp.PIANO_TOOLS)); schema_pieno = t(json.dumps([x for x in mcp.TOOLS if x["name"] != "plancia_passo"] + mcp.PIANO_TOOLS))
    skill = 0
    try:
        m = [l for l in (Path(__file__).resolve().parent.parent / "skills" / "plancia-metodo" / "SKILL.md").read_text(encoding="utf-8").splitlines() if l.startswith("description:")]
        skill = t(m[0]) if m else 0
    except Exception: pass
    chiamate = 0
    try:
        f = Path(rad) / ".factory" / "eventi.jsonl"
        if f.is_file(): chiamate = sum(1 for l in f.read_text(encoding="utf-8", errors="replace").splitlines()[-20000:] if "plancia_piano" in l or "plancia_passo" in l)
    except Exception: pass
    iniettato = sessioni * (regola + skill) + max(0, richieste - sessioni) * prome
    return {"regola": regola, "promemoria": prome, "skill": skill, "schema": schema, "schema_pieno": schema_pieno, "chiamate": chiamate,
            "iniettato": iniettato, "voci": [
                {"nome": "Regola del piano (una volta per chat)", "token": regola, "volte": sessioni},
                {"nome": "Descrizione della skill (una volta per chat)", "token": skill, "volte": sessioni},
                {"nome": "Promemoria sui messaggi successivi", "token": prome, "volte": max(0, richieste - sessioni)}]}


def _progetto(rad, da):
    rich = RQ.tutte(rad, 5000)
    try: vs = VC.richieste(rad)
    except Exception: vs = []
    if vs: rich = [r for r in rich if r.get("fonte") != "vscode"] + [{"inizio": v["inizio"], "fonte": "vscode", "domanda": v["domanda"], "token_in": v.get("token_in", 0), "token_out": v.get("token_out", 0), "token_lavoro": v.get("token_in", 0) + v.get("token_out", 0),
                                                                      "ragionamento": v.get("ragionamento", 0), "modelli": {v.get("modello") or "?": [v.get("token_in", 0) + v.get("token_out", 0), 0, v.get("token_out", 0)]}, "ctx": v.get("ctx", 0), "ctx_max": v.get("ctx_max", 0), "dettaglio": v.get("dettaglio") or [], "stimato": v["stimato"], "sessione": "vs"} for v in vs]
    p = {"radice": str(rad), "nome": Path(rad).name, "richieste": 0, "misurate": 0, "non_misurabili": 0, "stimate": 0, "lavoro": 0, "riletti": 0, "ragionamento": 0,
         "ingresso": 0, "risposte": 0, "scritti": 0, "stima_lavoro": 0, "contesto": None, "modelli": {}, "piani": 0, "skills_usate": {}, "pl_chiamate": 0, "pl_token": 0, "fonti": {}, "giorni": {}, "top": [], "ultimo": ""}
    sess = set()
    for r in rich:
        g = str(r.get("inizio") or "")[:10]
        if da and g < da: continue
        lav = int(r.get("token_lavoro") or 0); ril = int(r.get("token_riletti") or 0); rag = int(r.get("ragionamento") or 0)
        ctx = int(r.get("ctx") or 0)
        if ctx and g:
            lim = int(r.get("ctx_max") or 0); c0 = p["contesto"]
            if c0 is None: c0 = p["contesto"] = {"ultimo": 0, "max": 0, "pct": 0, "picco": 0, "picco_pct": 0, "quando": "", "dettaglio": [], "richieste": 0, "somma": 0}
            c0["richieste"] += 1; c0["somma"] += ctx
            if ctx > c0["picco"]: c0["picco"] = ctx; c0["picco_pct"] = round(ctx * 100 / lim, 1) if lim else 0
            if str(r.get("inizio") or "") >= c0["quando"]:
                c0.update({"ultimo": ctx, "max": lim, "pct": round(ctx * 100 / lim, 1) if lim else 0, "quando": str(r.get("inizio") or ""), "dettaglio": [{"nome": d["nome"], "token": int(ctx * d["pct"] / 100), "pct": d["pct"]} for d in (r.get("dettaglio") or [])]})
        mis = (lav + ril + ctx) > 0; f = r.get("fonte") or "?"; stim = bool(r.get("stimato"))
        if not (r.get("token_in") or r.get("token_out") or r.get("token_scritti")) and lav: r = dict(r, token_in=lav)      # vecchi dati senza divisione: tutto in "ingresso"
        p["richieste"] += 1; p["misurate" if mis and not stim else "non_misurabili" if not mis else "stimate"] += 1
        p["lavoro"] += lav; p["riletti"] += ril; p["ragionamento"] += rag
        p["ingresso"] += int(r.get("token_in") or 0); p["risposte"] += int(r.get("token_out") or 0); p["scritti"] += int(r.get("token_scritti") or 0)
        if stim: p["stima_lavoro"] += lav
        mm = r.get("modelli") or {}
        for nm, (a1, a2, a3) in (mm.items() if mm else [("?", (lav, ril, int(r.get("token_out") or 0)))]):
            m0 = p["modelli"].setdefault(nome_modello(nm), {"modello": nome_modello(nm), "richieste": 0, "lavoro": 0, "riletti": 0, "risposte": 0}); m0["richieste"] += 1; m0["lavoro"] += a1; m0["riletti"] += a2; m0["risposte"] += a3
        if r.get("piano_scritto"): p["piani"] += 1
        p["pl_chiamate"] += int(r.get("plancia_chiamate") or 0); p["pl_token"] += int(r.get("plancia_token") or 0)
        for sk in r.get("skills") or []: p["skills_usate"][sk] = p["skills_usate"].get(sk, 0) + 1
        sess.add(r.get("sessione") or g)
        ff = p["fonti"].setdefault(f, {"richieste": 0, "misurate": 0, "lavoro": 0, "riletti": 0, "stimate": 0}); ff["richieste"] += 1; ff["misurate"] += 1 if mis and not stim else 0; ff["stimate"] += 1 if stim else 0; ff["lavoro"] += lav; ff["riletti"] += ril
        gg = p["giorni"].setdefault(g, {"giorno": g, "richieste": 0, "lavoro": 0}); gg["richieste"] += 1; gg["lavoro"] += lav
        if mis: p["top"].append({"domanda": (r.get("domanda") or "").strip().split("\n")[0][:110], "lavoro": lav, "riletti": ril, "inizio": str(r.get("inizio") or "")[:16].replace("T", " "), "fonte": f, "stimato": stim, "modello": ", ".join(sorted({nome_modello(k) for k in (r.get("modelli") or {})})) or ""})
        if g and g > p["ultimo"]: p["ultimo"] = g
    p["top"] = sorted(p["top"], key=lambda x: -x["lavoro"])[:TOP]
    p["giorni"] = sorted(p["giorni"].values(), key=lambda x: x["giorno"])
    p["plancia"] = peso_plancia(rad, len(sess) if p["richieste"] else 0, p["richieste"])
    p["plancia"]["piani"] = p["piani"]; p["plancia"]["pl_chiamate"] = p["pl_chiamate"]; p["plancia"]["pl_token"] = p["pl_token"]; p["plancia"]["iniettato"] += p["pl_token"]
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
    tot = {k: sum(p[k] for p in out) for k in ("richieste", "misurate", "non_misurabili", "stimate", "lavoro", "riletti", "ragionamento", "ingresso", "risposte", "scritti", "stima_lavoro")}
    mod = {}
    for p in out:
        p["modelli"] = sorted(p["modelli"].values(), key=lambda m: -m["lavoro"])
        for m in p["modelli"]:
            t0 = mod.setdefault(m["modello"], {"modello": m["modello"], "richieste": 0, "lavoro": 0, "riletti": 0, "risposte": 0})
            for k in ("richieste", "lavoro", "riletti", "risposte"): t0[k] += m[k]
        p["skills_usate"] = sorted(p["skills_usate"].items(), key=lambda kv: -kv[1])
    tot["modelli"] = sorted(mod.values(), key=lambda m: -m["lavoro"])
    tot["plancia"] = sum(p["plancia"]["iniettato"] for p in out)
    tot["progetti_attivi"] = sum(1 for p in out if p["richieste"])
    d = {"giorni": giorni, "da": da, "progetti": out, "totali": tot, "calcolato": time.strftime("%H:%M:%S")}
    _C[chiave] = (ora, d)
    return d


def _cr_vscode(v):
    """Crediti di una richiesta della chat di VS Code. Dato approssimato: la chat dichiara il contesto della chiamata piu grande (promptTokens, cache compresa) e i token scritti,
    non quante chiamate ha fatto ne quanta cache ha riusato. Si conta il contesto tutto come input pieno (alto per la cache, basso per le chiamate multiple)."""
    acc = CRD.nuovo(); CRD.aggiungi(acc, v.get("modello") or "", v.get("ctx") or v.get("token_in") or 0, 0, 0, v.get("token_out") or 0, approx=True)
    return acc


def _cr_campi(r):
    """Campi crediti della riga (solo Copilot): cr = crediti stimati, cd = [token per voce, crediti per voce], cx = 1 se approssimato, cm = modelli senza prezzo, cl = chiamate long context."""
    a = r.get("crediti")
    if r.get("fonte") not in ("copilot", "vscode") or not a: return {}
    return {"cr": round(a["c"], 4), "cd": [a["t"], [round(x, 4) for x in a["k"]]], "cx": 1 if a.get("approx") else 0, "cn": sorted(a["mancanti"])[:6], "cl": a.get("lunghe", 0)}


def righe(radici, giorni=90):
    """Elenco piatto delle richieste (tutti i progetti) per la pagina Consumi: filtri, grafici e regole di spreco si calcolano nel browser.
    giorni=0 -> tutto. Mai un errore: un progetto che non si legge viene saltato."""
    da = _taglio(giorni); out = []; progetti = []; vecchio = os.environ.get("FACTORY_ROOT")
    try:
        for i, rad in enumerate(radici):
            os.environ["FACTORY_ROOT"] = str(rad)
            try:
                rich = RQ.tutte(rad, 5000)
                try: vs = VC.richieste(rad)
                except Exception: vs = []
                if vs: rich = [r for r in rich if r.get("fonte") != "vscode"] + [{"inizio": v["inizio"], "fonte": "vscode", "domanda": v["domanda"], "token_in": v.get("token_in", 0), "token_out": v.get("token_out", 0), "token_lavoro": v.get("token_in", 0) + v.get("token_out", 0), "ragionamento": v.get("ragionamento", 0),
                                                                                  "modelli": {v.get("modello") or "?": [v.get("token_in", 0) + v.get("token_out", 0), 0, v.get("token_out", 0)]}, "ctx": v.get("ctx", 0), "ctx_max": v.get("ctx_max", 0), "crediti": _cr_vscode(v), "stimato": v["stimato"], "sessione": v.get("sessione") or "vs", "titolo": v.get("titolo", "")} for v in vs]
                n0 = len(out)
                for r in rich:
                    g = str(r.get("inizio") or "")[:10]
                    if da and g < da: continue
                    mm = r.get("modelli") or {}; mod = nome_modello(max(mm, key=lambda k: mm[k][0] + mm[k][2]) if mm else "")
                    out.append({"p": len(progetti), "t": str(r.get("inizio") or "")[:16], "f": r.get("fonte") or "?", "m": mod, "s": "%d|%s" % (len(progetti), r.get("sessione") or g),
                                "d": (r.get("domanda") or "").strip()[:300], "L": int(r.get("token_lavoro") or 0), "R": int(r.get("token_riletti") or 0), "O": int(r.get("token_out") or 0), "I": int(r.get("token_in") or 0),
                                "W": int(r.get("token_scritti") or 0), "G": int(r.get("ragionamento") or 0), "c": int(r.get("ctx") or 0), "cm": int(r.get("ctx_max") or 0), "st": 1 if r.get("stimato") else 0,
                                "pi": 1 if r.get("piano_scritto") else 0, **_cr_campi(r), "sk": r.get("skills") or [], "ti": str(r.get("titolo") or "")[:80], "pc": int(r.get("plancia_chiamate") or 0), "pt": int(r.get("plancia_token") or 0)})
                sess = {o["s"] for o in out[n0:]}
                ctx = None; cv = [v for v in vs if v.get("ctx")]
                if cv:
                    u = max(cv, key=lambda v: v["inizio"]); lim = int(u.get("ctx_max") or 0); pk = max(cv, key=lambda v: v["ctx"])
                    ctx = {"ultimo": u["ctx"], "max": lim, "picco": pk["ctx"], "dettaglio": [{"nome": d["nome"], "pct": d["pct"], "token": int(u["ctx"] * d["pct"] / 100)} for d in (u.get("dettaglio") or [])]}
                progetti.append({"nome": Path(rad).name, "radice": str(rad), "plancia": peso_plancia(rad, len(sess), len(out) - n0), "contesto": ctx})
            except Exception:
                progetti.append({"nome": Path(rad).name, "radice": str(rad), "plancia": None})
    finally:
        if vecchio is None: os.environ.pop("FACTORY_ROOT", None)
        else: os.environ["FACTORY_ROOT"] = vecchio
    out.sort(key=lambda x: x["t"], reverse=True)
    return {"giorni": giorni, "progetti": progetti, "righe": out[:6000], "troncate": len(out) > 6000, "calcolato": time.strftime("%H:%M:%S")}


def esporta(a):
    """Scrive le righe dei consumi in un JSON SENZA i testi delle domande (solo numeri, modelli, date): per verificare le regole su dati veri senza mandare nulla di privato."""
    try:
        try: from fcore import panoramica as PN
        except ImportError: from . import panoramica as PN
        d = righe(PN.progetti(), 90)
    except Exception as e:
        print("non riesco a leggere i consumi: %s" % e); return 1
    for r in d["righe"]: r["d"] = "(%d caratteri)" % len(r["d"]); r["ti"] = ""
    for i, p in enumerate(d["progetti"]): p["nome"] = "progetto-%d" % (i + 1); p["radice"] = ""
    f = Path(a[0] if a else "plancia-consumi.json"); f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    print("scritto %s: %d richieste, nessun testo dei prompt." % (f.resolve(), len(d["righe"]))); return 0

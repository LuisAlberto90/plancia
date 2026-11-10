"""Mappa del codice: i moduli del progetto e chi usa chi, letti dagli import (zero token, solo lettura).
Mostra la struttura vera, non il significato: "questo e il login" lo sa solo chi legge il codice.
In piu: quali moduli ha toccato l'agente nell'ultima richiesta e oggi (dai file registrati)."""
import os, re, time
from collections import Counter
from pathlib import Path
try: from . import contesto as CX, richieste as RQ
except ImportError: import contesto as CX, richieste as RQ

PY = re.compile(r"(?m)^[ \t]*(?:from[ \t]+([A-Za-z_][\w.]*)[ \t]+import|import[ \t]+([A-Za-z_][\w., \t]*))")
JAVA = re.compile(r"(?m)^[ \t]*import[ \t]+(?:static[ \t]+)?([\w.]+)\s*;")
JS = re.compile(r"""(?:from|require\(|import\()\s*['"](\.{1,2}/[^'"]*)['"]""")
EXT_JS = (".ts", ".tsx", ".js", ".jsx", ".vue")
LINGUA = {".py": "Python", ".java": "Java", ".kt": "Kotlin", ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript", ".jsx": "JavaScript", ".vue": "Vue"}
MAX_FILE, MAX_NODI, LEGGI = 4000, 40, 40000
_C = {}


def _mod(p):
    """Modulo di un file (percorso relativo). Come la mappa del progetto, ma Angular scende di un livello (src/app/<area>)."""
    parti = p.parts
    if parti[:2] == ("src", "app") and len(parti) >= 4: return "src/app/" + parti[2]
    return CX._modulo(p) or "(radice)"


def _leggi(f):
    try:
        with open(f, "rb") as h: return h.read(LEGGI).decode("utf-8", errors="ignore")
    except Exception: return ""


def _calcola(rad):
    rad = Path(rad); sorg = []; note = []
    for d, dirs, fs in os.walk(rad):
        dirs[:] = sorted(x for x in dirs if x not in CX.SALTA and not x.startswith(".") and not x.endswith(".egg-info"))
        for x in fs:
            e = Path(x).suffix.lower()
            if e not in LINGUA: continue
            if len(sorg) >= MAX_FILE: note.append("progetto molto grande: mappa parziale (primi %d file)" % MAX_FILE); break
            p = (Path(d) / x).relative_to(rad); sorg.append((_mod(p), p, e))
        if len(sorg) >= MAX_FILE: break
    info = {}
    for m, p, e in sorg:
        i = info.setdefault(m, {"id": m, "file": 0, "righe": 0, "lingue": Counter()}); i["file"] += 1; i["lingue"][LINGUA[e]] += 1
    pkg = {}                                                              # Java: package -> modulo
    for m in info:
        if info[m]["lingue"].get("Java") or info[m]["lingue"].get("Kotlin"): pkg[m.split(":")[-1]] = m
    nomi = {}                                                             # Python: nome del pacchetto -> modulo
    for m in info: nomi.setdefault(m.split("/")[-1], m)                 # alias: src/foo -> foo
    for m in info: nomi[m] = m                                          # i nomi esatti (cartella di primo livello) vincono sugli alias
    archi = Counter()
    for m, p, e in sorg:
        t = _leggi(rad / p); info[m]["righe"] += t.count("\n") + 1
        dest = set()
        if e == ".py":
            for a, b in PY.findall(t):
                for nm in ([a] if a else [x.strip().split(" as ")[0] for x in b.split(",")]):
                    top = nm.split(".")[0]
                    if top in nomi: dest.add(nomi[top])
        elif e in (".java", ".kt"):
            for imp in JAVA.findall(t):
                parti = imp.split(".")[:-1]
                while parti:
                    k = ".".join(parti)
                    if k in pkg: dest.add(pkg[k]); break
                    parti = parti[:-1]
        else:
            for ref in JS.findall(t):
                try: tgt = Path(os.path.normpath(str((p.parent / ref).as_posix())).replace("\\", "/"))
                except Exception: continue
                if tgt.parts and tgt.parts[0] != "..": dest.add(_mod(tgt))
        for b in dest:
            if b != m and b in info: archi[(m, b)] += 1
    tenuti = sorted(info.values(), key=lambda x: -x["righe"])[:MAX_NODI]; ids = {x["id"] for x in tenuti}
    if len(info) > MAX_NODI: note.append("%d moduli piu piccoli non mostrati" % (len(info) - MAX_NODI))
    return {"moduli": [{"id": x["id"], "file": x["file"], "righe": x["righe"], "lingua": (x["lingue"].most_common(1) or [("", 0)])[0][0]} for x in tenuti],
            "archi": [[a, b, n] for (a, b), n in sorted(archi.items(), key=lambda kv: -kv[1]) if a in ids and b in ids], "note": note}


def _tocca(rad, rich, ids):
    out = []
    for r in rich:
        for f in r.get("file") or []:
            f = str(f).replace("\\", "/")
            try:
                p = Path(os.path.relpath(f, str(rad))) if os.path.isabs(f) or re.match(r"^[A-Za-z]:/", f) else Path(f)
            except Exception: continue
            if p.parts and p.parts[0] != "..":
                m = _mod(p)
                if m in ids and m not in out: out.append(m)
    return out


def mappa(rad):
    k = str(rad); t = time.time()
    if k not in _C or t - _C[k][0] > 120: _C[k] = (t, _calcola(rad))
    d = dict(_C[k][1]); ids = {m["id"] for m in d["moduli"]}
    try: rich = [r for r in RQ.tutte(rad, 60) if r]
    except Exception: rich = []
    t0 = time.mktime(time.strptime(time.strftime("%Y-%m-%d"), "%Y-%m-%d"))
    d["toccati"] = {"ultima": _tocca(rad, rich[:1], ids), "oggi": _tocca(rad, [r for r in rich if (RQ._ts(r.get("inizio")) or 0) >= t0], ids)}
    d["ultima_domanda"] = ((rich[0].get("domanda") or "").strip().split("\n")[0][:120]) if rich else ""
    return d

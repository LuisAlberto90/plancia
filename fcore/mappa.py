"""Mappa dell'architettura: i blocchi del progetto divisi per livello (ingresso, logica, dati, trasversale) e chi usa chi, letti dagli import
(zero token, solo lettura). Il livello e dedotto dai nomi (controller, service, repository...): e un'ipotesi, la struttura degli import e un fatto.
In piu: quali blocchi ha toccato l'agente nell'ultima richiesta e oggi (dai file registrati)."""
import os, re, time
from collections import Counter
from pathlib import Path
try: from . import contesto as CX, richieste as RQ
except ImportError: import contesto as CX, richieste as RQ

PY = re.compile(r"(?m)^[ \t]*(?:from[ \t]+([A-Za-z_.][\w.]*)[ \t]+import[ \t]+([\w, \t]+)|import[ \t]+([A-Za-z_][\w., \t]*))")
JAVA = re.compile(r"(?m)^[ \t]*import[ \t]+(?:static[ \t]+)?([\w.]+(?:\.\*)?)\s*;")
JPKG = re.compile(r"(?m)^[ \t]*package[ \t]+([\w.]+)\s*;")
JS = re.compile(r"""(?:from|require\(|import\()\s*['"](\.{1,2}/[^'"]*)['"]""")
EXT_JS = (".ts", ".tsx", ".js", ".jsx", ".vue")
LINGUA = {".py": "Python", ".java": "Java", ".kt": "Kotlin", ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript", ".jsx": "JavaScript", ".vue": "Vue"}
LIVELLI = ["Ingresso", "Logica", "Dati", "Trasversale"]
SPIEGA = {"Ingresso": "da dove entra il lavoro: API, schermate, comandi, pannello",
          "Logica": "le regole e il lavoro vero (servizi, batch, calcoli)",
          "Dati": "database, repository, entità, modelli, file su disco",
          "Trasversale": "usato da tutti: configurazione, utility, sicurezza, errori"}
CHIAVI = [("Trasversale", r"config|util|helper|common|shared|security|exception|error|logg|constant|middleware|validat"),
          ("Dati", r"repositor|dao|entit|model|persist|jpa|mapper|schema|migrat|database|^db|store|storage|dto|record|orm"),
          ("Ingresso", r"controller|rest|api|web|resource|endpoint|route|view|^ui$|page|component|cli|main|^app$|handler|server|panel|pannell|hook|listener|command|gui|screen"),
          ("Logica", r"service|domain|usecase|business|logic|batch|job|task|process|manager|engine|worker|scheduler|plan|analy")]
MAX_FILE, MAX_NODI, LEGGI = 4000, 34, 40000
_C = {}


def _livello(parti):
    """Livello di un file dai nomi di cartelle e classe (dall'ultimo al primo: la cartella piu vicina al file conta di piu)."""
    for s in reversed([x.lower() for x in parti]):
        for liv, rx in CHIAVI:
            if re.search(rx, s): return liv
    return "Logica"


def _leggi(f):
    try:
        with open(f, "rb") as h: return h.read(LEGGI).decode("utf-8", errors="ignore")
    except Exception: return ""


def _test(p):
    return any(x.lower() in ("test", "tests", "__tests__", "spec", "e2e", "testing") for x in p.parts[:-1]) or re.search(r"(?i)(^test_|_test\.|\.spec\.|\.test\.)", p.name) is not None or re.search(r"(Test|Tests|IT)\.(java|kt)$", p.name) is not None


def _prefisso(liste):
    """Parte iniziale in comune a tutti i percorsi (es. com.azienda.progetto): non dice niente, si toglie."""
    if not liste: return []
    pre = list(liste[0])
    for l in liste[1:]:
        k = 0
        while k < len(pre) and k < len(l) and pre[k] == l[k]: k += 1
        pre = pre[:k]
    return pre


def _chiavi(file, prof):
    """Blocco di ogni file con una certa profondita: per Java/Kotlin il package, per gli altri la cartella; prof=None -> un blocco per file."""
    out = {}
    for f in file:
        if prof is None: out[f["p"]] = "/".join(f["parti"]); continue
        base = f["pkg"] if f["pkg"] is not None else list(f["parti"][:-1])
        out[f["p"]] = ".".join(base[:prof]) if f["pkg"] is not None else "/".join(base[:prof])
        if not out[f["p"]]: out[f["p"]] = "(base)"
    return out


def _calcola(rad):
    rad = Path(rad); file = []; note = []; ntest = 0
    for d, dirs, fs in os.walk(rad):
        dirs[:] = sorted(x for x in dirs if x not in CX.SALTA and not x.startswith(".") and not x.endswith(".egg-info"))
        for x in sorted(fs):
            e = Path(x).suffix.lower()
            if e not in LINGUA: continue
            p = (Path(d) / x).relative_to(rad)
            if _test(p): ntest += 1; continue
            if len(file) >= MAX_FILE: note.append("progetto molto grande: mappa parziale (primi %d file)" % MAX_FILE); break
            t = _leggi(rad / p); pkg = None
            if e in (".java", ".kt"):
                m = JPKG.search(t); pkg = m.group(1).split(".") if m else []
            file.append({"p": p.as_posix(), "path": p, "e": e, "t": t, "pkg": pkg, "righe": t.count("\n") + 1, "parti": p.parts})
        if len(file) >= MAX_FILE: break
    if ntest: note.append("%d file di test non mostrati" % ntest)
    pre = _prefisso([f["pkg"] for f in file if f["pkg"]])
    for f in file:
        if f["pkg"] is not None: f["pkg"] = f["pkg"][len(pre):]
        elif f["parti"][:2] == ("src", "app") and len(f["parti"]) >= 4: f["parti"] = f["parti"][2:]   # Angular: src/app/<area> -> area
    if pre: note.append("package comune tolto dai nomi: " + ".".join(pre))
    scelta = None
    for prof in (1, 2, 3, 4, None):                                       # il blocco piu fine che non fa esplodere il disegno
        ch = _chiavi(file, prof)
        if len(set(ch.values())) <= MAX_NODI: scelta = ch
        else: break
    if scelta is None: scelta = _chiavi(file, 1)
    if len(set(scelta.values())) < 6 and len(file) > 1:                   # cartella unica e piatta: un blocco per file, i piu grandi
        scelta = _chiavi(file, None)
    nodi = {}
    for f in file:
        k = scelta[f["p"]]; n = nodi.setdefault(k, {"id": k, "file": 0, "righe": 0, "lingue": Counter(), "liv": Counter(), "esempi": []})
        n["file"] += 1; n["righe"] += f["righe"]; n["lingue"][LINGUA[f["e"]]] += 1
        n["liv"][_livello((f["pkg"] if f["pkg"] is not None else list(f["parti"][:-1])) + [Path(f["p"]).stem])] += 1
        if len(n["esempi"]) < 6: n["esempi"].append(Path(f["p"]).name)
    fnodo = {f["p"]: scelta[f["p"]] for f in file}
    classe = {}                                                           # Java: nome completo della classe -> blocco; package -> blocchi
    pacc = {}
    for f in file:
        if f["pkg"] is not None:
            full = ".".join(f["pkg"] + [Path(f["p"]).stem]); classe[full] = fnodo[f["p"]]; pacc.setdefault(".".join(f["pkg"]), set()).add(fnodo[f["p"]])
    modpy = {}                                                            # Python: nome del modulo puntato -> blocco
    for f in file:
        if f["e"] == ".py":
            mm = ".".join(f["parti"])[:-3]; modpy[mm] = fnodo[f["p"]]
            if mm.endswith(".__init__"): modpy[mm[:-9]] = fnodo[f["p"]]
    byp = {f["p"] for f in file}; archi = Counter()
    for f in file:
        m = fnodo[f["p"]]; t = f["t"]; dest = set(); p = f["path"]
        if f["e"] == ".py":
            qui = list(f["parti"][:-1])
            for a, b, c in PY.findall(t):
                nomi = []
                if a:
                    liv = len(a) - len(a.lstrip(".")); base = a.lstrip(".")
                    pad = qui[:len(qui) - (liv - 1)] if liv else []
                    pre_ = ".".join(pad + ([base] if base else [])) if liv else base
                    nomi.append(pre_)
                    for x in b.split(","):
                        x = x.strip().split(" as ")[0].strip()
                        if x: nomi.append((pre_ + "." if pre_ else "") + x)
                else:
                    nomi += [x.strip().split(" as ")[0].strip() for x in c.split(",")]
                for nm in nomi:
                    k = nm
                    while k:
                        if k in modpy: dest.add(modpy[k]); break
                        k = k.rpartition(".")[0]
        elif f["e"] in (".java", ".kt"):
            pq = ".".join(pre) + "."
            for imp in JAVA.findall(t):
                jolly = imp.endswith(".*"); k = imp[:-2] if jolly else imp
                if pre and k.startswith(pq): k = k[len(pq):]
                if jolly: dest |= pacc.get(k, set()); continue
                while k:
                    if k in classe: dest.add(classe[k]); break
                    k = k.rpartition(".")[0]
        else:
            for ref in JS.findall(t):
                try: tgt = os.path.normpath((p.parent / ref).as_posix()).replace("\\", "/")
                except Exception: continue
                if tgt.startswith(".."): continue
                for cand in [tgt] + [tgt + e for e in EXT_JS] + [tgt + "/index" + e for e in EXT_JS]:
                    if cand in byp: dest.add(fnodo[cand]); break
        for b in dest:
            if b != m: archi[(m, b)] += 1
    out = []
    if len(nodi) > MAX_NODI:
        tenuti = {n["id"] for n in sorted(nodi.values(), key=lambda x: -x["righe"])[:MAX_NODI]}; note.append("%d blocchi più piccoli non mostrati" % (len(nodi) - MAX_NODI))
        nodi = {k: v for k, v in nodi.items() if k in tenuti}; archi = Counter({k: v for k, v in archi.items() if k[0] in tenuti and k[1] in tenuti})
    for n in nodi.values():
        liv = n["liv"].most_common(1)[0][0]
        out.append({"id": n["id"], "livello": liv, "file": n["file"], "righe": n["righe"], "lingua": (n["lingue"].most_common(1) or [("", 0)])[0][0], "esempi": n["esempi"]})
    return {"moduli": out, "archi": [[a, b, n] for (a, b), n in sorted(archi.items(), key=lambda kv: -kv[1])], "livelli": LIVELLI, "spiega": SPIEGA, "note": note, "_fnodo": fnodo}


def _tocca(rad, rich, fnodo):
    """Blocchi toccati dai file indicati (percorsi relativi o assoluti, anche Windows)."""
    out = []
    for r in rich:
        for f in r.get("file") or []:
            f = str(f).replace("\\", "/")
            try:
                p = Path(os.path.relpath(f, str(rad))).as_posix() if os.path.isabs(f) or re.match(r"^[A-Za-z]:/", f) else Path(f).as_posix()
            except Exception: continue
            if p.startswith(".."): continue
            m = fnodo.get(p)
            if m and m not in out: out.append(m)
    return out


def mappa(rad):
    k = str(rad); t = time.time()
    if k not in _C or t - _C[k][0] > 120: _C[k] = (t, _calcola(rad))
    d = dict(_C[k][1]); fn = d.pop("_fnodo", {})
    try: rich = [r for r in RQ.tutte(rad, 60) if r]
    except Exception: rich = []
    t0 = time.mktime(time.strptime(time.strftime("%Y-%m-%d"), "%Y-%m-%d"))
    ids = {m["id"] for m in d["moduli"]}; fn = {f: m for f, m in fn.items() if m in ids}
    d["toccati"] = {"ultima": _tocca(rad, rich[:1], fn), "oggi": _tocca(rad, [r for r in rich if (RQ._ts(r.get("inizio")) or 0) >= t0], fn)}
    d["ultima_domanda"] = ((rich[0].get("domanda") or "").strip().split("\n")[0][:120]) if rich else ""
    return d

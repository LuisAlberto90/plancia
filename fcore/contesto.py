"""Mappa del progetto per gli agenti, calcolata SENZA LLM: stack, comandi, moduli, test, file da non leggere interi.
  plancia contesto            mostra la mappa
  plancia contesto --scrivi   la salva in .factory/CONTESTO.md (l'agente la legge al posto di esplorare: meno token)
Rilanciala quando la struttura cambia; `plancia salute` avvisa se e vecchia."""
import json, os, re, sys, time
from pathlib import Path
try: from . import store as lib
except ImportError: import store as lib

SALTA = {".git", ".factory", ".claude", ".github", ".vscode", ".idea", "node_modules", "venv", ".venv", "env", "__pycache__", "dist", "build", "target", ".pytest_cache",
         ".mypy_cache", ".tox", ".gradle", ".next", "coverage", "site-packages", ".ipynb_checkpoints", "out", "bin", "obj"}
LINGUE = {".py": "Python", ".java": "Java", ".kt": "Kotlin", ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript", ".jsx": "JavaScript", ".go": "Go", ".rs": "Rust",
          ".cs": "C#", ".php": "PHP", ".rb": "Ruby", ".sql": "SQL", ".sh": "Shell", ".ps1": "PowerShell", ".scala": "Scala", ".cbl": "COBOL", ".cob": "COBOL", ".vue": "Vue",
          ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".ipynb": "Notebook", ".yaml": "YAML", ".yml": "YAML"}
CODICE = {k for k, v in LINGUE.items() if v not in ("YAML", "HTML", "CSS", "SCSS", "Notebook")}
MAX_FILE = 20000


def _righe(f):
    try:
        with open(f, "rb") as h: return h.read(4_000_000).count(b"\n") + 1
    except Exception: return 0


def scansiona(rad):
    rad = Path(rad); files, lingue, moduli, grandi, test, note, n = [], {}, {}, [], set(), [], 0
    for d, dirs, fs in os.walk(rad):
        dirs[:] = sorted(x for x in dirs if x not in SALTA and not x.startswith(".") and not x.endswith(".egg-info"))
        rel = Path(d).relative_to(rad)
        for x in fs:
            n += 1
            if n > MAX_FILE: note.append("progetto molto grande: mappa parziale (primi %d file)" % MAX_FILE); break
            e = Path(x).suffix.lower()
            if e not in LINGUE: continue
            p = rel / x; r = _righe(rad / p) if e in CODICE or e == ".ipynb" else 0
            lingue[LINGUE[e]] = lingue.get(LINGUE[e], 0) + (r if e in CODICE else 1)
            top = _modulo(p)
            if top and e in CODICE: m = moduli.setdefault(top, [0, 0]); m[0] += 1; m[1] += r
            if r > 1000 and e in CODICE: grandi.append((r, p.as_posix()))
            if e == ".ipynb" and (rad / p).stat().st_size > 1_000_000: grandi.append((-(rad / p).stat().st_size // 1_000_000, p.as_posix()))
            if re.search(r"(^|/)(tests?|spec|__tests__)(/|$)|(^|/)test_[^/]+\.py$|_test\.(py|go)$|\.(spec|test)\.[jt]sx?$|Test\.java$", p.as_posix()): test.add(_cartella_test(p))
        if n > MAX_FILE: break
    return {"lingue": sorted(lingue.items(), key=lambda x: -x[1]), "moduli": sorted(moduli.items(), key=lambda x: -x[1][1]), "grandi": sorted(grandi, key=lambda x: -abs(x[0]))[:10],
            "test": sorted(test)[:10], "note": note}


def _modulo(p):
    parti = p.parts
    if len(parti) < 2: return None
    if "java" in parti and parti.index("java") >= 1 and parti[parti.index("java") - 1] in ("main", "test"):   # Java: modulo = package a 4 livelli
        i = parti.index("java"); pk = parti[i + 1:-1]
        return ("/".join(parti[:i - 2]) + ":" if i > 2 else "") + (".".join(pk[:4]) or "(default)")
    if parti[0] in ("src", "lib", "app", "packages", "modules", "apps", "services") and len(parti) >= 3: return parti[0] + "/" + parti[1]
    return parti[0]


def _cartella_test(p):
    s = p.as_posix(); m = re.search(r"^(.*?/(?:tests?|spec|__tests__))(/|$)", s)
    return m.group(1) if m else (p.parent.as_posix() or ".")


BUILD = ("pom.xml", "build.gradle", "build.gradle.kts", "package.json", "go.mod", "Cargo.toml", "pyproject.toml", "requirements.txt", "setup.py", "Makefile", "angular.json")


def sottoprogetti(rad):
    """Cartelle (fino a 2 livelli) con un proprio file di build: workspace con backend e frontend separati."""
    rad = Path(rad); out = []
    for d in sorted(x for x in rad.iterdir() if x.is_dir() and x.name not in SALTA and not x.name.startswith(".")):
        if any((d / b).exists() for b in BUILD): out.append(d)
        else:
            for d2 in sorted(x for x in d.iterdir() if x.is_dir() and x.name not in SALTA and not x.name.startswith(".")) if d.is_dir() else []:
                if any((d2 / b).exists() for b in BUILD): out.append(d2)
    return out[:8]


def comandi(rad, _sotto=True):
    rad = Path(rad); c = []
    def add(k, v): c.append((k, v)) if (k, v) not in c else None
    pj = rad / "package.json"
    if pj.exists():
        try:
            sc = json.loads(pj.read_text(encoding="utf-8")).get("scripts", {})
            for k in ("dev", "start", "build", "test", "lint"):
                if k in sc: add(k, "npm run %s" % k if k not in ("start", "test") else "npm %s" % k)
        except Exception: pass
    if (rad / "pom.xml").exists():
        mv = ("mvnw.cmd" if os.name == "nt" and (rad / "mvnw.cmd").exists() else "./mvnw") if (rad / "mvnw").exists() or (rad / "mvnw.cmd").exists() else "mvn"
        if mv == "mvn": mv = _maven_trovato() or mv
        add("build", "%s -q package -DskipTests" % mv); add("test", "%s test" % mv); add("test di una classe", "%s test -Dtest=NomeClasseTest" % mv)
        if (rad / "src/main/resources").is_dir(): add("avvio (Spring Boot)", "%s spring-boot:run" % mv)
    if (rad / "build.gradle").exists() or (rad / "build.gradle.kts").exists(): add("build", "./gradlew build -x test"); add("test", "./gradlew test")
    if (rad / "go.mod").exists(): add("build", "go build ./..."); add("test", "go test ./...")
    if (rad / "Cargo.toml").exists(): add("build", "cargo build"); add("test", "cargo test")
    py = any((rad / x).exists() for x in ("pyproject.toml", "setup.py", "requirements.txt", "setup.cfg", "pytest.ini", "tox.ini")) or any(rad.glob("*.py")) or (rad / "src").is_dir() and any((rad / "src").rglob("*.py"))
    if py and ((rad / "pom.xml").exists() or (rad / "package.json").exists()) and not any(rad.glob("*.py")) and not any(rad.glob("*/*.py")) and not (rad / "pyproject.toml").exists(): py = False   # requirements.txt in un progetto Java/Node: non e Python
    if py:
        if (rad / "requirements.txt").exists(): add("dipendenze", "pip install -r requirements.txt")
        elif (rad / "pyproject.toml").exists(): add("dipendenze", "pip install -e .")
        pyx = lib.config().get("python") or next((x for x in (".venv/bin/python", "venv/bin/python", ".venv/Scripts/python.exe", "venv/Scripts/python.exe") if (rad / x).exists()), None) \
              or next((str(x) for x in (Path.home() / ".venvs" / rad.name / "bin" / "python", Path.home() / ".venvs" / rad.name.lower() / "bin" / "python") if x.exists()), None)
        add("python", "`%s` (venv del progetto: usalo per test e pip install)" % pyx if pyx else "nessun venv: crealo con `python3 -m venv ~/.venvs/%s` (fuori da cartelle condivise) prima di installare pacchetti" % rad.name)
        add("test", ("%s -m pytest -q" % pyx if pyx else "python -m pytest -q") + _radice_test_py(rad))
    mk = rad / "Makefile"
    if mk.exists():
        for t in re.findall(r"^([a-zA-Z][\w-]*):", mk.read_text(errors="ignore"), re.M)[:8]:
            if t in ("build", "test", "run", "lint", "dev", "install"): add(t, "make " + t)
    for f in ("docker-compose.yml", "docker-compose.yaml", "compose.yaml"):
        if (rad / f).exists(): add("servizi", "docker compose up -d"); break
    if _sotto and not any(k in ("build", "test") for k, _ in c):
        for s in sottoprogetti(rad):
            rel = s.relative_to(rad).as_posix()
            for k, v in comandi(s, False):
                if k == "python" or k == "dipendenze" and "venv" in v: continue
                add("%s: %s" % (rel, k), "cd %s && %s" % (rel, v.strip("`")))
    return c


def _radice_test_py(rad):
    for c in sorted(Path(rad).rglob("conftest.py")):
        if not set(c.parts) & SALTA: return ""
    for d in ("tests", "test"):
        if (Path(rad) / d).is_dir(): return " " + d
    for t in sorted(Path(rad).rglob("tests")):
        if t.is_dir() and not set(t.parts) & SALTA:
            par = t.parent.relative_to(rad).as_posix()
            return "  (da %s: cd %s && python -m pytest -q tests)" % (par, par) if par != "." else " tests"
    return ""


def avvio(rad):
    rad = Path(rad); out = []
    for pat in ("main.py", "app.py", "manage.py", "wsgi.py", "server.py", "*_main.py", "*scheduled*job*.py", "Application.java", "index.ts", "main.ts", "main.go"):
        for f in sorted(rad.glob(pat)) + sorted((rad / "src").glob(pat) if (rad / "src").is_dir() else []):
            if f.is_file(): out.append(f.relative_to(rad).as_posix())
    return out[:10]


def documenti(rad):
    rad = Path(rad); out = [x for x in ("README.md", "README.rst", "AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md", ".github/copilot-instructions.md") if (rad / x).exists()]
    for d in ("docs", "doc", "documentation"):
        if (rad / d).is_dir(): out += sorted(p.relative_to(rad).as_posix() for p in (rad / d).glob("*.md"))[:8]
    return out[:14]


def mappa(rad=None):
    rad = Path(rad or lib.radice()); s = scansiona(rad); c = comandi(rad); a = avvio(rad); dc = documenti(rad)
    r = ["# Mappa del progetto: %s" % rad.name, "", "Generata da `plancia contesto` il %s, senza LLM. Leggila PRIMA di esplorare: cio che e qui non va ricercato." % time.strftime("%Y-%m-%d %H:%M"), ""]
    if s["lingue"]: r += ["## Stack", "- " + ", ".join("%s (%s)" % (k, ("%d righe" % v) if k not in ("Notebook", "YAML", "HTML", "CSS", "SCSS") else "%d file" % v) for k, v in s["lingue"][:6]), ""]
    if c: r += ["## Comandi (verificali una volta, poi aggiorna qui se diversi)"] + [("- %s: %s" if k == "python" else "- %s: `%s`") % (k, v) for k, v in c] + [""]
    if a: r += ["## Punti di avvio"] + ["- `%s`" % x for x in a] + [""]
    if s["moduli"]: r += ["## Moduli (file di codice, righe)"] + ["- `%s/` %d file, %d righe" % (k, v[0], v[1]) for k, v in s["moduli"][:15]] + [""]
    if s["test"]: r += ["## Test"] + ["- `%s/`" % x for x in s["test"]] + [""]
    if s["grandi"]: r += ["## File grandi: leggi solo il pezzo che serve (grep, range di righe), mai interi"] + [("- `%s` %d righe" % (p, n)) if n > 0 else ("- `%s` notebook %d MB" % (p, -n)) for n, p in s["grandi"]] + [""]
    if dc: r += ["## Documenti"] + ["- `%s`" % x for x in dc] + [""]
    r += ["## Da non esplorare", "- " + ", ".join(sorted(x for x in SALTA if (rad / x).exists()) or ["-"]), ""] + ["> " + x for x in s["note"]]
    return "\n".join(r).rstrip() + "\n"


def main(a):
    if a[:1] in (["-h"], ["--help"]): print(__doc__); return 0
    t = mappa()
    if "--scrivi" in a:
        f = lib.dir_() / "CONTESTO.md"; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(t, encoding="utf-8")
        print("scritto %s (%d righe)" % (f, t.count("\n"))); return 0
    print(t); return 0


if __name__ == "__main__": sys.exit(main(sys.argv[1:]))


def _maven_trovato():
    """Maven/JDK non nel PATH (PC aziendali): li cerco nei posti soliti e scrivo il comando completo, cosi l'agente non si blocca."""
    import glob, shutil
    if shutil.which("mvn") and (shutil.which("java") or os.environ.get("JAVA_HOME")): return None
    home = str(Path.home())
    if os.name == "nt":
        mvn = sorted(glob.glob(r"C:\Strumenti\*maven*\bin\mvn.cmd") + glob.glob(r"C:\Strumenti\*maven*\*\bin\mvn.cmd") + glob.glob(r"C:\Program Files\*maven*\bin\mvn.cmd")
                     + glob.glob(home + r"\*maven*\bin\mvn.cmd") + glob.glob(home + r"\.m2\wrapper\dists\*\*\*\bin\mvn.cmd"))
        jdk = [] if (shutil.which("java") or os.environ.get("JAVA_HOME")) else sorted(
            d for d in glob.glob(r"C:\Program Files\Java\jdk*") + glob.glob(r"C:\Program Files\Eclipse Adoptium\jdk*") + glob.glob(r"C:\Program Files\Microsoft\jdk*")
            + glob.glob(r"C:\Strumenti\*jdk*") + glob.glob(r"C:\Strumenti\*Jdk*") + glob.glob(home + r"\.jdks\*") + glob.glob(home + r"\*jdk*") + glob.glob(home + r"\*Jdk*")
            if os.path.isfile(os.path.join(d, "bin", "java.exe")))
        if not mvn and not jdk: return None
        jh = ("$env:JAVA_HOME='%s'; " % jdk[-1]) if jdk else ""
        return "%s& '%s'" % (jh, mvn[-1]) if mvn else jh + "mvn"
    mvn = sorted(glob.glob(home + "/*maven*/bin/mvn") + glob.glob("/opt/*maven*/bin/mvn"))
    return mvn[-1] if mvn else None

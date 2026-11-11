"""Cosa si ripete nel lavoro con gli agenti in un progetto -> candidati a diventare skill o agenti (zero token: solo i fatti gia registrati).
Guarda le richieste passate (Claude Code, Copilot CLI, chat di VS Code) e cerca: comandi rifatti spesso, file riletti ogni volta, errori che tornano,
domande simili, richieste di sola analisi. Ogni candidato dice cosa ha visto (con numeri ed esempi) e cosa succede se lo accetti."""
import re, time
from pathlib import Path
try: from . import richieste as RQ, store as lib
except ImportError: import richieste as RQ; import store as lib

CARTELLE = {"copilot": ".github", "claude": ".claude"}
MIN_RICHIESTE = 3                                                    # sotto questa soglia e un caso, non un'abitudine
BANALI = re.compile(r"(?i)^\s*(ls|dir|cd|pwd|cat|type|echo|head|tail|grep|rg|find|where|which|sleep|clear|cls|set-location|get-childitem|get-content|select-string|write-output|plancia|true)\b")
GIT_BANALI = re.compile(r"(?i)\bgit\s+(status|diff|log|show|branch|add|stash|remote|fetch|rev-parse|config)\b")
STRUMENTI = r"mvnw?(?:\.cmd)?|gradlew?(?:\.bat)?|npm|npx|pnpm|yarn|pytest|dotnet|cargo|make|docker-compose|docker|ng|tsc|ruff|eslint|terraform|kubectl|gh|pip|poetry|uv|go|flake8|black|mypy"
CHIAVE = re.compile(r"(?:^|[\s&;|'\"\\/(])(" + STRUMENTI + r")(?:\.cmd|\.exe|\.bat)?['\"]?\s+((?:-{1,2}[\w.-]+(?:=\S+)?\s+)*)([\w:.-]+)(?:\s+([\w:.-]+))?", re.I)
IGNORA_FILE = re.compile(r"(?i)(^|/)(\.factory|\.git|node_modules|target|dist|build|__pycache__|\.venv)/|(^|/)(CONTESTO\.md|AGENTS\.md|CLAUDE\.md|SKILL\.md|README\.md|package-lock\.json|yarn\.lock|pom\.xml)$|copilot-instructions")
ANALISI = re.compile(r"(?i)\b(analizz|spiega|controlla|verifica|rivedi|revisione|review|cerca|trova|audit|check|explain|analy[sz]e|investigate|find|capire|perch[eé]|dove|come funziona)\w*")


def _slug(s): return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")[:30] or "x"


def _chiave(cosa):
    """'mvn test -Dtest=X' -> 'mvn test'; 'npm run build' -> 'npm run build'. None se banale o non riconoscibile."""
    c = str(cosa or "").strip()
    if not c or BANALI.match(c) or GIT_BANALI.search(c): return None
    m = CHIAVE.search(c)
    if not m: return None
    tool = re.sub(r"(?i)\.(cmd|exe|bat)$", "", m.group(1)).lower(); sub = (m.group(3) or "").lower()
    if tool in ("mvnw", "mvn.cmd"): tool = "mvn"
    if sub.startswith("-"): return None
    extra = (" " + m.group(4).lower()) if tool in ("npm", "pnpm", "yarn", "npx", "docker", "cargo", "poetry", "uv") and sub in ("run", "exec", "compose") and m.group(4) else ""
    return ("%s %s%s" % (tool, sub, extra)).strip()


def _quando(r):
    ep = RQ._ts(r.get("fine") or r.get("inizio")) or 0
    return time.strftime("%d/%m", time.localtime(ep)) if ep else ""


def _dom(r): return lib.redigi_testo((r.get("domanda") or "").strip().split("\n")[0], 90)


def _parole(t): return set(w for w in re.findall(r"[a-zà-ú]{4,}", str(t).lower()))


def _testo_skill_esistenti(rad):
    out = ""
    for d in (Path(rad) / ".claude" / "skills", Path(rad) / ".github" / "skills", Path(rad) / ".agents" / "skills"):
        for f in sorted(d.glob("*/SKILL.md")) if d.is_dir() else []:
            try: out += f.read_text(encoding="utf-8", errors="ignore")[:8000].lower() + "\n"
            except Exception: pass
    return out


def _skill_vicina(rad, parole):
    """La skill gia presente che assomiglia di piu a queste parole: (nome, copertura 0-1, parole mancanti). None se non ce ne sono."""
    best = None
    for d in (Path(rad) / ".claude" / "skills", Path(rad) / ".github" / "skills", Path(rad) / ".agents" / "skills"):
        for f in sorted(d.glob("*/SKILL.md")) if d.is_dir() else []:
            try: t = f.read_text(encoding="utf-8", errors="ignore")[:8000]
            except Exception: continue
            pw = _parole(f.parent.name + " " + t)
            if not parole: continue
            cop = len(parole & pw) / float(len(parole))
            if best is None or cop > best[1]: best = (f.parent.name, cop, sorted(parole - pw)[:8])
    return best


_C = {}


def analizza(rad, limite=200):
    """Lista di candidati + quante richieste ho guardato (in cache 30 s: la pagina la chiede piu volte)."""
    k = str(rad); t = time.time()
    if k in _C and t - _C[k][0] < 30: return _C[k][1]
    _C[k] = (t, _analizza(rad, limite)); return _C[k][1]


def _analizza(rad, limite):
    try: rich = RQ.tutte(rad, limite)
    except Exception: rich = []
    rich = [r for r in rich if r]
    nome = Path(rad).name; esistenti = _testo_skill_esistenti(rad); cand = []
    info = {"richieste": len(rich), "dal": ""}
    if rich: info["dal"] = _quando(rich[-1])
    # 1) comandi rifatti spesso
    cm = {}
    for i, r in enumerate(rich):
        for a in r.get("attivita") or []:
            if a.get("tipo") != "comando": continue
            k = _chiave(a.get("cosa"))
            if not k: continue
            e = cm.setdefault(k, {"rich": set(), "n": 0, "esempi": [], "ultimo": "", "err": 0})
            e["rich"].add(i); e["n"] += 1; e["err"] += 1 if a.get("esito") == "errore" else 0
            c = str(a.get("cosa") or "")
            if c and c not in e["esempi"]: e["esempi"].append(c)
            if not e["ultimo"]: e["ultimo"] = _quando(r)
    for k, e in sorted(cm.items(), key=lambda x: -len(x[1]["rich"])):
        if len(e["rich"]) < MIN_RICHIESTE or e["n"] < MIN_RICHIESTE + 1 or k in esistenti: continue
        completi = [x for x in e["esempi"] if not x.endswith("…") and len(x) < 88]
        cand.append({"id": "cand-cmd-" + _slug(k), "genere": "skill", "tipo_cand": "comando", "chiave": k, "completi": completi[:4], "peso": len(e["rich"]),
                     "titolo": "Il comando `%s` lo rifai spesso: una skill lo ricorda all'agente" % k, "ambito": "solo questo progetto",
                     "visto": ["Usato %d volte in %d richieste diverse (ultima volta: %s)." % (e["n"], len(e["rich"]), e["ultimo"])] + (["Andato male %d volte: l'agente fatica a ricordare come si lancia." % e["err"]] if e["err"] else []) + ["Esempio: " + (completi[0] if completi else e["esempi"][0])],
                     "perche": "Senza una skill l'agente riscopre ogni volta come si lancia (percorsi, opzioni, JDK fuori dal PATH) e consuma token per rifarlo.",
                     "effetto": "Creo la skill «%s-comandi» con i comandi visti qui sopra. Resta sul tuo PC, esclusa da git." % _slug(nome)})
    # 2) file riletti in molte richieste
    fl = {}
    for i, r in enumerate(rich):
        for p in {str(a.get("cosa") or "").replace("\\", "/") for a in r.get("attivita") or [] if a.get("tipo") == "leggi"}:
            if p and p != "file" and "," not in p and not IGNORA_FILE.search(p): fl.setdefault(p, set()).add(i)
    caldi = sorted([(p, len(s)) for p, s in fl.items() if len(s) >= 4], key=lambda x: -x[1])[:5]
    if caldi and (caldi[0][1] >= 5 or len(caldi) >= 2) and not any(p.split("/")[-1].lower() in esistenti for p, _ in caldi[:2]):
        cand.append({"id": "cand-file-riletti", "genere": "skill", "tipo_cand": "file", "peso": caldi[0][1],
                     "titolo": "L'agente rilegge ogni volta gli stessi file (%d)" % len(caldi), "ambito": "solo questo progetto",
                     "visto": ["%s: letto in %d richieste" % (p, n) for p, n in caldi],
                     "scegli_cartella": True, "perche": "Se un file serve quasi a ogni richiesta, un riassunto breve (a cosa serve, funzioni chiave, trappole) fa risparmiare token e fa sbagliare meno.",
                     "effetto": "Ti do il testo da incollare in una chat: l'agente scrive la skill leggendo quei file, una volta.",
                     "prompt": "Create a project skill named %s-key-files with a SKILL.md (max 40 lines). Read these files: %s. For each: purpose in one line, the 3-5 functions or sections that matter, and the traps (what breaks if you change it). Description (frontmatter) must say: use when working on these files. Skills folder: <skills dir>. Then add that folder to .git/info/exclude." % (_slug(nome), ", ".join(p for p, _ in caldi))})
    # 3) errori che tornano
    er = {}
    for i, r in enumerate(rich):
        for a in r.get("attivita") or []:
            if a.get("esito") != "errore" or a.get("tipo") != "comando": continue
            k = _chiave(a.get("cosa")) or re.sub(r"\d+", "N", str(a.get("cosa") or ""))[:40]
            e = er.setdefault(k, {"rich": set(), "ultimo": "", "cosa": str(a.get("cosa") or "")})
            e["rich"].add(i)
            if not e["ultimo"]: e["ultimo"] = _quando(r)
    for k, e in sorted(er.items(), key=lambda x: -len(x[1]["rich"])):
        if len(e["rich"]) < 2 or not k: continue
        cand.append({"id": "cand-errore-" + _slug(k), "genere": "skill", "tipo_cand": "errore", "peso": len(e["rich"]),
                     "titolo": "Lo stesso errore torna: `%s`" % k[:50], "ambito": "solo questo progetto",
                     "visto": ["Fallito in %d richieste diverse (ultima: %s)." % (len(e["rich"]), e["ultimo"]), "Comando: " + e["cosa"][:90]],
                     "scegli_cartella": True, "perche": "Quando un comando fallisce sempre allo stesso modo, la soluzione va scritta una volta in una skill: l'agente la legge invece di rifare gli stessi tentativi.",
                     "effetto": "Ti do il testo da incollare: l'agente riproduce l'errore, trova la causa e scrive la skill di risoluzione.",
                     "prompt": "Run `%s` once, find why it fails and fix the cause if it is in the project config. Then create a project skill named %s-fix-%s (max 25 lines): the symptom, the cause, the exact fix, how to check it worked. Skills folder: <skills dir>. Add the folder to .git/info/exclude." % (e["cosa"][:90], _slug(nome), _slug(k)[:20])})
        break                                                          # uno solo per volta: il piu frequente
    # 4) domande simili
    cl = []
    for i, r in enumerate(rich):
        pw = _parole(_dom(r))
        if len(pw) < 4: continue
        for c in cl:
            if len(pw & c["pw"]) / float(len(pw | c["pw"])) >= 0.5: c["rich"].append(i); break
        else: cl.append({"pw": pw, "rich": [i]})
    for c in sorted(cl, key=lambda c: -len(c["rich"])):
        if len(c["rich"]) < MIN_RICHIESTE: break
        ex = [_dom(rich[i]) for i in c["rich"][:3]]; ch = "cand-ricorrente-" + _slug(" ".join(sorted(c["pw"])[:3]))
        conta = {}
        for i in c["rich"]:
            for w in _parole(_dom(rich[i])): conta[w] = conta.get(w, 0) + 1
        chiavi = {w for w, n in conta.items() if n * 2 >= len(c["rich"])} or c["pw"]
        vic = _skill_vicina(rad, chiavi)
        visto = ["Richieste molto simili in %d occasioni, l'ultima il %s." % (len(c["rich"]), _quando(rich[c["rich"][0]]))] + ["\u00ab%s\u00bb" % x for x in ex]
        esempi = "; ".join('"%s"' % x for x in ex)
        if vic and vic[1] >= 0.6:
            cand.append({"id": ch, "genere": "skill", "tipo_cand": "ricorrente", "peso": len(c["rich"]) + 1,
                         "titolo": "La skill \u201c%s\u201d esiste ma continui a ripetere la richiesta (%d volte): va migliorata" % (vic[0], len(c["rich"])), "ambito": "solo questo progetto",
                         "visto": visto + ["La skill copre gia questi temi, ma tu devi comunque chiederlo di nuovo: probabilmente la descrizione non la fa scattare."],
                         "perche": "Una skill utile deve scattare da sola. Se continui a ripetere le stesse frasi, la sua descrizione non contiene le parole che usi tu.",
                         "effetto": "Ti do il testo da incollare: l'agente riscrive la descrizione con le tue parole e ci aggiunge cio che chiedi ogni volta.",
                         "prompt": "I keep asking for: %s. Read the skill '%s' (in .claude/skills or .github/skills). Improve ONLY its frontmatter description and body: make the description say when to use it with the words I use in those requests, and add the steps you had to improvise. Keep it under 40 lines." % (esempi, vic[0])})
        elif vic and vic[1] >= 0.3:
            cand.append({"id": ch, "genere": "skill", "tipo_cand": "ricorrente", "peso": len(c["rich"]),
                         "titolo": "Ti capita di chiedere cose simili (%d volte): falle entrare nella skill \u201c%s\u201d" % (len(c["rich"]), vic[0]), "ambito": "solo questo progetto",
                         "visto": visto + ["La skill \u201c%s\u201d copre in parte l'argomento (mancano: %s)." % (vic[0], ", ".join(vic[2]) or "-")],
                         "perche": "Meglio far crescere una skill che ne hai gia che crearne una nuova: ogni skill in piu costa token a ogni chat.",
                         "effetto": "Ti do il testo da incollare: l'agente aggiunge alla skill la procedura per questi casi.",
                         "prompt": "I often ask for things like: %s. Extend the existing skill '%s' so it also covers this kind of request: add the steps, commands/files to use and what to check at the end, and update its description so it triggers on these words. Do not create a new skill." % (esempi, vic[0])})
        else:
            cand.append({"id": ch, "genere": "skill", "tipo_cand": "ricorrente", "peso": len(c["rich"]),
                         "titolo": "Ti capita di chiedere cose simili (%d volte)" % len(c["rich"]), "ambito": "solo questo progetto",
                         "visto": visto, "scegli_cartella": True, "perche": "Un compito che ripeti si puo scrivere una volta come procedura: l'agente la segue sempre allo stesso modo invece di reinventarla.",
                         "effetto": "Ti do il testo da incollare: l'agente scrive la procedura partendo dalle tue richieste.",
                         "prompt": "I often ask for things like: %s. Create a project skill (max 40 lines) named %s-%s with the procedure you would follow for this kind of request: steps, which commands/files to use, what to check at the end. The frontmatter description must say when to use it. Skills folder: <skills dir>. Add the folder to .git/info/exclude." % (esempi, _slug(nome), _slug(" ".join(sorted(c["pw"])[:2])))})
        break
    # 5) richieste di sola analisi -> agente di sola lettura
    sl = [r for r in rich if not any(a.get("tipo") == "modifica" for a in r.get("attivita") or []) and sum(1 for a in r.get("attivita") or [] if a.get("tipo") in ("leggi", "cerca")) >= 5 and ANALISI.search(_dom(r))]
    gia = any(re.search(r"(?i)analist|analyst|review|read-only", f.name) for d in (Path(rad) / ".github" / "agents", Path(rad) / ".claude" / "agents") if d.is_dir() for f in d.glob("*.md"))
    if len(sl) >= MIN_RICHIESTE and not gia:
        cand.append({"id": "cand-agente-analista", "genere": "agente", "tipo_cand": "analista", "peso": len(sl),
                     "titolo": "Un agente di sola lettura per analizzare e rivedere il codice", "ambito": "solo questo progetto",
                     "visto": ["%d richieste erano solo analisi (leggere e cercare, nessuna modifica), l'ultima il %s." % (len(sl), _quando(sl[0]))] + ["«%s»" % _dom(r) for r in sl[:2]],
                     "perche": "Un agente che puo solo leggere non rompe niente, costa meno e risponde sempre nello stesso formato (risposta breve, prove con file:riga, dubbi aperti).",
                     "effetto": "Creo un agente «%s-analista» nel formato giusto per l'agente che scegli. Puo solo leggere e cercare." % _slug(nome), "solo_uno": True})
    cand.sort(key=lambda c: -c["peso"])
    return cand, info


def _scrivi(f, testo):
    if f.exists(): return False
    f.parent.mkdir(parents=True, exist_ok=True); f.write_text(testo, encoding="utf-8"); return True


def _escludi(rad, voce):
    ex = Path(rad) / ".git" / "info" / "exclude"
    try:
        if (Path(rad) / ".git").is_dir() and voce not in (ex.read_text(encoding="utf-8") if ex.exists() else ""):
            with open(ex, "a", encoding="utf-8") as h: h.write("\n" + voce + "\n")
    except Exception: pass


def agente_md(per, nome, desc):
    """Il file agente nel formato di quell'agente. Copilot: .agent.md con alias read/search. Claude: .md con Read, Grep, Glob. Stesso corpo."""
    corpo = ("You are a read-only analyst. Investigate and explain; never change anything.\n\n"
             "- Read and search the code. Do not edit, create or delete files. Do not run commands that change state (installs, builds that write, git commit/push).\n"
             "- Start from .factory/CONTESTO.md if it exists: it is the project map.\n"
             "- Answer in this format: 1) short answer, 2) evidence as `path:line`, 3) open questions or risks.\n")
    if per == "copilot": return "---\nname: %s\ndescription: %s\ntools: ['read', 'search']\n---\n\n%s" % (nome, desc, corpo)
    return "---\nname: %s\ndescription: %s\ntools: Read, Grep, Glob\n---\n\n%s" % (nome, desc, corpo)


def crea(rad, pid, agenti):
    """Crea il file del candidato `pid` (ricalcolato qui: dal browser non arriva mai contenuto). agenti: lista di 'copilot'/'claude'."""
    _C.pop(str(rad), None); cand, _ = analizza(rad); c = next((x for x in cand if x["id"] == pid), None)
    if not c: return {"ok": False, "messaggio": "Questa proposta non c'e piu: la Plancia non vede piu il motivo. Ricarica la pagina."}
    nome = _slug(Path(rad).name); r = Path(rad)
    if c["tipo_cand"] == "comando":
        if not c.get("completi"): return {"ok": False, "messaggio": "I comandi visti sono troppo lunghi per scriverli giusti: usa il testo per la chat."}
        cart = ".claude" if len(agenti) > 1 else CARTELLE[agenti[0]]       # .claude/skills lo leggono sia Claude Code sia Copilot: una copia sola, niente doppioni
        n = "%s-comandi" % nome; f = r / cart / "skills" / n / "SKILL.md"
        righe = ["---", "name: %s" % n, "description: Commands the team runs repeatedly in %s (%s). Use before running build, test or tooling commands in this project." % (r.name, c["chiave"]), "---", "",
                 "# Commands that keep coming back in %s" % r.name, "", "Use them as written. If one fails, report the exact error instead of trying variations.", ""]
        righe += ["- `%s`" % x for x in c["completi"]]
        if not _scrivi(f, "\n".join(righe) + "\n"): return {"ok": False, "messaggio": "Esiste gia %s: non la sovrascrivo." % f.relative_to(r).as_posix()}
        _escludi(r, "%s/skills/%s/" % (cart, n))
        return {"ok": True, "messaggio": "Creata %s (esclusa da git). La leggono %s." % (f.relative_to(r).as_posix(), "sia Claude Code sia Copilot" if cart == ".claude" else ("Copilot" if cart == ".github" else "Claude Code"))}
    if c["tipo_cand"] == "analista":
        per = agenti[0]; n = "%s-analista" % nome
        f = r / (".github/agents/%s.agent.md" % n if per == "copilot" else ".claude/agents/%s.md" % n)
        desc = "Read-only investigator for %s: explains code, finds where things happen and reviews changes without editing anything. Use when the request is to analyze, explain, check or find something." % r.name
        if not _scrivi(f, agente_md(per, n, desc)): return {"ok": False, "messaggio": "Esiste gia %s: non lo sovrascrivo." % f.relative_to(r).as_posix()}
        _escludi(r, f.relative_to(r).as_posix())
        return {"ok": True, "messaggio": "Creato %s nel formato di %s (escluso da git). Riapri la chat per vederlo nell'elenco agenti." % (f.relative_to(r).as_posix(), "Copilot" if per == "copilot" else "Claude Code")}
    return {"ok": False, "messaggio": "Per questa proposta serve il testo per la chat."}

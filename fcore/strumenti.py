"""Cosa usano gli agenti in un progetto: skill, server MCP, hook, istruzioni, plugin. Con avvisi e proposte.
  plancia strumenti                 elenco per il progetto corrente
  plancia strumenti --json          lo stesso in JSON (per il pannello)
  plancia skill-progetto [--scrivi] crea la skill del progetto "come si fanno build e test qui" dai comandi verificati"""
import json, os, re, sys
from pathlib import Path
try: from . import store as lib
except ImportError: import store as lib

TOKEN = lambda testo: max(1, len(testo) // 4)                      # stima grezza: ~4 caratteri per token


def _fm(f):
    """name/description dal frontmatter di uno SKILL.md."""
    try: t = f.read_text(encoding="utf-8", errors="ignore")[:4000]
    except Exception: return {}
    m = re.match(r"^---\s*\n(.*?)\n---", t, re.S); d = {}
    for l in (m.group(1).splitlines() if m else []):
        k, _, v = l.partition(":")
        if k.strip() in ("name", "description"): d[k.strip()] = v.strip().strip("\"'")
    return d


def _json(f):
    try: return json.loads(Path(f).read_text(encoding="utf-8"))
    except Exception: return None


def _vscode_user():
    if os.name == "nt": return Path(os.environ.get("APPDATA", "")) / "Code" / "User"
    return Path.home() / ".config" / "Code" / "User"


def skill(rad):
    h = Path.home(); out = []
    posti = [("progetto", Path(rad) / ".claude" / "skills"), ("progetto", Path(rad) / ".github" / "skills"), ("progetto", Path(rad) / ".agents" / "skills"),
             ("tutti i progetti (Claude)", h / ".claude" / "skills"), ("tutti i progetti (Copilot)", h / ".copilot" / "skills")]
    for p in list((h / ".copilot" / "installed-plugins").glob("*/*/skills")) + list((h / ".copilot" / "installed-plugins").glob("*/skills")) + list((h / ".claude" / "plugins" / "cache").glob("*/*/*/skills")) + _vscode_plugin_dirs("skills"):
        posti.append(("plugin " + p.parent.name, p))
    for dove, d in posti:
        for f in sorted(d.glob("*/SKILL.md")) if d.is_dir() else []:
            m = _fm(f); out.append({"nome": m.get("name") or f.parent.name, "descrizione": (m.get("description") or "")[:240], "dove": dove, "file": str(f)})
    return out



def _fm_agente(f):
    """Frontmatter di un file agente (chiavi semplici ed elenchi, senza dipendenze) + corpo."""
    try: t = f.read_text(encoding="utf-8", errors="ignore")
    except Exception: return {}, ""
    m = re.match(r"^﻿?---\s*\r?\n(.*?)\r?\n---\s*\r?\n?", t, re.S); d = {}; k = None
    for l in (m.group(1).splitlines() if m else []):
        if re.match(r"^\s+-\s+", l) and k: d.setdefault(k, []); d[k] = (d[k] if isinstance(d[k], list) else []) + [l.split("-", 1)[1].strip().strip("\"'")]; continue
        if ":" in l and not l.startswith((" ", "\t")):
            k, _, v = l.partition(":"); k = k.strip().lower(); v = v.strip()
            if v.startswith("[") and v.endswith("]"): d[k] = [x.strip().strip("\"'") for x in v[1:-1].split(",") if x.strip()]
            elif v in ("", "|", ">", ">-", "|-"): d[k] = ""
            else: d[k] = v.strip("\"'")
        elif k and isinstance(d.get(k), str) and l.strip(): d[k] = (d[k] + " " + l.strip()).strip()      # descrizione su piu righe
    return d, (t[m.end():] if m else t)


def agenti(rad):
    """Agenti personalizzati (sotto-agenti di Claude Code, custom agent / chat mode di Copilot): cosa fa ognuno e cosa migliorare. Solo lettura dei file."""
    h = Path.home(); r = Path(rad); out = []
    posti = [("GitHub Copilot", "solo questo progetto", r / ".github" / "agents", "*.md"), ("GitHub Copilot", "solo questo progetto", r / ".github" / "chatmodes", "*.md"),
             ("Claude Code", "solo questo progetto", r / ".claude" / "agents", "*.md"),
             ("GitHub Copilot", "tutti i progetti", h / ".copilot" / "agents", "*.md"), ("Claude Code", "tutti i progetti", h / ".claude" / "agents", "*.md")]
    for per, ambito, d, pat in posti:
        for f in sorted(d.glob(pat)) if d.is_dir() else []:
            if f.name.lower().startswith("readme"): continue
            m, corpo = _fm_agente(f); nome = str(m.get("name") or re.sub(r"\.(agent|chatmode)$", "", f.stem))
            desc = str(m.get("description") or "").strip(); tools = m.get("tools")
            if isinstance(tools, str): tools = [x.strip() for x in tools.split(",") if x.strip()]
            righe = [x.strip() for x in corpo.splitlines() if x.strip()]
            titoli = [re.sub(r"^#+\s*", "", x) for x in righe if x.startswith("#")][:6]
            intro = next((x for x in righe if not x.startswith(("#", "-", "*", "|", "```", "<"))), "")
            tok = TOKEN(corpo); cons = []
            if not desc: cons.append("Manca la descrizione: l'agente principale non sa quando chiamarlo. Aggiungi `description:` con una frase tipo \"Use when ...\".")
            elif len(desc) < 40: cons.append("Descrizione molto corta: scrivi QUANDO va usato (es. \"Use when reviewing a pull request\"), cosi viene scelto al momento giusto.")
            if not tools: cons.append("Puo usare tutti gli strumenti. Se deve solo leggere o analizzare, limita `tools:` (lettura e ricerca): e piu sicuro e sbaglia meno.")
            elif len(tools) > 15: cons.append("Ha %d strumenti: tieni solo quelli che servono al suo compito." % len(tools))
            if tok > 1500: cons.append("Istruzioni lunghe (~%d token, lette ogni volta che parte): sposta i dettagli in una skill e lascia qui ruolo, limiti e formato della risposta." % tok)
            elif tok < 20: cons.append("Istruzioni quasi vuote: scrivi cosa deve fare, cosa NON deve fare e in che formato risponde.")
            if tok >= 20 and not re.search(r"(?i)\b(output|return|report|respond|reply|format|rispond|restitu|riporta|elenca)", corpo): cons.append("Non dice in che formato deve rispondere: aggiungi una riga (es. \"Return: findings as a list with file:line\").")
            out.append({"nome": nome, "per": per, "ambito": ambito, "descrizione": desc[:400], "intro": lib.redigi(intro, 220) if intro and intro != desc else "", "sezioni": titoli,
                        "strumenti": tools or [], "modello": str(m.get("model") or ""), "token": tok, "file": str(f.relative_to(r)).replace("\\", "/") if r in f.parents else str(f).replace(str(h), "~"), "consigli": cons})
    par = lambda a: set(re.findall(r"[a-z]{4,}", (a["nome"] + " " + a["descrizione"]).lower()))
    for i, a in enumerate(out):                                          # doppioni e sovrapposizioni
        for b in out[i + 1:]:
            if a["per"] != b["per"]: continue
            pa, pb = par(a), par(b)
            if a["nome"].lower() == b["nome"].lower(): a["consigli"].append("Stesso nome di %s: l'agente non sa quale scegliere, tienine uno." % b["file"]); b["consigli"].append("Stesso nome di %s: tienine uno." % a["file"])
            elif len(pa) > 5 and len(pb) > 5 and len(pa & pb) / float(len(pa | pb)) > 0.6: a["consigli"].append("Fa quasi la stessa cosa di “%s”: valuta di unirli." % b["nome"]); b["consigli"].append("Fa quasi la stessa cosa di “%s”: valuta di unirli." % a["nome"])
    return out


def mcp(rad):
    out = []
    def add(dove, d, chiave):
        for n, c in ((d or {}).get(chiave) or {}).items():
            cmd = " ".join([str(c.get("command") or c.get("url") or "")] + [str(x) for x in (c.get("args") or [])][:3])
            out.append({"nome": n, "dove": dove, "comando": lib.redigi(cmd, 120), "tipo": c.get("type") or ("http" if c.get("url") else "stdio")})
    add("progetto · VS Code (.vscode/mcp.json)", _json(Path(rad) / ".vscode" / "mcp.json"), "servers")
    add("progetto · Claude Code (.mcp.json)", _json(Path(rad) / ".mcp.json"), "mcpServers")
    add("tutti i progetti · VS Code", _json(_vscode_user() / "mcp.json"), "servers")
    add("tutti i progetti · Copilot CLI", _json(Path.home() / ".copilot" / "mcp-config.json"), "mcpServers")
    cj = _json(Path.home() / ".claude.json") or {}
    add("tutti i progetti · Claude Code", cj, "mcpServers")
    for k, v in (cj.get("projects") or {}).items():
        if os.path.normcase(os.path.abspath(k)) == os.path.normcase(os.path.abspath(str(rad))): add("progetto · Claude Code (locale)", v, "mcpServers")
    return out


def hook(rad):
    out = []
    s = _json(Path(rad) / ".claude" / "settings.json") or {}
    for ev, lst in (s.get("hooks") or {}).items():
        for g in lst or []:
            for h in g.get("hooks") or []:
                c = str(h.get("command") or ""); out.append({"evento": ev, "dove": ".claude/settings.json", "nostro": " hook" in c and ("factory" in c or "plancia" in c or "lavagna" in c), "comando": lib.redigi(c, 100)})
    for f in sorted((Path(rad) / ".github" / "hooks").glob("*.json")):
        d = _json(f) or {}
        for ev, lst in (d.get("hooks") or {}).items():
            for h in lst or []:
                c = str(h.get("bash") or h.get("powershell") or h.get("command") or ""); out.append({"evento": ev, "dove": ".github/hooks/" + f.name, "nostro": "plancia" in f.name or " hook" in c and "factory" in c, "comando": lib.redigi(c, 100)})
    return out


def istruzioni(rad):
    out = []; r = Path(rad)
    cand = [r / "AGENTS.md", r / "CLAUDE.md", r / ".github" / "copilot-instructions.md", Path.home() / ".claude" / "CLAUDE.md", Path.home() / ".copilot" / "copilot-instructions.md"] + sorted((r / ".github" / "instructions").glob("*.instructions.md"))
    for f in cand:
        if f.is_file():
            t = f.read_text(encoding="utf-8", errors="ignore")
            out.append({"file": str(f.relative_to(r)) if r in f.parents else str(f), "token": TOKEN(t), "righe": t.count("\n") + 1, "sempre": "instructions" not in f.parent.name})
    return out


def _vscode_plugin_dirs(sotto=None):
    """Plugin installati dalla chat di VS Code (Chat: Install Plugin from Source): ~/.vscode/agent-plugins/<host>/<owner>/<repo>."""
    base = Path.home() / ".vscode" / "agent-plugins"
    out = [d for d in base.glob("*/*/*") if d.is_dir()] if base.is_dir() else []
    return [d / sotto for d in out if (d / sotto).is_dir()] if sotto else out


def plugin():
    out = []; h = Path.home()
    for d in _vscode_plugin_dirs():
        m = _json(d / ".github" / "plugin" / "plugin.json") or _json(d / ".claude-plugin" / "plugin.json") or _json(d / "plugin.json") or {}
        out.append({"nome": m.get("name") or d.name, "versione": m.get("version"), "dove": "chat di VS Code"})
    for p in sorted((h / ".copilot" / "installed-plugins").glob("*/*")) + sorted((h / ".copilot" / "installed-plugins").glob("*")):
        m = _json(p / "plugin.json") or _json(p / ".claude-plugin" / "plugin.json") or _json(p / ".github" / "plugin" / "plugin.json")
        if m and m.get("name") not in [x["nome"] for x in out]: out.append({"nome": m.get("name"), "versione": m.get("version"), "dove": "Copilot CLI / VS Code"})
    ip = _json(h / ".claude" / "plugins" / "installed_plugins.json") or {}
    for k in (ip.get("plugins") or {}): out.append({"nome": k, "versione": None, "dove": "Claude Code"})
    return out


def _ambito(dove):
    return "tutti i progetti" if dove.startswith("tutti") else ("solo questo progetto" if dove == "progetto" else "tutti i progetti (" + dove + ")")


def _rifiutate(rad):
    try: return set(json.loads((Path(rad) / ".factory" / "proposte.json").read_text(encoding="utf-8")).get("rifiutate") or [])
    except Exception: return set()


def _comandi_build(rad):
    ctx = Path(rad) / ".factory" / "CONTESTO.md"
    t = ctx.read_text(encoding="utf-8", errors="ignore") if ctx.exists() else ""
    return [(k.strip(), v) for k, v in re.findall(r"(?m)^- ([^`]+?): `([^`]+)`", t) if re.search(r"\b(build|test)\b", k)], t


def proposte(rad, sk, ist, mc, tutte=False, ag=()):
    """Suggerimenti in parole semplici. Ognuno ha: id stabile, titolo, perche, ambito (tutti i progetti / solo questo) e un'azione:
    'crea' = la Plancia lo fa da sola con un clic; 'prompt' = testo pronto da incollare in chat; 'info' = solo da sapere."""
    p = []; r = Path(rad); nomi = [s["nome"] for s in sk]; nome_p = r.name
    if "plancia-metodo" not in nomi:
        p.append({"id": "skill-metodo", "scegli_agente": True, "titolo": "Insegna all'agente il metodo della Plancia", "ambito": "tutti i progetti",
                  "perche": "Senza, l'agente decide da solo come lavorare: a volte non scrive il piano, fa giri a vuoto o dichiara finito senza provare.",
                  "azione": {"tipo": "crea", "testo": "Installa la skill plancia-metodo per tutti i tuoi progetti."}})
    doppie = sorted({n for n in nomi if nomi.count(n) > 1})
    for n in doppie:
        dov = [s["file"] for s in sk if s["nome"] == n]
        if n == "plancia-metodo" and any(s["dove"].startswith("plugin") for s in sk if s["nome"] == n):
            p.append({"id": "doppia-plancia-metodo", "titolo": "Le istruzioni della Plancia per l'agente ci sono due volte", "ambito": "tutti i progetti",
                      "perche": "La Plancia e una sola. Sono doppie solo le sue istruzioni per l'agente (la skill plancia-metodo): una arriva col plugin e si aggiorna da sola, l'altra e una copia vecchia rimasta in %s da prima del plugin. L'agente potrebbe seguire quella vecchia: conviene toglierla." % ", ".join(sorted({s["file"].replace(str(Path.home()), "~").rsplit("plancia-metodo", 1)[0] for s in sk if s["nome"] == "plancia-metodo" and not s["dove"].startswith("plugin")})),
                      "azione": {"tipo": "crea", "testo": "Tengo quella del plugin e tolgo le copie installate a mano."}})
            continue
        p.append({"id": "doppia-" + _slug(n), "titolo": "La skill \u201c%s\u201d c'e due volte" % n, "ambito": "tutti i progetti",
                  "perche": "Con due copie l'agente non sa quale usare e puo seguire quella vecchia.",
                  "azione": {"tipo": "info", "testo": "Tieni una sola copia e cancella l'altra cartella:\n" + "\n".join(dov)}})
    tot = sum(x["token"] for x in ist if x["sempre"])
    if tot > 3000:
        p.append({"id": "istruzioni-lunghe", "titolo": "Le istruzioni fisse costano ~%d token a ogni domanda" % tot, "ambito": "solo questo progetto",
                  "perche": "Le istruzioni fisse (AGENTS.md, CLAUDE.md, copilot-instructions) si pagano anche per la domanda piu semplice. Le skill invece si leggono solo quando servono.",
                  "azione": {"tipo": "prompt", "testo": "Read %s. Keep in them only the rules that apply to EVERY request (max ~40 lines). Move each specific topic (how to test, how to deploy, conventions of one module) into its own project skill under <skills dir>/<topic>/SKILL.md (<skills dir> = .github/skills if you are GitHub Copilot, .claude/skills if you are Claude Code) with a one-line description of when to use it. Do not lose any rule. Show me the diff before saving." % ", ".join(x["file"] for x in ist if x["sempre"])}})
    if len(mc) > 6:
        p.append({"id": "mcp-troppi", "titolo": "%d server MCP accesi" % len(mc), "ambito": "solo questo progetto",
                  "perche": "Ogni server MCP aggiunge la descrizione dei suoi strumenti a ogni domanda: piu sono, piu consumi e piu l'agente si confonde.",
                  "azione": {"tipo": "info", "testo": "Spegni quelli che non usi in questo progetto (in VS Code: icona strumenti nella chat, oppure .vscode/mcp.json)."}})
    cm, ctx = _comandi_build(rad)
    if cm and not any(s["nome"].endswith("-build-test") for s in sk if s["dove"] == "progetto"):
        p.append({"id": "skill-build-test", "scegli_agente": True, "titolo": "Comandi di build e test sempre pronti", "ambito": "solo questo progetto",
                  "perche": "L'agente usa subito i comandi giusti (anche Maven o JDK fuori dal PATH) invece di cercarli a ogni richiesta. La Plancia li conosce gia: " + "; ".join("%s = %s" % (k, v) for k, v in cm[:3]) + ("…" if len(cm) > 3 else ""),
                  "azione": {"tipo": "crea", "testo": "Crea la skill del progetto con questi comandi (resta sul tuo PC: esclusa da git)."}})
    java = "Java" in ctx
    test_java = [s for s in sk if re.search(r"junit|java test|spring", (s["nome"] + " " + s["descrizione"]).lower())]
    if java and not test_java:
        dirs = re.findall(r"(?m)^- `([^`]*src/test[^`]*)`", ctx)[:3]
        p.append({"id": "skill-test-java", "titolo": "Come si scrivono i test in questo progetto Java", "ambito": "solo questo progetto",
                  "perche": "Quando chiedi di aggiungere o sistemare test, l'agente copia lo stile giusto (librerie, mock, nomi) invece di inventarlo.",
                  "azione": {"tipo": "prompt", "testo": "Create a project skill at <skills dir>/%s-java-tests/SKILL.md, where <skills dir> is .github/skills if you are GitHub Copilot or .claude/skills if you are Claude Code (then add that folder to .git/info/exclude). Look at 2-3 existing tests%s and write in max 40 lines: test framework and versions, how mocks/fixtures are done, naming, where new tests go, the exact command to run one test class and the whole suite (see .factory/CONTESTO.md). Only facts you saw in the code. Plan first." % (_slug(nome_p), " in " + ", ".join(dirs) if dirs else "")}})
    ang = (r / "angular.json").exists() or any(r.glob("*/angular.json"))
    if ang and not any("angular" in (s["nome"] + s["descrizione"]).lower() for s in sk):
        p.append({"id": "skill-angular", "titolo": "Come si costruisce e si prova il frontend Angular", "ambito": "solo questo progetto",
                  "perche": "Evita che l'agente provi comandi npm a caso o rompa la configurazione dei test.",
                  "azione": {"tipo": "prompt", "testo": "Create a project skill at <skills dir>/%s-angular/SKILL.md, where <skills dir> is .github/skills if you are GitHub Copilot or .claude/skills if you are Claude Code (then add that folder to .git/info/exclude). Read package.json, angular.json and the test config (karma/jest) and write in max 40 lines: how to install, build, serve and test, which test runner and how specs are written here, known pitfalls. Only facts you saw. Plan first." % _slug(nome_p)}})
    clas = (r / ".github" / "hooks" / "plancia.json").exists() or (r / ".github" / "hooks" / "lavagna.json").exists() or "plancia:inizio" in _leggi(r / "AGENTS.md") or "lavagna:inizio" in _leggi(r / "AGENTS.md")
    if clas and any(s["dove"].startswith("plugin") for s in sk):
        p.append({"id": "passa-al-plugin", "titolo": "Questo progetto ha ancora la vecchia installazione", "ambito": "solo questo progetto",
                  "perche": "Hook, regola e strumenti scritti dentro il progetto (AGENTS.md, .github/hooks, .claude/settings.json, .vscode/mcp.json) dalla versione classica o dalla vecchia Lavagna. Col plugin non servono piu e possono puntare a programmi che non esistono, cosi la Plancia non vede niente.",
                  "azione": {"tipo": "crea", "testo": "Tolgo dal progetto solo le parti della Plancia/Lavagna: il resto dei file resta com'e."}})
    if ag:
        p.append({"id": "agenti-revisione", "titolo": "Fai rivedere i tuoi %d agenti all'AI" % len(ag), "ambito": "solo questo progetto",
                  "perche": "Qui sopra vedi i controlli automatici (gratis). Per un giudizio vero su ruoli, sovrapposizioni e istruzioni serve che l'agente li legga: costa qualche migliaio di token, una volta.",
                  "azione": {"tipo": "prompt", "testo": "Review my custom agents: %s. For each one: what it does in one line, when it should be used, what overlaps with the others, missing limits (tools, what it must NOT do, output format), and max 3 concrete improvements with the exact text to add or remove. Then tell me if any agent is useless or missing for this project. Do not edit files: report only." % ", ".join(a["file"] for a in ag[:12])}})
    rif = _rifiutate(rad)
    for x in p: x["rifiutata"] = x["id"] in rif
    return p if tutte else [x for x in p if not x["rifiutata"]]


def _leggi(f):
    try: return Path(f).read_text(encoding="utf-8", errors="ignore")
    except Exception: return ""


def _slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:30] or "progetto"


def azione_proposta(rad, pid, azione, agente=""):
    """Dal pannello: rifiuta / ripristina una proposta, oppure 'crea' (solo per quelle che la Plancia sa fare da sola)."""
    rad = Path(rad); f = rad / ".factory" / "proposte.json"
    try: d = json.loads(f.read_text(encoding="utf-8"))
    except Exception: d = {}
    rif = set(d.get("rifiutate") or [])
    if azione == "rifiuta": rif.add(pid)
    elif azione == "ripristina": rif.discard(pid)
    elif azione == "crea" and pid == "skill-build-test":
        ag = _agenti(agente)
        if not ag: return {"ok": False, "messaggio": "scegli prima per quale agente"}
        os.environ["FACTORY_ROOT"] = str(rad)
        import contextlib, io
        for a in ag:
            with contextlib.redirect_stdout(io.StringIO()): rc = skill_progetto(True, CARTELLE[a])
            if rc: return {"ok": False, "messaggio": "non sono riuscito a creare la skill"}
            _escludi_da_git(rad, "%s/skills/%s-build-test/" % (CARTELLE[a], _slug2(rad.name)))
        return {"ok": True, "messaggio": "Skill creata in " + " e ".join("%s/skills" % CARTELLE[a] for a in ag) + " (esclusa da git): da adesso l'agente usa questi comandi."}
    elif azione == "crea" and pid == "doppia-plancia-metodo":
        import shutil
        for d in (Path.home() / ".claude" / "skills" / "plancia-metodo", Path.home() / ".copilot" / "skills" / "plancia-metodo"):
            if (d / "SKILL.md").exists(): shutil.rmtree(d, ignore_errors=True)
        return {"ok": True, "messaggio": "Fatto: resta solo il metodo del plugin."}
    elif azione == "crea" and pid == "passa-al-plugin":
        import importlib.util
        spec = importlib.util.spec_from_file_location("factory_main", str(Path(__file__).resolve().parent.parent / "factory.py"))
        fm = importlib.util.module_from_spec(spec); spec.loader.exec_module(fm)
        out = []; fm.scollega(rad, True, out)
        return {"ok": True, "messaggio": "Fatto: " + "; ".join(out[:4]) + ". Riapri la chat: da adesso ci pensa il plugin."}
    elif azione == "crea" and pid == "skill-metodo":
        ag = _agenti(agente)
        if not ag: return {"ok": False, "messaggio": "scegli prima per quale agente"}
        from fcore import metodo
        metodo.installa(globale=True, scrivi=True, agenti=ag)
        return {"ok": True, "messaggio": "Metodo installato per tutti i tuoi progetti (" + " e ".join("~/.%s/skills" % ("copilot" if a == "copilot" else "claude") for a in ag) + ")."}
    else: return {"ok": False, "messaggio": "azione non valida"}
    d["rifiutate"] = sorted(rif); f.write_text(json.dumps(d, indent=1), encoding="utf-8")
    return {"ok": True}


CARTELLE = {"copilot": ".github", "claude": ".claude"}                    # stesso formato SKILL.md (standard Agent Skills): cambia solo la cartella


def _agenti(scelta):
    return ["copilot", "claude"] if scelta == "entrambi" else ([scelta] if scelta in CARTELLE else [])


def _slug2(n): return re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")[:40]


def _escludi_da_git(rad, voce):
    ex = Path(rad) / ".git" / "info" / "exclude"
    try:
        if (Path(rad) / ".git").is_dir() and voce not in (ex.read_text(encoding="utf-8") if ex.exists() else ""):
            with open(ex, "a", encoding="utf-8") as h: h.write("\n" + voce + "\n")
    except Exception: pass


def tutto(rad=None):
    rad = str(rad or lib.radice()); sk, mc, ist = skill(rad), mcp(rad), istruzioni(rad)
    for s in sk: s["ambito"] = _ambito(s["dove"])
    ag = agenti(rad); pr = proposte(rad, sk, ist, mc, tutte=True, ag=[a for a in ag if a["ambito"].startswith("solo")])
    mp = None
    try:
        import time
        fm = Path(rad) / ".factory" / "CONTESTO.md"
        if fm.exists():
            tx = fm.read_text(encoding="utf-8", errors="ignore"); mp = {"token": TOKEN(tx), "righe": tx.count("\n") + 1, "giorni": int((time.time() - fm.stat().st_mtime) // 86400), "titoli": [x[3:].strip() for x in tx.splitlines() if x.startswith("## ")][:8]}
    except Exception: pass
    return {"progetto": rad, "mappa": mp, "agenti": ag, "skill": sk, "mcp": mc, "hook": hook(rad), "istruzioni": ist, "plugin": plugin(),
            "proposte": [x for x in pr if not x["rifiutata"]], "rifiutate": [x for x in pr if x["rifiutata"]]}


def skill_progetto(scrivi=False, cartella=".github"):
    """Skill del progetto con i comandi di build/test della mappa (deterministica, senza LLM)."""
    rad = lib.radice(); ctx = rad / ".factory" / "CONTESTO.md"
    if not ctx.exists(): print("Manca .factory/CONTESTO.md: prima " + lib.comando() + " contesto --scrivi"); return 2
    cm = re.findall(r"(?m)^- ([^`]+?): `([^`]+)`", ctx.read_text(encoding="utf-8", errors="ignore"))
    cm = [(k, v) for k, v in cm if re.search(r"\b(build|test|avvio|start|dipendenze|python)\b", k)]
    if not cm: print("Nessun comando di build/test nella mappa."); return 2
    nome = re.sub(r"[^a-z0-9]+", "-", rad.name.lower()).strip("-")[:40] + "-build-test"
    righe = ["---", "name: %s" % nome, "description: Exact build, test and run commands for %s (verified paths, including tools outside PATH). Use before running any build or test in this project." % rad.name, "---", "",
             "# Build and test in %s" % rad.name, "", "Use these commands as they are; do not search for Maven/JDK/npm again. If one fails, report the exact error.", ""]
    righe += ["- %s: `%s`" % (k.strip(), v) for k, v in cm]
    righe += ["", "Run the narrowest test first (one class), the full suite only at the end. Filter long output for FAIL/ERROR/summary lines."]
    f = rad / cartella / "skills" / nome / "SKILL.md"
    if not scrivi: print("Scriverei %s:\n\n%s\n\n(aggiungi --scrivi)" % (f, "\n".join(righe))); return 0
    f.parent.mkdir(parents=True, exist_ok=True); f.write_text("\n".join(righe) + "\n", encoding="utf-8")
    print("Scritta la skill %s. Se i comandi cambiano: rigenera con lo stesso comando." % f); return 0


def main(a):
    if a and a[0] == "skill-progetto": return skill_progetto("--scrivi" in a, ".claude" if "--claude" in a else ".github")
    d = tutto()
    if "--json" in a: print(json.dumps(d, ensure_ascii=False, indent=1)); return 0
    print("Skill:"); [print("  %-28s %s" % (s["nome"], s["dove"])) for s in d["skill"]]
    print("Server MCP:"); [print("  %-28s %s" % (m["nome"], m["dove"])) for m in d["mcp"]]
    print("Hook: %d (%d della Plancia)" % (len(d["hook"]), sum(h["nostro"] for h in d["hook"])))
    print("Istruzioni:"); [print("  %-40s ~%d token%s" % (i["file"], i["token"], "" if i["sempre"] else " (solo quando servono)")) for i in d["istruzioni"]]
    if d["proposte"]: print("Proposte:"); [print("  - [%s] %s (%s)\n    %s\n    -> %s" % (p["id"], p["titolo"], p["ambito"], p["perche"], p["azione"]["testo"])) for p in d["proposte"]]
    return 0


if __name__ == "__main__": sys.exit(main(sys.argv[1:]))

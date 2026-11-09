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
    for p in list((h / ".copilot" / "installed-plugins").glob("*/*/skills")) + list((h / ".copilot" / "installed-plugins").glob("*/skills")) + list((h / ".claude" / "plugins" / "cache").glob("*/*/*/skills")):
        posti.append(("plugin " + p.parent.name, p))
    for dove, d in posti:
        for f in sorted(d.glob("*/SKILL.md")) if d.is_dir() else []:
            m = _fm(f); out.append({"nome": m.get("name") or f.parent.name, "descrizione": (m.get("description") or "")[:240], "dove": dove, "file": str(f)})
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


def plugin():
    out = []; h = Path.home()
    for p in sorted((h / ".copilot" / "installed-plugins").glob("*/*")) + sorted((h / ".copilot" / "installed-plugins").glob("*")):
        m = _json(p / "plugin.json") or _json(p / ".claude-plugin" / "plugin.json") or _json(p / ".github" / "plugin" / "plugin.json")
        if m and m.get("name") not in [x["nome"] for x in out]: out.append({"nome": m.get("name"), "versione": m.get("version"), "dove": "Copilot CLI / VS Code"})
    ip = _json(h / ".claude" / "plugins" / "installed_plugins.json") or {}
    for k in (ip.get("plugins") or {}): out.append({"nome": k, "versione": None, "dove": "Claude Code"})
    return out


def proposte(rad, sk, ist, mc):
    """Suggerimenti concreti e brevi. Ognuno dice perche e come."""
    p = []; r = Path(rad); nomi = [s["nome"] for s in sk]
    if "plancia-metodo" not in nomi: p.append({"cosa": "Manca la skill plancia-metodo", "perche": "senza, l'agente pianifica e verifica a modo suo", "come": lib.comando() + " metodo --globale --scrivi"})
    doppie = sorted({n for n in nomi if nomi.count(n) > 1})
    if doppie: p.append({"cosa": "Skill doppie: " + ", ".join(doppie), "perche": "due copie con lo stesso nome confondono l'agente", "come": "tieni una sola copia (vedi la colonna 'dove')"})
    tot = sum(x["token"] for x in ist if x["sempre"])
    if tot > 3000: p.append({"cosa": "Istruzioni lunghe: ~%d token letti a ogni sessione" % tot, "perche": "si pagano a ogni domanda, anche la piu semplice", "come": "sposta le parti specifiche in skill (si caricano solo quando servono)"})
    if len(mc) > 6: p.append({"cosa": "%d server MCP attivi" % len(mc), "perche": "ogni server aggiunge la descrizione dei suoi strumenti al contesto", "come": "spegni quelli che non usi in questo progetto"})
    ctx = r / ".factory" / "CONTESTO.md"
    if ctx.exists() and not any(s["dove"] == "progetto" and s["nome"].endswith("-build-test") for s in sk):
        if re.search(r"(?m)^- [^`]*\b(build|test)\b[^`]*: `", ctx.read_text(encoding="utf-8", errors="ignore")):
            p.append({"cosa": "Skill del progetto per build e test", "perche": "l'agente usa subito i comandi giusti (anche Maven/JDK fuori dal PATH) invece di cercarli a ogni richiesta", "come": lib.comando() + " skill-progetto --scrivi"})
    st = (ctx.read_text(encoding="utf-8", errors="ignore") if ctx.exists() else "")
    if "Java" in st and not any("junit" in (s["nome"] + s["descrizione"]).lower() or "spring" in (s["nome"] + s["descrizione"]).lower() for s in sk):
        p.append({"cosa": "Progetto Java senza skill per i test", "perche": "le prove con modifiche (9, 10) vanno meglio se l'agente sa come scrivere test JUnit qui", "come": "dopo la skill build-test, chiedi alla chat: \"write a project skill on how tests are written in this repo (look at 2 existing tests)\""})
    ang = (r / "angular.json").exists() or any(r.glob("*/angular.json"))
    if ang and not any("angular" in (s["nome"] + s["descrizione"]).lower() for s in sk):
            p.append({"cosa": "Progetto Angular senza skill dedicata", "perche": "evita che l'agente provi comandi npm a caso", "come": "chiedi alla chat: \"write a project skill on how to build and test the Angular app here (check package.json and karma/jest config)\""})
    return p


def tutto(rad=None):
    rad = str(rad or lib.radice()); sk, mc, ist = skill(rad), mcp(rad), istruzioni(rad)
    return {"progetto": rad, "skill": sk, "mcp": mc, "hook": hook(rad), "istruzioni": ist, "plugin": plugin(), "proposte": proposte(rad, sk, ist, mc)}


def skill_progetto(scrivi=False):
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
    f = rad / ".claude" / "skills" / nome / "SKILL.md"
    if not scrivi: print("Scriverei %s:\n\n%s\n\n(aggiungi --scrivi)" % (f, "\n".join(righe))); return 0
    f.parent.mkdir(parents=True, exist_ok=True); f.write_text("\n".join(righe) + "\n", encoding="utf-8")
    print("Scritta la skill %s (letta da Claude Code, Copilot CLI e chat di VS Code). Se i comandi cambiano: rigenera con lo stesso comando." % f); return 0


def main(a):
    if a and a[0] == "skill-progetto": return skill_progetto("--scrivi" in a)
    d = tutto()
    if "--json" in a: print(json.dumps(d, ensure_ascii=False, indent=1)); return 0
    print("Skill:"); [print("  %-28s %s" % (s["nome"], s["dove"])) for s in d["skill"]]
    print("Server MCP:"); [print("  %-28s %s" % (m["nome"], m["dove"])) for m in d["mcp"]]
    print("Hook: %d (%d della Plancia)" % (len(d["hook"]), sum(h["nostro"] for h in d["hook"])))
    print("Istruzioni:"); [print("  %-40s ~%d token%s" % (i["file"], i["token"], "" if i["sempre"] else " (solo quando servono)")) for i in d["istruzioni"]]
    if d["proposte"]: print("Proposte:"); [print("  - %s: %s -> %s" % (p["cosa"], p["perche"], p["come"])) for p in d["proposte"]]
    return 0


if __name__ == "__main__": sys.exit(main(sys.argv[1:]))

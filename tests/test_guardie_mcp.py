"""Test di guardie (policy + hook PreToolUse), init --tutto e server MCP, in una cartella temporanea."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; F = str(ROOT / "factory.py")
ok = ko = 0
def v(nome, cond, det=""):
    global ok, ko
    if cond: ok += 1; print("  ok  " + nome)
    else: ko += 1; print("  KO  %s %s" % (nome, str(det)[:300]))
d = Path(tempfile.mkdtemp()); env = {k: x for k, x in os.environ.items() if k not in ("FACTORY_ROOT", "FACTORY_PIANO")}; env["PLANCIA_HOME"] = str(d / "_casa")
def run(*a, stdin=None): return subprocess.run([sys.executable, F, *a], capture_output=True, text=True, cwd=d, env=env, input=stdin)

x = run("init", "--modo", "governata", "--tutto", "--scrivi"); v("init --tutto: policy, MCP VS Code e Claude, hook", (d / ".factory/policy.json").exists() and "plancia" in json.loads((d / ".vscode/mcp.json").read_text())["servers"] and "plancia" in json.loads((d / ".mcp.json").read_text())["mcpServers"], x.stdout + x.stderr)
run("init", "--modo", "governata", "--tutto", "--scrivi"); h = json.loads((d / ".claude/settings.json").read_text())["hooks"]
v("init ripetuto: un solo hook per evento, PreToolUse presente", all(len(h[e]) == 1 for e in h) and "PreToolUse" in h)
v("AGENTS.md: una sola regola", (d / "AGENTS.md").read_text().count("plancia:inizio") == 1)

x = run("policy", "verifica", "--file", ".env"); v("policy: .env negato", x.returncode == 3 and "protetto" in x.stdout)
x = run("policy", "verifica", "--file", "src/app.py"); v("policy: file normale ammesso", x.returncode == 0)
x = run("policy", "verifica", "--comando", "rm -rf /"); v("policy: rm -rf / negato", x.returncode == 3)
x = run("policy", "verifica", "--comando", "psql -c 'DROP TABLE ordini'"); v("policy: DROP TABLE negato", x.returncode == 3)
x = run("policy", "verifica", "--comando", "echo x > config/.env"); v("policy: redirezione su .env negata", x.returncode == 3)
x = run("policy", "verifica", "--comando", "pytest -q"); v("policy: pytest ammesso", x.returncode == 0)

def hook_claude(tool, inp): return run("hook", "PreToolUse", stdin=json.dumps({"hook_event_name": "PreToolUse", "cwd": str(d), "tool_name": tool, "tool_input": inp}))
x = hook_claude("Edit", {"file_path": str(d / ".env"), "old_string": "a", "new_string": "b"}); o = json.loads(x.stdout or "{}")
v("hook Claude: Edit su .env negato con motivo", o.get("hookSpecificOutput", {}).get("permissionDecision") == "deny", x.stdout)
x = hook_claude("Write", {"file_path": str(d / "src/main.py"), "content": "x"}); v("hook Claude: Write su file normale ammesso (silenzio)", x.returncode == 0 and not x.stdout)
x = hook_claude("Bash", {"command": "git push --force origin main"}); v("hook Claude: git push --force negato", '"deny"' in x.stdout)
x = run("hook", "preToolUse", stdin=json.dumps({"cwd": str(d), "toolName": "bash", "toolArgs": json.dumps({"command": "rm -rf ~"})}))
v("hook Copilot: rm -rf ~ negato (formato Copilot)", json.loads(x.stdout or "{}").get("permissionDecision") == "deny", x.stdout)
x = run("hook", "preToolUse", stdin=json.dumps({"cwd": str(d), "toolName": "edit", "toolArgs": json.dumps({"path": "secrets/db.yaml"})}))
v("hook Copilot: edit su secrets/ negato", '"deny"' in x.stdout)
x = hook_claude("editFiles", {"files": [str(d / ".env")]}); v("hook VS Code: editFiles su .env negato", '"deny"' in x.stdout)
x = hook_claude("runInTerminal", {"command": "rm -rf /"}); v("hook VS Code: runInTerminal rm -rf / negato", '"deny"' in x.stdout)
n0 = len((d / ".factory/eventi.jsonl").read_text().splitlines())
for _ in range(2): run("hook", "PostToolUse", stdin=json.dumps({"hook_event_name": "PostToolUse", "cwd": str(d), "tool_name": "Read"}))
v("hook doppio (VS Code legge .claude e .github): un solo evento", len((d / ".factory/eventi.jsonl").read_text().splitlines()) == n0 + 1)
v("negazione registrata negli eventi", "guardia_negata" in (d / ".factory/eventi.jsonl").read_text())
(d / ".factory/policy.json").write_text(json.dumps({"sola_lettura": True}))
x = hook_claude("Write", {"file_path": str(d / "src/main.py")}); v("sola lettura: Write negato", '"deny"' in x.stdout)
x = hook_claude("Bash", {"command": "git status"}); v("sola lettura: git status ammesso", not x.stdout)
x = hook_claude("Bash", {"command": "pip install requests"}); v("sola lettura: pip install negato", '"deny"' in x.stdout)
(d / ".factory/policy.json").write_text("{rotto"); x = hook_claude("Edit", {"file_path": str(d / ".env")})
v("policy.json rotto: i default restano attivi", '"deny"' in x.stdout)
(d / ".factory/policy.json").write_text("{}")

msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "plancia_task", "arguments": {"azione": "apri", "id": "M1", "titolo": "prova mcp", "passi": [{"id": "A", "testo": "leggere"}, {"id": "B", "testo": "scrivere", "dipende_da": ["A"]}]}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "plancia_passo", "arguments": {"id": "A", "stato": "fatto", "frase": "letto", "evidenza": "README.md"}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "plancia_stato", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "plancia_verifica_policy", "arguments": {"file": ".env"}}},
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "plancia_task", "arguments": {"azione": "conferma", "id": "M1"}}},
        {"jsonrpc": "2.0", "id": 8, "method": "metodo/ignoto"}]
x = run("mcp", stdin="\n".join(json.dumps(m) for m in msgs) + "\n"); R = {r.get("id"): r for r in (json.loads(l) for l in x.stdout.splitlines() if l.strip())}
v("mcp initialize: nome e versione protocollo", R.get(1, {}).get("result", {}).get("serverInfo", {}).get("name") == "plancia" and R[1]["result"]["protocolVersion"] == "2025-06-18", x.stdout[:300] + x.stderr)
nomi = [t["name"] for t in R.get(2, {}).get("result", {}).get("tools", [])]
v("mcp tools/list: 8 strumenti con nomi unici, nessun 'verifica' per l'agente", len(nomi) == 8 and len(set(nomi)) == 8 and not any("verific" in n and "policy" not in n for n in nomi), nomi)
v("mcp: notifica senza risposta", None not in R)
t = lambda i: R.get(i, {}).get("result", {}).get("content", [{}])[0].get("text", "")
v("mcp task apri con passi: DRAFT", "DRAFT" in t(3) and not R[3]["result"]["isError"], t(3))
v("mcp passo fatto", not R[4]["result"]["isError"] and json.loads((d / ".factory/task/M1/piano.json").read_text())["steps"][0]["stato"] == "FATTO")
v("mcp stato: task e piano", "M1" in t(5) and "1/2" in t(5), t(5))
v("mcp verifica_policy .env: NEGATO ed errore", "NEGATO" in t(6) and R[6]["result"]["isError"])
v("mcp conferma senza frase: rifiutata", R[7]["result"]["isError"])
v("mcp metodo ignoto: errore -32601", R.get(8, {}).get("error", {}).get("code") == -32601)

x = run("task", "apri", "AN1", "solo analisi", "--analisi"); v("task --analisi: aperto senza chiedere conferma", x.returncode == 0 and "sola analisi" in x.stdout, x.stdout)
x = hook_claude("Write", {"file_path": str(d / "src/main.py"), "content": "x"}); v("analisi: scrittura su file del progetto negata", '"deny"' in x.stdout and "analisi" in x.stdout, x.stdout)
x = hook_claude("Write", {"file_path": str(d / ".factory/ESITO.md"), "content": "x"}); v("analisi: scrittura in .factory/ ammessa", not x.stdout, x.stdout)
x = run("task", "eseguito", "AN1"); v("analisi: chiusura rifiutata con passi aperti", x.returncode == 2)
for s in ("capire", "fare", "controllare"): run("piano", "passo", s, "fatto")
x = run("task", "eseguito", "AN1"); v("analisi: chiusura senza conferma", x.returncode == 0 and "ESEGUITO" in x.stdout, x.stdout)
x = hook_claude("Write", {"file_path": str(d / "src/main.py"), "content": "x"}); v("dopo la chiusura dell'analisi: scrittura di nuovo ammessa", not x.stdout, x.stdout)
x = run("task", "apri", "MOD1", "modifica"); x = run("task", "avvia", "MOD1"); v("task normale: avvia senza conferma ancora rifiutato", x.returncode == 2)

x = subprocess.run([sys.executable, F, "mcp"], input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n", capture_output=True, text=True, cwd=d, env=dict(env, PLANCIA_MCP="piano"))
v("mcp PLANCIA_MCP=piano: solo i 3 strumenti del piano", [t_["name"] for t_ in json.loads(x.stdout)["result"]["tools"]] == ["plancia_piano_nuovo", "plancia_passo", "plancia_piano_aggiungi"], x.stdout[:200])
m2 = [{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "plancia_piano_nuovo", "arguments": {"nuovo": True, "titolo": "Endpoint", "passi": ["A: leggere", "B: modificare <- A"]}}},
      {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "plancia_passo", "arguments": {"id": "A", "stato": "fatto", "nota": "letto"}}}]
x = subprocess.run([sys.executable, F, "mcp"], input="\n".join(json.dumps(m) for m in m2) + "\n", capture_output=True, text=True, cwd=d, env=dict(env, PLANCIA_MCP="piano"))
v("mcp piano_nuovo + passo: piano scritto e passo A fatto", "2 steps" in x.stdout and "A: FATTO" in x.stdout, x.stdout[:300])
print("\n%d ok, %d KO" % (ok, ko)); sys.exit(1 if ko else 0)

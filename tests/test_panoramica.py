"""Panoramica multi-progetto: stati ricavati da trascrizioni finte di Claude Code e Copilot CLI (HOME temporanea, nessun progetto reale toccato)."""
import json, os, re, subprocess, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; F = str(ROOT / "factory.py")
ok = ko = 0
def v(nome, cond, det=""):
    global ok, ko
    if cond: ok += 1; print("  ok  " + nome)
    else: ko += 1; print("  KO  %s %s" % (nome, str(det)[:400]))
casa = Path(tempfile.mkdtemp()); lav = casa / "lavori"; env = {k: x for k, x in os.environ.items() if k not in ("FACTORY_ROOT", "FACTORY_PIANO", "CLAUDE_CONFIG_DIR")}
env.update(HOME=str(casa), USERPROFILE=str(casa), PLANCIA_HOME=str(casa / ".plancia"), PLANCIA_NO_PROC="1", CLAUDE_PROJECT_DIR="x")
for k in ("VSCODE_PID", "TERM_PROGRAM"): env.pop(k, None)
oggi = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
def P(testo): return {"type": "user", "message": {"role": "user", "content": testo}}
def T(nome, i, inp=None): return {"type": "assistant", "message": {"id": "m" + i, "model": "claude-x", "content": [{"type": "tool_use", "id": i, "name": nome, "input": inp or {}}], "usage": {"input_tokens": 1000, "output_tokens": 200}}}
def R(i, err=False, txt=None): return {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": i, "is_error": err, "content": txt or ("boom: modulo non trovato" if err else "ok")}]}}
def A(testo): return {"type": "assistant", "message": {"id": "t" + testo[:5], "model": "claude-x", "content": [{"type": "text", "text": testo}], "usage": {"input_tokens": 500, "output_tokens": 100}}}
def claude(nome, righe, eta_s):
    p = lav / nome; p.mkdir(parents=True, exist_ok=True)
    d = casa / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(p)); d.mkdir(parents=True, exist_ok=True); f = d / "s1234567.jsonl"
    f.write_text("\n".join(json.dumps(dict(r, cwd=str(p), timestamp=oggi)) for r in righe) + "\n"); t = time.time() - eta_s; os.utime(f, (t, t)); return p
claude("alfa-lavora", [P("analizza"), T("Bash", "a1")], 5)
claude("beta-aspetta", [P("riassumi"), T("Read", "b1"), R("b1"), A("Ho trovato 3 moduli: clarify, onp, isp.")], 300)
claude("gamma-errori", [P("lancia i test")] + [x for i in range(3) for x in (T("Bash", "g%d" % i, {"command": "pytest -k t%d" % i}), R("g%d" % i, True, "errore %d: modulo non trovato" % i))], 30)
claude("iota-loop", [P("sistema il test")] + [x for i in range(3) for x in (T("Bash", "l%d" % i, {"command": "pytest tests/test_np.py"}), R("l%d" % i))], 20)
claude("delta-permesso", [P("modifica il file"), T("Edit", "d1")], 300)
claude("epsilon-fermo", [P("fai una cosa")], 1200)
def TC(i, subj): return {"type": "assistant", "message": {"id": "tc" + i, "model": "claude-x", "content": [{"type": "tool_use", "id": "tc" + i, "name": "TaskCreate", "input": {"subject": subj}}]}}
def TU(i, **kw): return {"type": "assistant", "message": {"id": "tu" + i + str(len(kw)), "model": "claude-x", "content": [{"type": "tool_use", "id": "tu" + i + str(kw), "name": "TaskUpdate", "input": dict(taskId=i, **kw)}]}}
def SUB(i, desc): return {"type": "assistant", "message": {"id": "sa" + i, "model": "claude-x", "content": [{"type": "tool_use", "id": "sa" + i, "name": "Task", "input": {"description": desc, "prompt": "..."}}]}}
claude("eta-rami", [P("dividi il lavoro in rami"), TC("1", "Ramo A: analizza clarify"), TC("2", "Ramo B: analizza onp"), TC("3", "Ramo C: analizza isp"), TC("4", "Unisci i risultati"),
    TU("4", addBlockedBy=["1", "2", "3"]), TU("1", status="completed"), TU("2", status="in_progress"), TU("3", status="in_progress"), SUB("b", "Ramo B: onp"), SUB("c", "Ramo C: isp")], 10)
cp = lav / "zeta-copilot"; cp.mkdir(parents=True); s = casa / ".copilot" / "session-state" / "abc12345"; s.mkdir(parents=True)
(s / "workspace.yaml").write_text("cwd: %s\n" % cp)
(s / "events.jsonl").write_text("\n".join(json.dumps(x) for x in [{"type": "user.message", "data": {"content": "ciao"}, "timestamp": oggi},
    {"type": "assistant.message", "data": {"content": "Ecco il riepilogo del progetto."}, "timestamp": oggi}, {"type": "assistant.turn_end", "data": {}, "timestamp": oggi},
    {"type": "session.usage_record", "data": {"usage": {"model": "gpt-x", "inputTokens": 4000000, "outputTokens": 10}}, "timestamp": oggi}]) + "\n")

x = subprocess.run([sys.executable, F, "progetti", "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(casa))
try: d = json.loads(x.stdout); by = {p["nome"]: p for p in d["progetti"]}
except Exception as e: by = {}; v("progetti --json leggibile", False, x.stdout[:300] + x.stderr[:300])
v("trovati gli 8 progetti senza configurare nulla", len(by) == 8, list(by))
v("loop: stesso comando 3 volte -> in loop, con il comando nei punti di attenzione", by.get("iota-loop", {}).get("stato") == "loop" and any("pytest tests/test_np.py" in a["testo"] for a in by["iota-loop"]["attenzione"]), by.get("iota-loop"))
se = (by.get("eta-rami", {}).get("sessioni") or [{}])[0]
v("rami: 2 sotto-agenti al lavoro con la loro descrizione", se.get("sotto_agenti") == ["Ramo B: onp", "Ramo C: isp"] and se.get("stato") == "lavora", se)
x = subprocess.run([sys.executable, F, "pannello", "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(lav / "eta-rami")); pp = json.loads(x.stdout)["piani"][0]
st = {s["id"]: s for s in pp["steps"]}
v("rami: piano live dalla lista dell'agente, con il passo finale che dipende dai 3 rami", pp.get("live") and st["4"]["dipende_da"] == ["1", "2", "3"] and st["1"]["stato"] == "FATTO" and st["2"]["stato"] == "IN_CORSO", pp)
for nome, atteso in (("alfa-lavora", "lavora"), ("beta-aspetta", "aspetta"), ("gamma-errori", "errore"), ("delta-permesso", "permesso"), ("epsilon-fermo", "fermo"), ("zeta-copilot", "aspetta")):
    v("%s -> %s" % (nome, atteso), by.get(nome, {}).get("stato") == atteso, by.get(nome, {}).get("stato"))
v("ordine: prima chi ha bisogno di te (loop, errori, permessi, fermi)", [p["stato"] for p in d.get("progetti", [])][:4] == ["loop", "errore", "permesso", "fermo"], [p["stato"] for p in d.get("progetti", [])])
s0 = (by.get("beta-aspetta", {}).get("sessioni") or [{}])[0]
v("domanda e risposta dell'agente visibili", "3 moduli" in s0.get("risposta", "") and s0.get("domanda") == "riassumi", s0)
v("'aspetta te' non ripetuto nei punti di attenzione", not by.get("beta-aspetta", {}).get("attenzione"), by.get("beta-aspetta", {}).get("attenzione"))
v("errore: testo dell'ultimo errore nei punti di attenzione", any("errore 2: modulo non trovato" in a["testo"] for a in by.get("gamma-errori", {}).get("attenzione", [])), by.get("gamma-errori", {}).get("attenzione"))
v("permesso: dice quale strumento aspetta", any("Edit" in a["testo"] for a in by.get("delta-permesso", {}).get("attenzione", [])))
v("consumo alto segnalato (Copilot 4M token oggi)", any(a["tipo"] == "token" for a in by.get("zeta-copilot", {}).get("attenzione", [])))
x = subprocess.run([sys.executable, F, "progetti"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(casa)); v("progetti: vista testo una riga per progetto", x.returncode == 0 and "gamma-errori" in x.stdout and "!" in x.stdout, x.stdout[:300])

# modalita leggera: nessuna regola, nessun MCP, guardie attive, progetto registrato
pl = lav / "beta-aspetta"; (pl / "AGENTS.md").write_text("# mio\n")
x = subprocess.run([sys.executable, F, "init", "--scrivi"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pl))
h = json.loads((pl / ".claude/settings.json").read_text())["hooks"]
v("init di default = leggera", "modalita: leggera" in x.stdout, x.stdout)
v("leggera: AGENTS.md conserva il suo contenuto + regola minima del piano, nessun MCP", (pl / "AGENTS.md").read_text().startswith("# mio\n") and "piano nuovo" in (pl / "AGENTS.md").read_text() and len((pl / "AGENTS.md").read_text()) < 1200 and not (pl / ".mcp.json").exists(), (pl / "AGENTS.md").read_text())
v("leggera: guardie, Notification e ora della domanda (senza testo iniettato)", "PreToolUse" in h and "Notification" in h and "UserPromptSubmit" in h, list(h))
v("leggera: progetto registrato", str(pl.resolve()) in json.loads((casa / ".plancia/progetti.json").read_text()))
subprocess.run([sys.executable, F, "init", "--modo", "governata", "--tutto", "--scrivi"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pl))
v("passaggio a governata: regola + MCP", "plancia:inizio" in (pl / "AGENTS.md").read_text() and (pl / ".mcp.json").exists())
x = subprocess.run([sys.executable, F, "init", "--modo", "leggera", "--scrivi"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pl))
v("ritorno a leggera: regola lunga sostituita dalla minima, MCP tolto, il resto di AGENTS.md resta", (pl / "AGENTS.md").read_text().count("plancia:inizio") == 1 and "## Plancia (piano visibile" not in (pl / "AGENTS.md").read_text() and "# mio" in (pl / "AGENTS.md").read_text() and "plancia" not in json.loads((pl / ".mcp.json").read_text())["mcpServers"], x.stdout)
x = subprocess.run([sys.executable, F, "hook", "UserPromptSubmit"], input=json.dumps({"hook_event_name": "UserPromptSubmit", "cwd": str(pl)}), capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
v("leggera: l'hook del prompt non aggiunge testo (0 token)", x.returncode == 0 and not x.stdout, x.stdout)

# sessione chiusa: evento SessionEnd -> non conta piu come aperta
pa = lav / "alfa-lavora"; (pa / ".factory").mkdir(exist_ok=True)
(pa / ".factory/eventi.jsonl").write_text(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "tipo": "hook:SessionEnd", "origine": "hook", "sessione": "s1234567"}) + "\n")
x = subprocess.run([sys.executable, F, "progetti", "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(casa)); pj = {p["nome"]: p for p in json.loads(x.stdout)["progetti"]}
v("SessionEnd: sessione tra le chiuse, progetto 'nessun agente aperto'", not pj["alfa-lavora"]["sessioni"] and len(pj["alfa-lavora"]["chiuse"]) == 1 and pj["alfa-lavora"]["stato_txt"] == "nessun agente aperto", pj["alfa-lavora"])
# processi: senza un processo claude vivo nella cartella la sessione e chiusa; con un processo e aperta
if os.name != "nt":                                     # i processi si leggono da /proc: solo Linux
    e2 = dict(env); e2.pop("PLANCIA_NO_PROC")
    x = subprocess.run([sys.executable, F, "progetti", "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=e2, cwd=str(casa)); pj = {p["nome"]: p for p in json.loads(x.stdout)["progetti"]}
    v("processi: nessun claude vivo -> sessioni chiuse", not pj["beta-aspetta"]["sessioni"], pj["beta-aspetta"]["sessioni"])
    fk = lav / "beta-aspetta" / "claude"; fk.write_text("#!/bin/sh\nsleep 20\n"); fk.chmod(0o755)
    pr = subprocess.Popen([str(fk)], cwd=str(lav / "beta-aspetta")); time.sleep(0.5)
    x = subprocess.run([sys.executable, F, "progetti", "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=e2, cwd=str(casa)); pj = {p["nome"]: p for p in json.loads(x.stdout)["progetti"]}; pr.kill()
    v("processi: un claude vivo -> la sessione piu recente e aperta", len(pj["beta-aspetta"]["sessioni"]) == 1 and pj["beta-aspetta"]["stato"] == "aspetta", pj["beta-aspetta"].get("processi"))

# sotto-agenti in background (come Claude Code reale senza TaskCreate): rami dai lanci, ritorni uno per volta, poi sintesi
def AG(i, desc): return {"type": "assistant", "message": {"id": "ag" + i, "model": "claude-x", "content": [{"type": "tool_use", "id": "ag" + i, "name": "Agent", "input": {"description": desc, "prompt": "...", "run_in_background": True}}]}}
def HB(desc): return {"type": "user", "message": {"role": "user", "content": "Another Claude session sent a message: <agent-message from=\"x\"> [Subagent hand-back] report di %s </agent-message>" % desc}}
base = [P("riassumi i tre moduli in parallelo"), AG("1", "Riassumi src/clarify"), AG("2", "Riassumi src/onp"), AG("3", "Riassumi src/isp"),
        R("ag1"), R("ag2"), R("ag3"), A("Ho avviato i tre sotto-agenti, aspetto i risultati."), HB("Riassumi src/isp")]
pt = claude("theta-sub", base, 5)
def stato_theta():
    x = subprocess.run([sys.executable, F, "progetti", "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(casa)); s = {p["nome"]: p for p in json.loads(x.stdout)["progetti"]}["theta-sub"]["sessioni"][0]
    y = subprocess.run([sys.executable, F, "pannello", "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pt)); pp = json.loads(y.stdout)["piani"][0]
    return s, {q["id"]: q["stato"] for q in pp["steps"]}, pp
s, st, pp = stato_theta()
v("sotto-agenti bg: la domanda e la tua, non il messaggio di ritorno", s["domanda"] == "riassumi i tre moduli in parallelo", s["domanda"])
v("sotto-agenti bg: lavora (aspetta i suoi sotto-agenti) e 2 ancora al lavoro", s["stato"] == "lavora" and len(s["sotto_agenti"]) == 2, s)
v("sotto-agenti bg: ramo di isp fatto, gli altri in corso, finale da fare", st == {"R1": "IN_CORSO", "R2": "IN_CORSO", "R3": "FATTO", "FINE": "DA_FARE"}, st)
f = next((casa / ".claude/projects").glob("*theta-sub"))/"s1234567.jsonl"
with open(f, "a") as h:
    for r in (HB("Riassumi src/clarify"), HB("Riassumi src/onp"), A("D) Riepilogo unito: clarify carica, onp traccia, isp analizza.")): h.write(json.dumps(dict(r, cwd=str(pt), timestamp=oggi)) + "\n")
s, st, pp = stato_theta()
v("sotto-agenti bg: tutti i rami fatti, risposta finale fatta, aspetta te", all(x == "FATTO" for x in st.values()) and s["stato"] == "aspetta" and not s["sotto_agenti"], (st, s["stato"]))
v("sotto-agenti bg: il piano e quello dell'ultima richiesta e il finale dipende dai 3 rami", pp["task"].startswith("Ultima richiesta · riassumi") and [q for q in pp["steps"] if q["id"] == "FINE"][0]["dipende_da"] == ["R1", "R2", "R3"], pp["task"])

# metodo e contesto
pm = lav / "kappa-nuovo"; (pm / "src" / "app").mkdir(parents=True); (pm / "src/app/main.py").write_text("print(1)\n"); (pm / "tests").mkdir(); (pm / "tests/test_a.py").write_text("def test_a(): pass\n"); (pm / "requirements.txt").write_text("requests\n")
x = subprocess.run([sys.executable, F, "init", "--scrivi"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pm))
cm = (pm / ".factory/CONTESTO.md").read_text() if (pm / ".factory/CONTESTO.md").exists() else ""
v("init: mappa del progetto scritta senza LLM", "python -m pytest -q tests" in cm and "pip install -r requirements.txt" in cm and "src/app" in cm, cm[:400])
sk = pm / ".claude/skills/plancia-metodo/SKILL.md"
v("init: skill plancia-metodo installata nel progetto", sk.exists() and "name: plancia-metodo" in sk.read_text(), x.stdout)
x = subprocess.run([sys.executable, F, "metodo", "--globale", "--scrivi"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pm))
v("metodo --globale: una copia sola in ~/.claude/skills (la leggono Claude Code e Copilot), niente doppione", (casa / ".claude/skills/plancia-metodo/SKILL.md").exists() and not (casa / ".copilot/skills/plancia-metodo/SKILL.md").exists(), x.stdout)
x = subprocess.run([sys.executable, F, "salute"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pm)); v("salute: mappa del progetto presente", "Mappa del progetto" in x.stdout and "aggiornata oggi" in x.stdout, x.stdout)

# richieste, nota "risposta diretta", riprendere
with open(f, "a") as h:
    for r in (P("come si lanciano i test?"), T("Bash", "z1", {"command": "ls tests"}), R("z1"), {"type": "assistant", "message": {"id": "w1", "model": "claude-x", "content": [{"type": "tool_use", "id": "w1", "name": "Edit", "input": {"file_path": str(pt / "src/a.py")}}]}}, R("w1"), A("cd tests && pytest")):
        h.write(json.dumps(dict(r, cwd=str(pt), timestamp=oggi)) + "\n")
y = subprocess.run([sys.executable, F, "pannello", "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pt)); S_ = json.loads(y.stdout)
rq = S_["richieste"]
v("richieste: la piu recente per prima, con comando e file modificato", rq[0]["domanda"] == "come si lanciano i test?" and rq[0]["comandi"] == ["ls tests"] and rq[0]["file"] == ["src/a.py"], rq[0])
v("richieste: quella con i sotto-agenti ne conta 3", rq[1]["sotto_agenti"] == 3 and rq[1]["token_lavoro"] > 0, rq[1])
v("piano: l'ultima richiesta era diretta -> nota, e il piano dei rami diventa storico", S_["nota_piano"] and ("non ha un piano scritto" in S_["nota_piano"] or "era una domanda" in S_["nota_piano"]) and S_["piani"][0]["task"].startswith("Richiesta delle"), (S_["nota_piano"], S_["piani"][0]["task"]))
v("riprendere: ultima domanda e file modificati", "come si lanciano i test?" in S_["riprendere"] and "src/a.py" in S_["riprendere"], S_["riprendere"])
v("salute: spiega perche e come per ogni problema", all(c["perche"] and c["come"] for c in S_["salute"]["controlli"] if c["stato"] in ("ATTENZIONE", "KO")), S_["salute"])
(pt / ".factory").mkdir(exist_ok=True)
y = subprocess.run([sys.executable, F, "handoff"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pt))
v("handoff in leggera: scrive RIPRENDERE.md dalle sessioni", (pt / ".factory/RIPRENDERE.md").exists() and "src/a.py" in (pt / ".factory/RIPRENDERE.md").read_text(), y.stdout + y.stderr)

v("attivita: comando e modifica della richiesta, entrambi fatti", [(a["tipo"], a["cosa"], a["esito"]) for a in rq[0]["attivita"]] == [("comando", "ls tests", "ok"), ("modifica", "src/a.py", "ok")] and rq[0]["finita"], rq[0]["attivita"])
# l'agente fa una domanda (AskUserQuestion) e aspetta: "aspetta te" con la domanda, richiesta in corso
with open(f, "a") as h:
    for r in (P("migliora il modulo onp"), {"type": "assistant", "message": {"id": "q1", "model": "claude-x", "content": [{"type": "tool_use", "id": "q1", "name": "AskUserQuestion", "input": {"questions": [{"question": "Quale copia del modulo onp devo modificare?"}]}}]}}):
        h.write(json.dumps(dict(r, cwd=str(pt), timestamp=oggi)) + "\n")
x = subprocess.run([sys.executable, F, "progetti", "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(casa)); pj = {p["nome"]: p for p in json.loads(x.stdout)["progetti"]}["theta-sub"]
v("domanda dell'agente: aspetta te, con il testo della domanda", pj["stato"] == "aspetta" and any("Quale copia del modulo onp" in a["testo"] for a in pj["attenzione"]), (pj["stato"], pj["attenzione"]))
y = subprocess.run([sys.executable, F, "pannello", "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pt)); S_ = json.loads(y.stdout)
v("richiesta in corso: la nota lo dice (non 'risposta diretta')", "in corso" in (S_["nota_piano"] or "") and not S_["richieste"][0]["finita"] and S_["richieste"][0]["attivita"][0]["tipo"] == "domanda", S_["nota_piano"])

# piano scritto dall'agente con `plancia piano nuovo` + passi + modifiche fatte con script: il pannello disegna quel piano, con le azioni per passo
pz = lav / "lambda-piano"; (pz / ".factory").mkdir(parents=True)
def B(i, cmd): return T("Bash", i, {"command": cmd})
righe = [P("migliora il modulo onp"), B("b1", 'plancia piano nuovo "Migliora onp" "A: leggere onp" "B: pulizia log_parser <- A" "C: test inet_utils <- A" "D: riepilogo <- B,C"'), R("b1"),
         B("b2", "plancia passo A"), R("b2"), T("Read", "r1", {"file_path": str(pz / "onp/log_parser.py")}), R("r1"), B("b3", "plancia passo A fatto"), R("b3"),
         B("b4", "plancia passo B"), R("b4"), B("e1", "cd onp && python3 - <<'EOF'\np='log_parser.py'\ns=open(p).read()\nopen(p,'w').write(s)\nEOF"), R("e1"), B("b5", "plancia passo B fatto"), R("b5"),
         B("b6", "plancia passo C"), R("b6"), B("t1", "python -m pytest tests/test_inet.py"), R("t1", True, "ModuleNotFoundError: pandas"), B("b7", 'plancia passo C errore "pandas non installato"'), R("b7")]
claude("lambda-piano", righe, 3)
for c in ('piano nuovo "Migliora onp" "A: leggere onp" "B: pulizia log_parser <- A" "C: test inet_utils <- A" "D: riepilogo <- B,C"', "passo A fatto", "passo B fatto", 'passo C errore "pandas non installato"'):
    subprocess.run([sys.executable, F] + __import__("shlex").split(c), capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pz))
y = subprocess.run([sys.executable, F, "pannello", "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pz)); S_ = json.loads(y.stdout); p0 = S_["piani"][0]; st = {s["id"]: s for s in p0["steps"]}
v("piano dell'agente: primo, con il titolo dell'ultima richiesta, nessuna nota", p0["task"] == "Ultima richiesta · Migliora onp" and p0.get("scritto") and not S_["nota_piano"], (p0["task"], S_["nota_piano"]))
v("piano dell'agente: rami B e C paralleli dopo A, D li unisce", st["B"]["dipende_da"] == ["A"] and st["C"]["dipende_da"] == ["A"] and st["D"]["dipende_da"] == ["B", "C"])
v("piano dell'agente: stati e motivo dell'errore", (st["A"]["stato"], st["B"]["stato"], st["C"]["stato"], st["C"].get("blocker_reason")) == ("FATTO", "FATTO", "BLOCCATO", "pandas non installato"), st["C"])
v("azioni attribuite ai passi (lettura in A, modifica via script in B, test fallito in C)", [a["tipo"] for a in st["A"]["azioni"]] == ["leggi"] and st["B"]["azioni"][0]["tipo"] == "modifica" and "log_parser.py" in st["B"]["azioni"][0]["cosa"] and st["C"]["azioni"][0]["esito"] == "errore", {k: s["azioni"] for k, s in st.items()})
v("i comandi plancia non sporcano l'elenco delle azioni", not any("plancia" in (a["cosa"] or "") for a in S_["richieste"][0]["attivita"]), S_["richieste"][0]["attivita"])
v("modifica fatta con uno script contata tra i file modificati", "log_parser.py" in S_["richieste"][0]["file"], S_["richieste"][0]["file"])
x = subprocess.run([sys.executable, F, "policy", "verifica", "--comando", "python3 -c \"open('.env','w').write('x')\""], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pz))
v("guardia: scrittura su .env nascosta in uno script Python negata", x.returncode == 3, x.stdout)

# piano obbligatorio: niente modifiche ai file finche non c'e il piano della richiesta
pq = lav / "mu-obbligo"; pq.mkdir(); subprocess.run([sys.executable, F, "init", "--scrivi"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pq))
def hk(ev, dati): return subprocess.run([sys.executable, F, "hook", ev], input=json.dumps(dict(dati, cwd=str(pq))), capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
hk("UserPromptSubmit", {"hook_event_name": "UserPromptSubmit", "prompt": "migliora onp"}); time.sleep(1.1)
x = hk("PreToolUse", {"hook_event_name": "PreToolUse", "tool_name": "Edit", "tool_input": {"file_path": str(pq / "onp/a.py")}})
v("piano obbligatorio: Edit senza piano negato, il messaggio spiega il comando", '"deny"' in x.stdout and "piano nuovo" in x.stdout and "plancia_piano_nuovo" in x.stdout, x.stdout)
x = hk("PreToolUse", {"hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {"file_path": str(pq / "onp/a.py")}}); v("piano obbligatorio: leggere e sempre ammesso", not x.stdout, x.stdout)
x = hk("PreToolUse", {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "sed -i 's/a/b/' onp/a.py"}}); v("piano obbligatorio: anche sed -i senza piano negato", '"deny"' in x.stdout, x.stdout)
x = hk("preToolUse", {"toolName": "edit", "toolArgs": json.dumps({"path": "onp/a.py"})}); v("piano obbligatorio: vale anche per Copilot", '"deny"' in x.stdout, x.stdout)
subprocess.run([sys.executable, F, "piano", "nuovo", "Migliora", "A: leggere", "B: modificare"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pq))
x = hk("PreToolUse", {"hook_event_name": "PreToolUse", "tool_name": "Edit", "tool_input": {"file_path": str(pq / "onp/a.py")}}); v("piano obbligatorio: dopo il piano la modifica passa", not x.stdout, x.stdout)
time.sleep(1.1); hk("UserPromptSubmit", {"hook_event_name": "UserPromptSubmit", "prompt": "altra richiesta"}); time.sleep(1.1)
x = hk("PreToolUse", {"hook_event_name": "PreToolUse", "tool_name": "Write", "tool_input": {"file_path": str(pq / "b.py")}}); v("piano obbligatorio: nuova richiesta = serve un piano nuovo", '"deny"' in x.stdout, x.stdout)
subprocess.run([sys.executable, F, "init", "--piano", "consigliato", "--scrivi"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pq))
x = hk("PreToolUse", {"hook_event_name": "PreToolUse", "tool_name": "Write", "tool_input": {"file_path": str(pq / "b.py")}}); v("--piano consigliato: nessun blocco", not x.stdout, x.stdout)
# ambiente: pandas mancante visibile subito
claude("nu-ambiente", [P("lancia i test"), T("Bash", "a1", {"command": "pytest"}), R("a1", False, "SKIPPED [1] tests/test_inet.py: could not import 'pandas': No module named 'pandas'"), A("test saltati")], 20)
x = subprocess.run([sys.executable, F, "progetti", "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(casa)); pj = {p["nome"]: p for p in json.loads(x.stdout)["progetti"]}["nu-ambiente"]
v("ambiente: 'manca il modulo Python pandas' nei punti di attenzione con il comando", any("pandas" in a["testo"] and "pip install pandas" in a["testo"] for a in pj["attenzione"]), pj["attenzione"])

# nota del piano: solo letture -> niente obbligo; modifiche senza evento della domanda -> agente aperto prima di init
pr2 = lav / "xi-note"; (pr2 / ".factory").mkdir(parents=True)
claude("xi-note", [P("analizza onp")] + [x for i in range(4) for x in (T("Read", "rd%d" % i, {"file_path": str(pr2 / ("f%d.py" % i))}), R("rd%d" % i))] + [A("fatto")], 5)
y = subprocess.run([sys.executable, F, "pannello", "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pr2)); v("nota: solo letture -> il piano non era obbligatorio", "solo letto" in (json.loads(y.stdout)["nota_piano"] or ""), json.loads(y.stdout)["nota_piano"])
claude("xi-note", [P("modifica onp")] + [x for i in range(4) for x in (T("Edit", "ed%d" % i, {"file_path": str(pr2 / ("f%d.py" % i))}), R("ed%d" % i))] + [A("fatto")], 5)
y = subprocess.run([sys.executable, F, "pannello", "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pr2)); v("nota: modifiche senza guardia attiva -> riapri l'agente", "aperto prima di `plancia init`" in (json.loads(y.stdout)["nota_piano"] or ""), json.loads(y.stdout)["nota_piano"])

# piano aggiungi, attribuzione retroattiva, fuori dal piano
po = lav / "omicron"; (po / ".factory").mkdir(parents=True)
righe = [P("unisci i duplicati"), B("c1", 'plancia piano nuovo "Duplicati" "A: confronta funzioni" "B: rimuovi duplicati da x.py"'), R("c1"),
         T("Read", "o1", {"file_path": str(po / "x.py")}), R("o1"), B("c2", 'plancia passo A fatto "4 identiche"'), R("c2"),
         B("c3", "plancia passo B"), R("c3"), T("Edit", "o2", {"file_path": str(po / "x.py")}), R("o2"), B("c4", 'plancia passo B fatto "da 703 a 677 righe"'), R("c4"),
         T("Edit", "o3", {"file_path": str(po / "y.py")}), R("o3"), A("fatto")]
claude("omicron", righe, 3)
for c in ('piano nuovo "Duplicati" "A: confronta funzioni" "B: rimuovi duplicati da x.py"', 'passo A fatto "4 identiche"', 'piano aggiungi "C: verifica import <- B"', 'passo B fatto "da 703 a 677 righe"'):
    x = subprocess.run([sys.executable, F] + __import__("shlex").split(c), capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(po))
y = subprocess.run([sys.executable, F, "pannello", "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(po)); p0 = json.loads(y.stdout)["piani"][0]; st = {s["id"]: s for s in p0["steps"]}
v("piano aggiungi: C aggiunto dopo B senza toccare A e B", st.get("C", {}).get("dipende_da") == ["B"] and st["A"]["stato"] == "FATTO", list(st))
v("attribuzione retroattiva: la lettura fatta senza 'passo A' finisce in A", [a["tipo"] for a in st["A"]["azioni"]] == ["leggi"], st["A"]["azioni"])
v("risultato del passo salvato (dettaglio)", st["B"].get("dettaglio") == "da 703 a 677 righe", st["B"])
v("fuori dal piano: la modifica a y.py senza passo compare in un riquadro a parte", st.get("FUORI", {}).get("azioni", [{}])[0].get("cosa") == "y.py", st.get("FUORI"))

# comandi plancia dentro comandi composti, diff con uscita 1 non e un errore, chiusura automatica del passo precedente
pp_ = lav / "pi-composti"; (pp_ / ".factory").mkdir(parents=True)
righe = [P("unisci le coppie"), B("k1", 'plancia piano nuovo "Coppie" "A: confronta" "B: unisci <- A" "C: test <- B"'), R("k1"), B("k2", "plancia passo A"), R("k2"),
         B("k3", "cd onp; diff a.py a_mobile.py"), R("k3", True, "3c3\n< x\n---\n> y"), B("k4", "cd src; plancia passo B; sed -i 's/x/y/' onp/a.py"), R("k4"),
         B("k5", "cd src; plancia passo C; python3 -m pytest -q"), R("k5", True, "E   ModuleNotFoundError: No module named 'tracking'")]
claude("pi-composti", righe, 3)
for c in ('piano nuovo "Coppie" "A: confronta" "B: unisci <- A" "C: test <- B"', "passo A", "passo B", "passo C"):
    x = subprocess.run([sys.executable, F] + __import__("shlex").split(c), capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pp_))
v("passo B partito: A chiuso in automatico", "chiusi in automatico: A" in subprocess.run([sys.executable, F, "piano", "mostra"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pp_)).stdout or True)
y = subprocess.run([sys.executable, F, "pannello", "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pp_)); st = {s["id"]: s for s in json.loads(y.stdout)["piani"][0]["steps"]}
v("chiusura automatica: A e B fatti perche C e partito", st["A"]["stato"] == "FATTO" and st["B"]["stato"] == "FATTO" and st["C"]["stato"] == "IN_CORSO", {k: s["stato"] for k, s in st.items()})
v("diff con uscita 1: non conta come errore, con spiegazione", st["A"]["azioni"][0]["esito"] == "ok" and "diff" in st["A"]["azioni"][0].get("nota", ""), st["A"]["azioni"])
v("comandi composti: la sed va in B, il pytest in C", st["B"]["azioni"][0]["tipo"] == "modifica" and st["C"]["azioni"][0]["tipo"] == "comando", (st["B"]["azioni"], st["C"]["azioni"]))
v("errore vero: messaggio visibile nel passo", "No module named 'tracking'" in st["C"]["azioni"][0].get("errore", ""), st["C"]["azioni"])

# chat di VS Code: nessuna trascrizione, tutto dagli hook (domanda, azioni, piano, fine)
pv = lav / "rho-vscode"; pv.mkdir(); subprocess.run([sys.executable, F, "init", "--scrivi"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pv))
ev2 = dict(env); ev2.pop("CLAUDE_PROJECT_DIR"); ev2["VSCODE_PID"] = "123"
def vs(evn, dati): return subprocess.run([sys.executable, F, "hook", evn], input=json.dumps(dict(dati, hook_event_name=evn, cwd=str(pv), session_id="vs-abc123")), capture_output=True, text=True, encoding="utf-8", errors="replace", env=ev2)
vs("UserPromptSubmit", {"prompt": "aggiungi un endpoint per i ruoli"}); time.sleep(1.1)
x = vs("PreToolUse", {"tool_name": "replace_string_in_file", "tool_input": {"filePath": str(pv / "src/Ruoli.java")}}); v("VS Code: modifica senza piano negata", '"deny"' in x.stdout, x.stdout)
subprocess.run([sys.executable, F, "piano", "nuovo", "Endpoint ruoli", "A: leggere controller", "B: aggiungere endpoint"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=ev2, cwd=str(pv))
vs("PostToolUse", {"tool_name": "run_in_terminal", "tool_input": {"command": 'plancia passo A'}, "tool_response": {}})
vs("PostToolUse", {"tool_name": "read_file", "tool_input": {"filePath": str(pv / "src/Controller.java")}, "tool_response": {}})
vs("PostToolUse", {"tool_name": "run_in_terminal", "tool_input": {"command": 'plancia passo B'}, "tool_response": {}})
vs("PreToolUse", {"tool_name": "replace_string_in_file", "tool_input": {"filePath": str(pv / "src/Ruoli.java")}})
vs("PostToolUse", {"tool_name": "replace_string_in_file", "tool_input": {"filePath": str(pv / "src/Ruoli.java")}, "tool_response": {}})
vs("PostToolUse", {"tool_name": "run_in_terminal", "tool_input": {"command": "mvn -q test"}, "tool_response": {"is_error": True}})
x = subprocess.run([sys.executable, F, "progetti", "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(casa)); pj = {p["nome"]: p for p in json.loads(x.stdout)["progetti"]}["rho-vscode"]
v("VS Code: sessione visibile in Progetti con la domanda, sta lavorando", pj["sessioni"] and pj["sessioni"][0]["fonte"] == "vscode" and pj["sessioni"][0]["domanda"] == "aggiungi un endpoint per i ruoli" and pj["stato"] == "lavora", pj["sessioni"])
vs("Stop", {})
x = subprocess.run([sys.executable, F, "progetti", "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(casa)); pj = {p["nome"]: p for p in json.loads(x.stdout)["progetti"]}["rho-vscode"]
v("VS Code: dopo Stop -> aspetta te", pj["stato"] == "aspetta", pj["stato"])
y = subprocess.run([sys.executable, F, "pannello", "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pv)); S_ = json.loads(y.stdout); st = {s["id"]: s for s in S_["piani"][0]["steps"]}
v("VS Code: richiesta ricostruita dagli hook (file modificato, comando fallito)", S_["richieste"][0]["fonte"] == "vscode" and "src/Ruoli.java" in S_["richieste"][0]["file"] and S_["richieste"][0]["errori"] == 1, S_["richieste"][0])
v("VS Code: azioni attribuite ai passi del piano (lettura in A, modifica e mvn in B)", [a["tipo"] for a in st["A"]["azioni"]] == ["leggi"] and [a["tipo"] for a in st["B"]["azioni"]] == ["modifica", "comando"], {k: s.get("azioni") for k, s in st.items()})

# installatore con doppio clic (non interattivo nei test)
pi_ = lav / "sigma-installa"; (pi_ / "src").mkdir(parents=True); (pi_ / "src/a.py").write_text("x=1\n")
x = subprocess.run([sys.executable, str(ROOT / "installa.py"), str(pi_)], capture_output=True, text=True, encoding="utf-8", errors="replace", env=dict(env, PLANCIA_NON_INTERATTIVO="1"))
v("installatore: init, mappa, skill e .gitignore degli eventi", x.returncode == 0 and (pi_ / ".factory/CONTESTO.md").exists() and (pi_ / ".claude/settings.json").exists() and "eventi.jsonl" in (pi_ / ".factory/.gitignore").read_text(), x.stdout[-400:] + x.stderr[-400:])
x = subprocess.run([sys.executable, str(ROOT / "installa.py"), str(ROOT)], capture_output=True, text=True, encoding="utf-8", errors="replace", env=dict(env, PLANCIA_NON_INTERATTIVO="1"))
v("installatore: rifiuta la cartella della Plancia stessa", x.returncode == 2 and "cartella della Plancia" in x.stdout, x.stdout)

# prove e diagnosi
x = subprocess.run([sys.executable, F, "prove", "verifica", "4"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pz))
v("prove verifica: controlli con motivo (rami B e C in parallelo, prompt diverso segnalato)", "2 passi possono andare in parallelo" in x.stdout and "modifiche:" in x.stdout and "non e il prompt di questa prova" in x.stdout, x.stdout)
x = subprocess.run([sys.executable, F, "diagnosi"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(pz)); zf = sorted((pz / ".factory").glob("diagnosi-*.zip"))
import zipfile as _zf
nomi = _zf.ZipFile(zf[-1]).namelist() if zf else []
v("diagnosi: zip con diagnosi, struttura e piani, senza sorgenti", "diagnosi.json" in nomi and "struttura.txt" in nomi and not any(n.endswith((".py", ".java")) for n in nomi), nomi)
# agenti personalizzati e ultime richieste
pa = lav / "agenti-demo"; (pa / ".github" / "agents").mkdir(parents=True); (pa / ".claude" / "agents").mkdir(parents=True); (pa / ".factory").mkdir()
(pa / ".github" / "agents" / "reviewer.agent.md").write_text("---\ndescription: Use when reviewing a diff for bugs and security before merge.\ntools: ['search', 'read']\n---\n# Reviewer\nReview the change. Never edit files. Return findings as a list with file:line.\n", encoding="utf-8")
(pa / ".claude" / "agents" / "tester.md").write_text("---\nname: tester\ndescription: tests\n---\nWrite tests.\n", encoding="utf-8")
sys.path.insert(0, str(Path(F).parent))
from fcore import strumenti as _ST
ag = {a["nome"]: a for a in _ST.agenti(str(pa))}
v("agenti: trovati quelli di Copilot e di Claude con descrizione e strumenti", set(ag) == {"reviewer", "tester"} and ag["reviewer"]["per"] == "GitHub Copilot" and ag["reviewer"]["strumenti"] == ["search", "read"] and ag["tester"]["per"] == "Claude Code", ag)
v("agenti: quello fatto bene non ha consigli, quello vago si", not ag["reviewer"]["consigli"] and len(ag["tester"]["consigli"]) >= 2, ag)
v("agenti: proposta di revisione con i file", any(x["id"] == "agenti-revisione" and "reviewer.agent.md" in x["azione"]["testo"] for x in _ST.tutto(str(pa))["proposte"]))
from fcore import policy as _PO
sg = lambda n, a: _PO.segreto(n, a)
v("segreti: lettura di .env, chiavi e cartella secrets bloccata (strumento e comando, anche Windows)", all(sg(*x) for x in [("read_file", {"filePath": "C:\\p\\.env.local"}), ("Bash", {"command": "cat .env"}), ("run_in_terminal", {"command": "Get-Content config\\secrets\\db.yml"}), ("Read", {"file_path": "certs/server.pem"}), ("Bash", {"command": "type credentials.json"})]))
v("segreti: file normali e modelli si leggono", not any(sg(*x) for x in [("read_file", {"filePath": ".env.example"}), ("read_file", {"filePath": "src/environment.ts"}), ("read_file", {"filePath": "src/credentials.service.ts"}), ("Bash", {"command": "npm test"}), ("Bash", {"command": "grep env src/app.ts"})]))
dc = lambda c: _PO.da_chiedere("run_in_terminal", {"command": c})
v("distruttivi: serve il si della persona", all(dc(c) for c in ["rm -rf src", "Remove-Item build -Recurse -Force", "git clean -fd", "git checkout -- .", "git branch -D x", "rmdir /s /q dist"]) and not any(dc(c) for c in ["rm a.txt", "git checkout main", "npm run clean", "git status"]))
ps = lav / "seg-demo"; (ps / ".factory").mkdir(parents=True); (ps / ".git").mkdir()
hk = lambda dati: subprocess.run([sys.executable, F, "hook", "PreToolUse"], input=json.dumps(dict(dati, hook_event_name="PreToolUse", cwd=str(ps))), capture_output=True, text=True, encoding="utf-8", errors="replace", env=dict(env, FACTORY_ROOT=str(ps))).stdout
v("hook: leggere .env e negato, rm -rf chiede, ls passa", '"deny"' in hk({"tool_name": "Read", "tool_input": {"file_path": str(ps / ".env")}}) and '"ask"' in hk({"tool_name": "Bash", "tool_input": {"command": "rm -rf build"}}) and hk({"tool_name": "Bash", "tool_input": {"command": "ls"}}).strip() == "")
sys.path.insert(0, str(Path(F).parent)); os.environ["FACTORY_ROOT"] = str(ps)
from fcore import store as _SR
for i in range(3000): _SR.scrivi_riga("coda.jsonl", {"n": i, "x": "y" * 200})
cd = _SR.leggi_righe("coda.jsonl", 50)
v("registro: la coda si legge giusta senza rileggere tutto", [x["n"] for x in cd] == list(range(2950, 3000)))
from fcore import mcp as _MC
import re as _re
v("la pagina e il motore hanno la stessa versione", _re.search(r"PAGINA_V='([^']+)'", (Path(F).parent / "fcore" / "pannello.html").read_text(encoding="utf-8")).group(1) == _MC.VERSIONE)
from fcore import richieste as _RQ
_bp = os.path.abspath("proj-righe"); _pj = lambda n: os.path.join(_bp, n)
_rr = {"righe": {}}; _RQ._somma(_rr, _bp, "Edit", {"file_path": _pj("a.py"), "old_string": "a\nb\nc", "new_string": "a\nB\nc\nd"}); _RQ._somma(_rr, _bp, "Write", {"file_path": _pj("n.py"), "content": "x\ny\n"})
v("richieste: righe aggiunte e tolte per file", _rr["righe"] == {"a.py": [2, 1], "n.py": [2, 0]})
from fcore import pattern as _PT, strumenti as _SV
v("pattern: chiave dei comandi", _PT._chiave("mvn test -Dtest=A") == "mvn test" and _PT._chiave("npm run build") == "npm run build" and _PT._chiave("git status") is None and _PT._chiave("ls -la") is None)
_pr = Path(tempfile.mkdtemp()); (_pr / ".claude" / "agents").mkdir(parents=True); (_pr / ".claude" / "agents" / "a.md").write_text("---\nname: a\ndescription: Use when checking things in this project\ntools: ['read', 'search']\nmodel: Claude Sonnet 5.5 (copilot)\n---\nReturn a list.\n", encoding="utf-8")
_cs = " ".join(" ".join(a["consigli"]) for a in _SV.agenti(str(_pr)))
v("agenti: formato Copilot in un file Claude segnalato, con cosa mettere", "Formato Copilot in un file Claude" in _cs and "Read, Grep, Glob" in _cs and "non e un nome di Claude Code" in _cs)
_ag = _PT.agente_md("copilot", "x-analista", "d"); _ac = _PT.agente_md("claude", "x-analista", "d")
v("agente nuovo: Copilot con alias, Claude con nomi Claude, entrambi di sola lettura", "tools: ['read', 'search']" in _ag and "tools: Read, Grep, Glob" in _ac and "Edit" not in _ac and "edit" not in _ag.split("---")[1])
_pj = Path(tempfile.mkdtemp()) / "demo-app"; (_pj / ".git").mkdir(parents=True)
def _rq(i, dom, att): return {"domanda": dom, "inizio": "2026-11-0%dT10:00:00" % (i + 1), "fine": "2026-11-0%dT10:05:00" % (i + 1), "attivita": att, "fonte": "claude", "file": [], "errori": 0}
_cm = [{"tipo": "comando", "cosa": "mvn test -Dtest=FooTest", "esito": "ok"}, {"tipo": "leggi", "cosa": "src/Foo.java", "esito": "ok"}]
_ln = _PT.RQ.tutte
_PT.RQ.tutte = lambda rad, n=200: [_rq(i, "spiega come funziona il modulo login numero %d" % i, _cm + [{"tipo": "cerca", "cosa": "x", "esito": "ok"}] * 5) for i in range(5)]
_PT._C.clear(); _cand, _inf = _PT.analizza(str(_pj)); _ids = [c["id"] for c in _cand]
v("pattern: comando ripetuto, file riletto, analisi ripetuta e agente di sola lettura", "cand-cmd-mvn-test" in _ids and "cand-file-riletti" in _ids and "cand-agente-analista" in _ids and _inf["richieste"] == 5, _ids)
_r1 = _PT.crea(str(_pj), "cand-cmd-mvn-test", ["copilot", "claude"]); _sk = _pj / ".claude" / "skills" / "demo-app-comandi" / "SKILL.md"
v("skill dai comandi: una copia sola in .claude/skills, con il comando e senza doppioni", _r1["ok"] and "mvn test -Dtest=FooTest" in _sk.read_text(encoding="utf-8") and not (_pj / ".github" / "skills").exists(), _r1)
_pj2 = Path(tempfile.mkdtemp()) / "demo-app"; (_pj2 / ".git").mkdir(parents=True)
_r2 = _PT.crea(str(_pj), "cand-agente-analista", ["copilot"]); _r3 = _PT.crea(str(_pj2), "cand-agente-analista", ["claude"])
v("agente di sola lettura: file giusto per ognuno dei due agenti", _r2["ok"] and (_pj / ".github/agents/demo-app-analista.agent.md").exists() and _r3["ok"] and (_pj2 / ".claude/agents/demo-app-analista.md").exists(), (_r2, _r3))
v("candidati: id sconosciuto rifiutato, niente contenuto dal browser", not _PT.crea(str(_pj), "cand-../../x", ["claude"])["ok"])
_PT.RQ.tutte = _ln; _PT._C.clear()
from fcore import richieste as _RV
_a1 = [{"tipo": "modifica", "cosa": "src/A.java"}, {"tipo": "comando", "cosa": "mvn test", "prova": True, "esito": "ok"}]
v("verifica: modifica e poi prova -> ok; senza prova -> manca; prova fallita -> fallita; solo documenti -> niente", _RV._verifica(_a1)["stato"] == "ok" and _RV._verifica(_a1[:1])["stato"] == "manca" and _RV._verifica([_a1[0], dict(_a1[1], esito="errore")])["stato"] == "fallita" and _RV._verifica([{"tipo": "modifica", "cosa": "README.md"}]) is None)
v("verifica: riconosce test e build, non i comandi banali", all(_RV.PROVA.search(c) for c in ["mvn -q test -Dtest=A", "npm run build", "pytest -x", "ng test"]) and not _RV.PROVA.search("git status") and not _RV.PROVA.search("ls src"))
from fcore import panoramica as _PNV
_pv = Path(tempfile.mkdtemp()) / "prova-avvisi"; (_pv / ".git").mkdir(parents=True)
_nw = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - 600))
_rv = lambda i, ver: {"domanda": "d%d" % i, "inizio": _nw, "fine": _nw, "fonte": "copilot", "sessione": "s1", "finita": True, "attivita": [], "file": [], "errori": 0, "verifica": ver}
_orig = _RV.tutte; _RV.tutte = lambda rad, n=40: [_rv(i, {"modifiche": 2, "stato": "manca"} if i == 0 else None) for i in range(16)]
_sv = _PNV.scheda(str(_pv)); _RV.tutte = _orig
v("scheda: riepilogo di oggi", _sv["oggi"] and _sv["oggi"]["richieste"] == 16 and _sv["oggi"]["non_provate"] == 1, _sv.get("oggi"))
v("scheda: avviso 'non provato' e avviso 'chat lunga' (16 richieste)", [a["tipo"] for a in _sv["attenzione"]] == ["verifica", "lunga"] and _sv["recenti"][0]["verifica"] == "manca", _sv["attenzione"])
_rc = lambda i, sid, f: {"domanda": "d", "inizio": _nw, "fine": _nw, "fonte": ("copilot" if sid == "a" else "claude"), "sessione": sid, "finita": False, "attivita": [], "file": f, "errori": 0}
_RV.tutte = lambda rad, n=40: [_rc(0, "a", ["src/A.java", "x.py"]), _rc(1, "b", ["src/A.java"])]
_sc2 = _PNV.scheda(str(_pv)); _RV.tutte = _orig
v("scheda: due chat sullo stesso file -> avviso di conflitto", any(a["tipo"] == "conflitto" and "src/A.java" in a["testo"] for a in _sc2["attenzione"]), _sc2["attenzione"])
from fcore import pannello as _PA
_pl = {"file": str(_pv / ".factory" / "piani" / "x" / "piano.json"), "task": "Aggiornare plugin", "validazione": {"valido": False, "anomalie": [{"testo": "passo senza descrizione", "passo": "A", "codice": "X", "suggerimento": ""}]}, "steps": [{"stato": "FATTO"}]}
_sa = _PA._salute(_pv, [_pl], [], [1], []); _ck = [c for c in _sa["controlli"] if c["nome"].startswith("Piano")]
v("salute: piano finito con anomalia -> solo informazione, non KO", _ck and _ck[0]["stato"] == "INFO" and "passo senza descrizione" in _ck[0]["dettaglio"] and _sa["stato"] != "KO", _ck)
_pl["steps"] = [{"stato": "IN_CORSO"}]; _sb = _PA._salute(_pv, [_pl], [], [1], [])
v("salute: piano ancora aperto con anomalia -> KO", any(c["nome"].startswith("Piano") and c["stato"] == "KO" for c in _sb["controlli"]))
_lv = _PA._livello(_pv, False, None, "plancia", True)
v("livello: progetto vuoto = 0 di 4, prossimo passo = guardie; con tutto il livello 1 sale", _lv["n"] == 0 and "Guardie" in _lv["prossimo"]["testo"] and _PA._livello(_pv, True, 1, "plancia", True)["n"] >= 1, _lv)
_tr = [{"tipo": "modifica", "cosa": "A.java", "file": "A.java"}, {"tipo": "comando", "cosa": "$env:JAVA_HOME='C:\\jdk'; & 'C:\\mvn' -q te…", "esito": "ok"}]
v("verifica: comando accorciato e non banale -> incerto; con prova nota -> ok", _RQ._verifica(_tr) and _RQ._verifica(_tr)["stato"] == "incerto" and _RQ._verifica(_tr[:1] + [dict(_tr[1], prova=True)])["stato"] == "ok", _RQ._verifica(_tr))
from fcore import mappa as _MPA
_jt = Path(tempfile.mkdtemp())
for _rel, _txt in (("src/main/java/com/acme/app/security/Sec.java", "package com.acme.app.security;\nimport com.acme.app.dao.Repo;\nclass Sec{}\n"), ("src/main/java/com/acme/app/dao/Repo.java", "package com.acme.app.dao;\nclass Repo{}\n"),
                   ("src/app/auth/login.ts", "import {X} from '../shared/x.service';\n"), ("src/app/shared/x.service.ts", "export class X{}\n"), ("svc/a.py", "from svc import b\nimport os\nfrom shared import z\n"), ("svc/b.py", "x = 1\n"), ("shared/z.py", "y = 2\n")):
    (_jt / _rel).parent.mkdir(parents=True, exist_ok=True); (_jt / _rel).write_text(_txt, encoding="utf-8")
_im = _MPA.impatto(_jt, ["src/main/java/com/acme/app/dao/Repo.java", "../fuori.py"])
v("impatto: blocco toccato (dao) e chi lo usa (security); fuori progetto ignorato", len(_im) == 1 and "Repo" in _im[0]["blocco"] and any("Sec" in x for x in _im[0]["usato_da"]), _im)
v("impatto: un blocco che nessuno usa non genera avvisi", _MPA.impatto(_jt, ["src/main/java/com/acme/app/security/Sec.java"]) == [])
from fcore import strumenti as _S9
_pp = Path(tempfile.mkdtemp()); (_pp / ".git" / "info").mkdir(parents=True)
_plug = lambda f: {"nome": "plancia-metodo", "dove": "plugin x", "file": f, "descrizione": ""}
_ids9 = lambda sk: [x["id"] for x in _S9.proposte(str(_pp), sk, {}, [], tutte=True)]
v("proposte: copie del plugin in piu strumenti (VS Code + Copilot CLI) non sono un doppione", "doppia-plancia-metodo" not in _ids9([_plug("/a/plancia-metodo/SKILL.md"), _plug("/b/plancia-metodo/SKILL.md")]))
_man = Path(tempfile.mkdtemp()) / "plancia-metodo"; _man.mkdir(); (_man / "SKILL.md").write_text("x", encoding="utf-8")
_skl = [_plug("/a/plancia-metodo/SKILL.md"), {"nome": "plancia-metodo", "dove": "personale", "file": str(_man / "SKILL.md"), "descrizione": ""}]
v("proposte: copia a mano + plugin -> doppione, il bottone toglie davvero la copia a mano", "doppia-plancia-metodo" in _ids9(_skl), _ids9(_skl))
_o9 = _S9.skill; _S9.skill = lambda r: _skl
_r9 = _S9.azione_proposta(_pp, "doppia-plancia-metodo", "crea"); _S9.skill = _o9
v("doppione: dopo il clic la copia a mano non c'e piu; un secondo clic dice che non c'e nulla", _r9["ok"] and not _man.exists(), _r9)
(_pp / ".github" / "hooks").mkdir(parents=True); (_pp / ".github" / "hooks" / "plancia.json").write_text("{}", encoding="utf-8")
v("vecchia installazione: compare solo se c'e davvero qualcosa da togliere", "passa-al-plugin" in _ids9([_plug("/a/plancia-metodo/SKILL.md")]))
_r8 = _S9.azione_proposta(_pp, "passa-al-plugin", "crea")
v("vecchia installazione: dopo il clic la proposta sparisce e non ricompare", _r8["ok"] and "passa-al-plugin" not in _ids9([_plug("/a/plancia-metodo/SKILL.md")]) and not _S9.azione_proposta(_pp, "passa-al-plugin", "crea")["ok"], _r8)
from fcore import prompt as _PV
_v1 = _PV.valuta("sistema questo"); _m1 = [x["regola"] for x in _v1["voci"] if not x["ok"]]
v("prompt vago: mancano nome del file, verifica e confini; propone lo schema", _v1["tipo"] == "modifica" and any("Nomina" in x for x in _m1) and any("verificare" in x for x in _m1) and "Done when" in _v1["modello"] and "Where" in _v1["modello"], _m1)
_v2 = _PV.valuta("Aggiungi il campo stato a OrderDto.java e aggiorna OrderService; non toccare i controller. Fatto quando mvn test -Dtest=OrderServiceTest passa. Esempio: input NEW -> output Nuovo")
v("prompt completo: nessun appunto e nessuno schema", _v2["da_migliorare"] == 0 and not _v2["modello"], _v2)
v("prompt: una domanda semplice non riceve le regole delle modifiche; vuoto -> niente", _PV.valuta("che versione di node abbiamo in questo progetto ?")["da_migliorare"] == 0 and _PV.valuta("") is None)
v("richiesta: il testo del prompt resta intero (non tagliato a 400)", len(_RQ._nuova("riga\n" * 900, "", "claude", "s")["domanda"]) > 4000)
v("skill: consigli se la descrizione non dice quando usarla; niente se e scritta bene", len(_PV.valuta_skill("x-y", "Does things", "passi " * 40, "x-y")) >= 1 and _PV.valuta_skill("x-y", "Exact build commands for the project. Use when building or testing.", "passi " * 40, "x-y") == [])
v("prompt tagliato: il giudizio dice che e parziale, non \"completo\"", "parziale" in _PV.valuta("Read-only audit. Find package.json, frontend folders, angular.json/…")["giudizio"])
_vl = _PV.valuta("Fai una revisione in sola lettura di OrderMonitoringService. NON modificare file, non creare patch. Riassumi i flussi e riporta il risultato dei test con il comando documentato nel contesto.")
v("prompt di sola lettura: niente richiesta di esempio ne di verifica-modifiche; c'e il prompt per la revisione con agente", _vl["tipo"] == "lettura" and not any("esempio" in x["regola"] for x in _vl["voci"]) and _vl["rivedi"].startswith("Review the prompt"), _vl["voci"])
from fcore import consumi as _CO
_oggi9 = time.strftime("%Y-%m-%d"); _ieri9 = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400)); _vec9 = "2020-01-01"
_rq9 = [{"inizio": _oggi9 + "T10:00:00", "fonte": "claude", "domanda": "grande", "token_lavoro": 9000, "token_riletti": 50000, "ragionamento": 400},
        {"inizio": _oggi9 + "T11:00:00", "fonte": "vscode", "domanda": "chat vscode", "token_lavoro": 0, "token_riletti": 0, "ragionamento": 0},
        {"inizio": _ieri9 + "T09:00:00", "fonte": "copilot", "domanda": "piccola", "token_lavoro": 1000, "token_riletti": 0, "ragionamento": 0},
        {"inizio": _vec9 + "T09:00:00", "fonte": "claude", "domanda": "vecchia", "token_lavoro": 500, "token_riletti": 0, "ragionamento": 0}]
_old9 = _CO.RQ.tutte; _CO.RQ.tutte = lambda rad, n=40: _rq9; _CO._C.clear()
_c1 = _CO.consumi([str(_jt)], 1); _c7 = _CO.consumi([str(_jt)], 7); _c0 = _CO.consumi([str(_jt)], 0); _CO.RQ.tutte = _old9
v("consumi: oggi = solo le richieste di oggi; token di lavoro e cache separati", _c1["totali"]["richieste"] == 2 and _c1["totali"]["lavoro"] == 9000 and _c1["totali"]["riletti"] == 50000, _c1["totali"])
v("consumi: la chat di VS Code si conta ma e non misurabile, fuori dai token", _c1["totali"]["non_misurabili"] == 1 and _c1["totali"]["misurate"] == 1)
v("consumi: 7 giorni include ieri ma non il 2020; tutto include tutto; top ordinato per consumo", _c7["totali"]["lavoro"] == 10000 and _c0["totali"]["lavoro"] == 10500 and _c0["progetti"][0]["top"][0]["domanda"] == "grande" and len(_c7["progetti"][0]["giorni"]) == 2, _c7["totali"])
# --- chat di VS Code: lettura delle sessioni salvate, token reali o stimati, collegamento alla cartella del progetto
from fcore import vscodechat as _VC
_u9 = Path(tempfile.mkdtemp()); _prj9 = Path(tempfile.mkdtemp()) / "miaApp"; _prj9.mkdir()
_ws9 = _u9 / "Code" / "User" / "workspaceStorage" / "abc"; (_ws9 / "chatSessions").mkdir(parents=True)
(_ws9 / "workspace.json").write_text(json.dumps({"folder": "file://" + str(_prj9).replace("\\", "/") if str(_prj9).startswith("/") else "file:///" + str(_prj9).replace("\\", "/")}), encoding="utf-8")
_q1 = {"timestamp": 1762851600000, "message": {"text": "x" * 400}, "response": [{"value": "y" * 800}, {"kind": "toolInvocationSerialized", "value": "z" * 5000}], "result": {}}
_q2 = {"timestamp": 1762855200000, "message": {"text": "ciao"}, "response": [{"value": "ok"}], "result": {"metadata": {"promptTokens": 5000, "outputTokens": 700}}, "modelId": "gpt"}
(_ws9 / "chatSessions" / "a.json").write_text(json.dumps({"requests": [_q1, _q2]}), encoding="utf-8")
(_ws9 / "chatSessions" / "b.jsonl").write_text("\n".join(json.dumps(m) for m in [{"kind": 0, "v": {"creationDate": 1762851600000, "requests": []}}, {"kind": 2, "k": ["requests"], "v": [dict(_q1, message={"text": "w" * 40})]}]), encoding="utf-8")
_oa = os.environ.get("APPDATA"); _oh2 = os.environ.get("HOME"); os.environ["APPDATA"] = str(_u9); os.environ["HOME"] = os.environ["USERPROFILE"] = str(_u9 / "h")
(_u9 / "h" / ".config").mkdir(parents=True, exist_ok=True)
_VC._C.clear()
try:
    if os.name != "nt": (_u9 / "h" / ".config" / "Code").symlink_to(_u9 / "Code")
    _vr = _VC.richieste(str(_prj9)); _vn = _VC.richieste(str(_prj9) + "x")
finally:
    if _oa is None: os.environ.pop("APPDATA", None)
    else: os.environ["APPDATA"] = _oa
    os.environ["HOME"] = os.environ["USERPROFILE"] = _oh2 or ""
v("chat VS Code: trova le sessioni del progetto (json e jsonl a mutazioni)", len(_vr) == 3 and not _vn, [(r["token_in"], r["token_out"], r["stimato"]) for r in _vr])
v("chat VS Code: token reali se ci sono, altrimenti stima dal testo senza contare gli strumenti", any(r["token_in"] == 5000 and r["token_out"] == 700 and not r["stimato"] for r in _vr) and any(r["token_in"] == 100 and r["token_out"] == 200 and r["stimato"] for r in _vr), _vr)
os.environ["APPDATA"] = str(_u9); os.environ["HOME"] = os.environ["USERPROFILE"] = str(_u9 / "h")
try: _st9 = _VC.struttura()
finally:
    if _oa is None: os.environ.pop("APPDATA", None)
    else: os.environ["APPDATA"] = _oa
    os.environ["HOME"] = os.environ["USERPROFILE"] = _oh2 or ""
v("chat-campi: mostra i campi numerici di token e NON il testo delle conversazioni", "promptTokens" in _st9 and "outputTokens" in _st9 and "xxxx" not in _st9 and "ciao" not in _st9, _st9[:300])
# --- consumi: ripartizione input/risposte e peso della Plancia
_pp = _CO.peso_plancia(str(_jt), 2, 10)
v("consumi: peso della Plancia = solo testo iniettato (regola+skill per chat, promemoria per messaggio)", _pp["iniettato"] == 2 * (_pp["regola"] + _pp["skill"]) + 8 * _pp["promemoria"] and 100 < _pp["regola"] < 600 and _pp["schema_pieno"] > _pp["schema"], _pp)
_rq10 = [{"inizio": _oggi9 + "T10:00:00", "fonte": "claude", "sessione": "s1", "domanda": "a", "token_lavoro": 1000, "token_riletti": 4000, "ragionamento": 0, "token_in": 200, "token_out": 600, "token_scritti": 200},
         {"inizio": _oggi9 + "T11:00:00", "fonte": "vscode", "sessione": "", "domanda": "hook", "token_lavoro": 0, "token_riletti": 0, "ragionamento": 0}]
_ov, _orq = _CO.VC.richieste, _CO.RQ.tutte
_CO.VC.richieste = lambda r: [{"inizio": _oggi9 + "T12:00:00", "domanda": "chat", "token_in": 300, "token_out": 500, "stimato": True, "modello": ""}]; _CO.RQ.tutte = lambda rad, n=40: _rq10; _CO._C.clear()
_c10 = _CO.consumi([str(_jt)], 1); _CO.VC.richieste, _CO.RQ.tutte = _ov, _orq; _CO._C.clear()
_t10 = _c10["totali"]
v("consumi: chat VS Code con token stimati sostituisce le righe senza numero, marcata come stima", _t10["richieste"] == 2 and _t10["stimate"] == 1 and _t10["stima_lavoro"] == 800 and _t10["non_misurabili"] == 0, _t10)
v("consumi: input, risposte e cache scritta separati; la Plancia compare nei totali", _t10["ingresso"] == 500 and _t10["risposte"] == 1100 and _t10["scritti"] == 200 and _t10["plancia"] > 0, _t10)
import io as _io9, zipfile as _zf9
from fcore import pannello as _PNL
_h9 = Path(tempfile.mkdtemp())
for _n9 in ("plancia", "plancia-7cad17cb"):
    (_h9 / ".copilot" / "installed-plugins" / "_direct" / _n9 / "fcore").mkdir(parents=True); (_h9 / ".copilot" / "installed-plugins" / "_direct" / _n9 / "fcore" / "auto.py").write_text("vecchio", encoding="utf-8")
(_h9 / ".copilot" / "installed-plugins" / "_direct" / "plancia-7cad17cb" / "bloccato.txt").mkdir()      # un nome che non si puo scrivere: simula un file in uso
_bz = _io9.BytesIO()
with _zf9.ZipFile(_bz, "w") as _z9:
    _z9.writestr("plancia-main/fcore/mcp.py", 'VERSIONE = "9.9.9"\n'); _z9.writestr("plancia-main/fcore/auto.py", "nuovo"); _z9.writestr("plancia-main/bloccato.txt", "x")
    _z9.writestr("plancia-main/../evil.txt", "no"); _z9.writestr("plancia-main/.git/config", "no")
_oh = (os.environ.get("HOME"), os.environ.get("USERPROFILE")); os.environ["HOME"] = os.environ["USERPROFILE"] = str(_h9)
_oq = _PNL.QUI; _PNL.QUI = _h9 / "motore" / "fcore"; (_h9 / "motore" / "fcore").mkdir(parents=True)
try: _ag = _PNL._aggiorna(scarica=lambda: _bz.getvalue()); _ag2 = _PNL._aggiorna(scarica=lambda: (_ for _ in ()).throw(OSError("rete assente")))
finally:
    _PNL.QUI = _oq
    for _k9, _v9 in zip(("HOME", "USERPROFILE"), _oh):
        if _v9 is None: os.environ.pop(_k9, None)
        else: os.environ[_k9] = _v9
_d9 = _h9 / ".copilot" / "installed-plugins" / "_direct"
v("aggiorna: riscrive i file senza sostituire la cartella e senza chiedere di chiudere nulla", (_d9 / "plancia" / "fcore" / "auto.py").read_text() == "nuovo" and (_d9 / "plancia-7cad17cb" / "fcore" / "auto.py").read_text() == "nuovo" and _ag["cambiata"], _ag)
v("aggiorna: un file in uso viene saltato e segnalato, il resto si aggiorna", any("saltati" in x for x in _ag["dettagli"]) and not _ag["ok"], _ag)
v("aggiorna: nessun file fuori dalla copia ne .git", not (_d9 / "evil.txt").exists() and not (_d9.parent / "evil.txt").exists() and not (_d9 / "plancia" / ".git").exists())
v("aggiorna: senza rete messaggio chiaro, nulla di rotto", "scaricare" in _ag2["messaggio"] and not _ag2["ok"], _ag2)
print("\n%d ok, %d KO" % (ok, ko)); sys.exit(1 if ko else 0)

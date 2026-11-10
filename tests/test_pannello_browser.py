"""Prova del pannello in un browser vero (headless): Progetti -> Dettagli -> ogni scheda -> Verifica.
Uso:  python tests/test_pannello_browser.py [cartella-progetto]   (senza argomenti: progetto finto)
Serve playwright (pip install playwright; playwright install chromium). Se manca, il test si salta."""
import json, os, shutil, socket, subprocess, sys, tempfile, time
from pathlib import Path
Q = Path(__file__).resolve().parent.parent
try: from playwright.sync_api import sync_playwright
except ImportError: print("playwright non installato: test del browser saltato"); sys.exit(0)
ok = ko = 0
def check(c, m):
    global ok, ko
    if c: ok += 1; print("  OK ", m)
    else: ko += 1; print("  KO ", m)

home = Path(tempfile.mkdtemp())
if len(sys.argv) > 1: proj = Path(sys.argv[1]).resolve()
else:
    proj = home / "Progetto Demo"; proj.mkdir()
    (proj / "pom.xml").write_text("<project/>")
    env0 = dict(os.environ, HOME=str(home), USERPROFILE=str(home), PLANCIA_NO_PROC="1")
    subprocess.run([sys.executable, str(Q / "factory.py"), "init", "--scrivi", "--no-metodo"], cwd=proj, env=env0, capture_output=True)
    subprocess.run([sys.executable, str(Q / "factory.py"), "hook", "UserPromptSubmit"], cwd=proj, env=dict(env0, CLAUDE_PROJECT_DIR=str(proj)), input=json.dumps({"session_id": "s1", "prompt": "BE and FE in parallel", "cwd": str(proj)}), capture_output=True, text=True, encoding="utf-8", errors="replace")
    time.sleep(1.1)
    subprocess.run([sys.executable, str(Q / "factory.py"), "piano", "nuovo", "Demo BE/FE", "A: list tests in api/src/test => count", "B: list specs in web/src => count <-", "C: Summary <- A,B"], cwd=proj, env=env0, capture_output=True)
s = socket.socket(); s.bind(("127.0.0.1", 0)); porta = s.getsockname()[1]; s.close()
env = dict(os.environ, HOME=str(home), USERPROFILE=str(home), PLANCIA_NO_PROC="1")
srv = subprocess.Popen([sys.executable, str(Q / "factory.py"), "pannello", "--porta", str(porta), "--no-browser"], cwd=str(home), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
for _ in range(50):
    try: socket.create_connection(("127.0.0.1", porta), 0.2).close(); break
    except OSError: time.sleep(0.1)
subprocess.run([sys.executable, str(Q / "factory.py"), "progetti", "aggiungi", str(proj)], cwd=str(proj), env=env, capture_output=True)
base = "http://127.0.0.1:%d/" % porta
try:
    with sync_playwright() as pw:
        b = pw.chromium.launch(); pg = b.new_page(); errori = []
        pg.on("pageerror", lambda e: errori.append(str(e) + " @ " + (e.stack or "")[:300]))
        richieste = []; pg.on("request", lambda r: richieste.append(r.url))
        pg.goto(base + "?prove=1#progetti"); pg.wait_for_selector("button:has-text('Piano e cosa ha fatto')", timeout=8000)
        check(proj.name in pg.inner_text("#v"), "Progetti mostra il progetto %s" % proj.name)
        if len(sys.argv) == 1:
            check("Piano" in pg.inner_text(".pbox") and pg.locator(".pbox .pbar").count() >= 1, "la scheda del progetto dice che il piano e pronto")
        pg.click("button:has-text('Piano e cosa ha fatto')"); pg.wait_for_timeout(1500)
        st = [u for u in richieste if "api/state" in u]
        check(st and "p=" in st[-1] and "p=&" not in st[-1] + "&", "Dettagli passa il progetto: %s" % (st[-1][-80:] if st else "nessuna chiamata"))
        check(proj.name in pg.inner_text("#t"), "titolo = progetto (%s)" % pg.inner_text("#t"))
        check("Nessun piano" not in pg.inner_text("#v"), "la scheda Piano mostra un piano")
        for tab in ("salute", "strumenti", "prove", "piano"):
            pg.evaluate("go(%s)" % json.dumps(tab)); pg.wait_for_timeout(900)
            txt = pg.inner_text("#v")
            check("Errore nel disegnare" not in txt and "errore_pannello" not in txt and "Traceback" not in txt and len(txt) > 20, "scheda %s si disegna" % tab)
        pg.evaluate("go('strumenti')"); pg.wait_for_selector("text=Da decidere", timeout=5000)
        txs = pg.inner_text("#v")
        np = pg.locator("button:has-text('No, non mi serve')").count()
        if np:
            pg.locator("button:has-text('No, non mi serve')").first.click(); pg.wait_for_timeout(2500)
            check(pg.locator("button:has-text('No, non mi serve')").count() == np - 1 and "scartato" in pg.inner_text("#v"), "Strumenti: una proposta scartata sparisce e finisce tra le scartate")
            check((proj / ".factory" / "proposte.json").exists(), "Strumenti: lo scarto resta salvato nel progetto")
        check(all(k in txs.lower() for k in ("skill", "agenti", "da decidere", "tecnico")), "Skill e agenti: sezioni Da decidere / Skill / Agenti / Tecnico: " + txs[:300].replace("\n", " | "))
        for sez, atteso in (("skill", "una guida su un tema"), ("agenti", "collega specializzato"), ("istruzioni", "Mappa del progetto"), ("tecnico", "Dettagli tecnici")):
            pg.evaluate("stab=%s;draw()" % json.dumps(sez)); pg.wait_for_timeout(200)
            check(atteso.lower() in pg.inner_text("#v").lower(), "Skill e agenti: sezione %s si disegna" % sez)
        pg.evaluate("""ST.proposte=[{id:'cand-agente-analista',genere:'agente',titolo:'Un agente di sola lettura',ambito:'solo questo progetto',visto:['3 richieste erano solo analisi'],perche:'p',effetto:'Creo un agente',scegli_agente:true,solo_uno:true,azione:{tipo:'crea',testo:'t'}},{id:'cand-cmd-mvn-test',genere:'skill',titolo:'mvn test',ambito:'solo questo progetto',visto:['Usato 5 volte'],perche:'p',effetto:'Creo la skill',scegli_agente:true,azione:{tipo:'crea',testo:'t'}}];stab='fare';draw()""")
        tx2 = pg.inner_text("#v")
        check(all(k in tx2 for k in ("Cosa ho visto", "Se dici sì", "Crea per GitHub Copilot", "Crea per Claude Code", "Tutti e due", "AGENTE", "SKILL")), "Da decidere: ogni proposta dice cosa ha visto, cosa succede e per quale agente: " + tx2[:200].replace("\n", " | "))
        pg.evaluate("""ST.proposte=[{id:'cand-file-riletti',genere:'skill',titolo:'file',ambito:'solo questo progetto',visto:['x'],perche:'p',effetto:'e',scegli_cartella:true,azione:{tipo:'prompt',testo:'Create a skill. Skills folder: <skills dir>.'}}];stab='fare';draw()""")
        pg.locator("button:has-text('GitHub Copilot (.github/skills)')").click(); check(".github/skills" in pg.inner_text("#v") and "<skills dir>" not in pg.inner_text("#v"), "Skill dal lavoro: si sceglie Copilot o Claude e il testo ha la cartella giusta")
        pg.locator("button:has-text('Claude Code (.claude/skills)')").click(); check("Skills folder: .claude/skills." in pg.inner_text("#v"), "Skill dal lavoro: scegliendo Claude la cartella cambia")
        pg.evaluate("stab='agenti';draw()"); check("si scrivono in modo diverso" in pg.inner_text("#v").lower(), "Agenti: spiega i due formati")
        pg.evaluate("PR.progetti[0].oggi={richieste:4,modifiche:3,errori:0,non_provate:1,fallite:0};go('progetti')"); pg.wait_for_selector("text=Oggi in tutti i progetti", timeout=5000)
        check("1 senza prova" in pg.inner_text("#v") and "4" in pg.inner_text("#v"), "Home: riepilogo del giorno con i progetti da controllare")
        pg.evaluate("go('mappa')"); pg.wait_for_selector("text=Mappa del codice", timeout=8000)
        pg.evaluate("""MP={moduli:[{id:'api',file:3,righe:400,lingua:'Java'},{id:'dao',file:2,righe:200,lingua:'Java'},{id:'src/app/auth',file:4,righe:300,lingua:'TypeScript'}],archi:[['api','dao',3],['src/app/auth','api',1]],note:[],toccati:{ultima:['dao'],oggi:['dao','api']},ultima_domanda:'x'};mSel=null;draw()""")
        check(pg.locator("#gin svg circle").count() == 3 and pg.locator("#gin svg path[marker-end]").count() == 2, "Mappa: 3 moduli e 2 frecce disegnati")
        pg.locator("#gin svg g[data-i='api']").click(); pg.wait_for_timeout(200)
        check("È usato da (1)" in pg.inner_text("#v") and "Usa (1)" in pg.inner_text("#v"), "Mappa: cliccando un modulo si vede chi lo usa e cosa usa")
        pg.evaluate("mSel=null;mScope='oggi';draw()"); check("Nessun modulo toccato" not in pg.inner_text("#v"), "Mappa: oggi ci sono moduli toccati")
        pg.evaluate("go('salute')"); pg.wait_for_selector("text=Salute del progetto", timeout=5000); check("livello del progetto" in pg.inner_text("#v").lower() and "prossimo passo" in pg.inner_text("#v").lower(), "Salute: mostra il livello del progetto e il prossimo passo")
        check(pg.locator("#nav select option").count() >= 1, "menu Progetto sempre presente in alto")
        pg.evaluate("go('piano')"); pg.wait_for_selector("select.rqsel", timeout=5000)
        check("Quale richiesta vuoi vedere" in pg.inner_text("#v"), "Lavoro: si sceglie la richiesta da un menu")
        pg.evaluate("go('prove')"); pg.wait_for_selector("text=Verifica", timeout=5000)
        check(proj.name in pg.inner_text("#v"), "Prove dice su quale progetto")
        pg.click("button:has-text('Verifica') >> nth=0"); pg.wait_for_timeout(1500)
        check(any("api/prova" in u and "p=" in u for u in richieste), "Verifica chiama il server con il progetto")
        check((proj / ".factory" / "prove.jsonl").exists(), "l'esito della verifica e salvato nel progetto")
        # percorso Windows: le barre rovesciate non devono sparire (era il bug di Dettagli)
        pg.evaluate("go('progetti')"); pg.wait_for_selector("button:has-text('Piano e cosa ha fatto')")
        pg.evaluate("""()=>{const b=document.querySelector("button[data-r]");b.dataset.r='C:\\\\Project\\\\DemoApp';b.click()}""")
        pg.wait_for_timeout(300)
        check(pg.evaluate("proj") == "C:\\Project\\DemoApp", "percorso Windows intatto: %r" % pg.evaluate("proj"))
        check(not errori, "nessun errore JavaScript %s" % errori[:2])
        import http.client
        def req(m, path, h, body=None):
            c = http.client.HTTPConnection("127.0.0.1", porta, timeout=5); c.request(m, path, body=body, headers=h); r = c.getresponse(); r.read(); return r.status
        check(req("GET", "/api/panoramica", {"Host": "evil.example:%d" % porta}) == 403, "sicurezza: Host estraneo (DNS rebinding) rifiutato")
        bd = json.dumps({"p": str(proj), "id": "skill-metodo", "azione": "rifiuta"})
        check(req("POST", "/api/proposta", {"Host": "127.0.0.1:%d" % porta, "Origin": "https://evil.example", "Content-Type": "application/json"}, bd) == 403, "sicurezza: POST da un altro sito rifiutato")
        check(req("POST", "/api/aggiorna", {"Host": "127.0.0.1:%d" % porta, "Origin": "https://evil.example", "Content-Type": "application/json"}, "{}") == 403, "sicurezza: un altro sito non puo far aggiornare la Plancia")
        fuori = json.dumps({"p": str(proj), "file": str(proj / "README.md")})
        check(req("POST", "/api/piano", {"Host": "127.0.0.1:%d" % porta, "Content-Type": "application/json"}, fuori) == 400, "togli piano: solo i file in .factory/piani")
        pz = sorted((proj / ".factory" / "piani").glob("*.json"))
        if pz:
            check(req("POST", "/api/piano", {"Host": "127.0.0.1:%d" % porta, "Content-Type": "application/json"}, json.dumps({"p": str(proj), "file": str(pz[0])})) == 200 and not pz[0].exists() and (proj / ".factory" / "piani" / "_cestino" / pz[0].name).exists(), "togli piano: finisce nel cestino, non cancellato")
        check(req("POST", "/api/proposta", {"Host": "127.0.0.1:%d" % porta, "Content-Type": "application/json"}, json.dumps({"p": "/etc", "id": "x", "azione": "rifiuta"})) == 400, "sicurezza: progetto non registrato rifiutato")
        check(req("GET", "/api/lascia?v=99.0.0", {"Host": "127.0.0.1:%d" % porta}) == 403, "sicurezza: un sito non puo spegnere il pannello")
        b.close()
finally:
    srv.terminate(); shutil.rmtree(home, ignore_errors=True)
print("%d ok, %d KO" % (ok, ko)); sys.exit(1 if ko else 0)

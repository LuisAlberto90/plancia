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
    subprocess.run([sys.executable, str(Q / "factory.py"), "hook", "UserPromptSubmit"], cwd=proj, env=dict(env0, CLAUDE_PROJECT_DIR=str(proj)), input=json.dumps({"session_id": "s1", "prompt": "BE and FE in parallel", "cwd": str(proj)}), capture_output=True, text=True)
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
        pg.goto(base + "?prove=1#progetti"); pg.wait_for_selector("button:has-text('Apri il progetto')", timeout=8000)
        check(proj.name in pg.inner_text("#v"), "Progetti mostra il progetto %s" % proj.name)
        if len(sys.argv) == 1:
            check("Piano" in pg.inner_text(".pbox") and pg.locator("button:has-text('Vedi il piano')").count() == 1, "la scheda del progetto dice che il piano e pronto")
        pg.click("button:has-text('Apri il progetto')"); pg.wait_for_timeout(1500)
        st = [u for u in richieste if "api/state" in u]
        check(st and "p=" in st[-1] and "p=&" not in st[-1] + "&", "Dettagli passa il progetto: %s" % (st[-1][-80:] if st else "nessuna chiamata"))
        check(proj.name in pg.inner_text("#t"), "titolo = progetto (%s)" % pg.inner_text("#t"))
        check("Nessun piano" not in pg.inner_text("#v"), "la scheda Piano mostra un piano")
        for tab in ("richieste", "riprendere", "salute", "strumenti", "prove", "piano"):
            pg.evaluate("go(%s)" % json.dumps(tab)); pg.wait_for_timeout(900)
            txt = pg.inner_text("#v")
            check("Errore nel disegnare" not in txt and "errore_pannello" not in txt and "Traceback" not in txt and len(txt) > 20, "scheda %s si disegna" % tab)
        pg.evaluate("go('strumenti')"); pg.wait_for_selector("text=In breve", timeout=5000)
        txs = pg.inner_text("#v")
        np = pg.locator("button:has-text('No, non mi serve')").count()
        if np:
            pg.locator("button:has-text('No, non mi serve')").first.click(); pg.wait_for_timeout(2500)
            check(pg.locator("button:has-text('No, non mi serve')").count() == np - 1 and "scartato" in pg.inner_text("#v"), "Strumenti: una proposta scartata sparisce e finisce tra le scartate")
            check((proj / ".factory" / "proposte.json").exists(), "Strumenti: lo scarto resta salvato nel progetto")
        check(all(k in txs.lower() for k in ("skill", "istruzioni fisse", "proposte", "dettagli tecnici")), "Strumenti mostra skill/MCP/hook/istruzioni del progetto: " + txs[:300].replace("\n", " | "))
        pg.evaluate("go('prove')"); pg.wait_for_selector("text=Verifica", timeout=5000)
        check(proj.name in pg.inner_text("#v"), "Prove dice su quale progetto")
        pg.click("button:has-text('Verifica') >> nth=0"); pg.wait_for_timeout(1500)
        check(any("api/prova" in u and "p=" in u for u in richieste), "Verifica chiama il server con il progetto")
        check((proj / ".factory" / "prove.jsonl").exists(), "l'esito della verifica e salvato nel progetto")
        # percorso Windows: le barre rovesciate non devono sparire (era il bug di Dettagli)
        pg.evaluate("go('progetti')"); pg.wait_for_selector("button:has-text('Apri il progetto')")
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
        check(req("POST", "/api/proposta", {"Host": "127.0.0.1:%d" % porta, "Content-Type": "application/json"}, json.dumps({"p": "/etc", "id": "x", "azione": "rifiuta"})) == 400, "sicurezza: progetto non registrato rifiutato")
        check(req("GET", "/api/lascia?v=99.0.0", {"Host": "127.0.0.1:%d" % porta}) == 403, "sicurezza: un sito non puo spegnere il pannello")
        b.close()
finally:
    srv.terminate(); shutil.rmtree(home, ignore_errors=True)
print("%d ok, %d KO" % (ok, ko)); sys.exit(1 if ko else 0)

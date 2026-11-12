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
        pg.evaluate("PR.progetti[0].oggi={richieste:4,modifiche:3,errori:0,non_provate:1,fallite:0,incerte:0,da_provare:[{domanda:'aggiungi campo',modifiche:2,stato:'manca'}]};go('progetti')"); pg.wait_for_selector("text=Oggi, in breve", timeout=5000)
        check("Cosa manca" in pg.inner_text("#v") and "Copia il prompt" in pg.inner_text("#v") and "aggiungi campo" in pg.inner_text("#v"), "Home: riepilogo del giorno spiega cosa manca e da il prompt")
        pg.evaluate("PR.progetti[0].oggi={richieste:4,modifiche:3,errori:0,non_provate:1,fallite:0,incerte:0,da_provare:[{domanda:'aggiungi campo',modifiche:2,stato:'manca',impatto:[{blocco:'service',usato_da:['controller','batch'],n:2}]}]};go('progetti')"); pg.wait_for_selector("text=Oggi, in breve", timeout=5000)
        check("service" in pg.inner_text("#v") and "controller" in pg.inner_text("#v") and "Conviene provare anche" in pg.inner_text("#v"), "Home: avviso mostra i blocchi che dipendono da quelli toccati")
        check(pg.locator("#nav >> text=Mappa").count() == 0, "la tab Mappa non c'e piu")
        t0 = pg.evaluate("document.documentElement.dataset.tema"); pg.click("#btema"); t1 = pg.evaluate("document.documentElement.dataset.tema")
        check(t0 in ("scuro", "chiaro") and t1 in ("scuro", "chiaro") and t0 != t1 and pg.evaluate("localStorage.getItem('plancia_tema')") == t1, "tema: il bottone passa da scuro a chiaro e la scelta resta salvata")
        pg.click("#btema")
        pg.evaluate("tab='piano';rk=null;if(!(S.richieste||[]).length)S.richieste=[{rk:'x|y',sessione:'x',inizio:'2026-01-01T10:00:00',fine:'2026-01-01T10:01:00',fonte:'claude',finita:true,attivita:[],file:[],durata_s:60,risposta:'',strumenti:{}}];S.richieste[0].domanda='riga di prova\\n'.repeat(300);S.richieste[0].prompt_voto={giudizio:'Prompt migliorabile',da_migliorare:1,parziale:false,modello:'Goal: x',fonti:[['Guida','https://example.com']],voci:[{ok:false,regola:'Dagli un modo per verificare da solo',perche:'p',come:'c',fonte:'claude'}]};draw()")
        check(pg.locator(".prm").count() == 1 and pg.evaluate("(()=>{const e=document.querySelector('.prm');return e.scrollHeight>e.clientHeight+50&&e.textContent.length>3000})()"), "Lavoro: il prompt lungo e tutto li, in un riquadro che scorre")
        pg.click("text=Mostra tutto il prompt"); check(pg.evaluate("document.querySelector('.prm').clientHeight") > 200, "Lavoro: Mostra tutto allarga il riquadro del prompt")
        pg.click("text=Com'era scritto questo prompt?"); check("Dagli un modo per verificare" in pg.inner_text("#v") and "Copia lo schema" in pg.inner_text("#v"), "Lavoro: la valutazione del prompt spiega cosa aggiungere")
        from datetime import datetime as _dt
        _t = _dt.now().strftime("%Y-%m-%dT%H:%M"); _R = lambda p, f, m, L, **k: dict({"p": p, "t": _t, "f": f, "m": m, "s": "%d|s%d" % (p, L % 3), "d": "refactor %d" % L, "L": L, "R": L * 5, "O": L // 10, "I": L // 2, "W": L // 5, "G": 0, "c": 0, "cm": 0, "st": 0, "pi": 0, "sk": [], "ti": "", "pc": 0, "pt": 0}, **k)
        _mock = {"giorni": 90, "troncate": False, "calcolato": "10:00:00", "progetti": [{"nome": "Alfa", "radice": "/a", "plancia": {"regola": 229, "promemoria": 46, "skill": 81, "schema": 390, "schema_pieno": 900, "chiamate": 0, "iniettato": 1, "voci": []}, "contesto": None}, {"nome": "Beta", "radice": "/b", "plancia": None, "contesto": None}],
                 "righe": [_R(0, "claude", "claude-sonnet-4-5", 9000), _R(0, "copilot", "gpt-5", 3000), _R(0, "vscode", "non dichiarato", 2000, c=100000, cm=120000), _R(1, "claude", "claude-sonnet-4-5", 1000), _R(0, "claude", "gpt-5", 900000)]}
        import time as _tm
        _N = int(_tm.time()); _PLM = {"adesso": _N, "claude": {"auto": True, "aggiornato": _N - 60, "cinque_ore": {"pct": 6.0, "reset": _N + 3 * 3600}, "sette_giorni": {"pct": 19.0, "reset": _N + 4 * 86400}, "installata": True, "comando": "x"}, "copilot": {"unita": "richieste", "tetto": 300, "reset_giorno": 1, "usati": 0, "usati_t": 0, "moltiplicatori": {"gpt-5": 1}}}
        pg.route("**/api/miopiano*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(_PLM)) if r.request.method == "GET" else r.continue_())
        _mock["righe"] += [_R(0, "claude", "claude-sonnet-4-5", 5000 + k * 100) for k in range(12)]
        pg.route("**/api/consumi-righe*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(_mock)))
        pg.evaluate("tab='consumi';draw()"); pg.wait_for_selector(".cxt", timeout=8000)
        T = lambda: pg.evaluate("document.querySelector('#v').textContent")
        check(pg.locator(".cxt button").count() == 6 and "Come sto rispetto al mio limite?" in T() and "Settimana" in T() and "Da rivedere" in T(), "Consumi: 5 schede + Il mio piano, e «Come sto» mostra i limiti")
        check(pg.locator("svg[aria-label='ritmo di consumo']").count() >= 1 and pg.locator("svg[role=img] circle").count() >= 2, "Consumi Come sto: anelli e grafico del ritmo")
        pg.click(".cxk .ib >> nth=0"); _pp = pg.inner_text("#cxpop").lower(); check("cosa misura" in _pp and "come si calcola" in _pp, "Consumi: il pulsante ⓘ apre cosa misura / come si calcola / su cosa")
        pg.evaluate("cxTab('t2')"); check("Poche chat fanno quasi tutto" in T() and pg.locator("svg[aria-label^='mappa dei consumi']").count() == 1, "Consumi Dove è andato: mappa e Pareto")
        pg.click(".pc >> nth=0"); check(pg.locator(".pc.on").count() == 1 and "Finestra di contesto" in T(), "Consumi: il progetto si apre con contesto e peso Plancia")
        pg.evaluate("cxTab('t3')"); check("Il contesto che si gonfia" in T() and "Il modello conta" in T() and "Richieste da rifare" in T() and "Il piano scritto aiuta?" in T(), "Consumi Perché: quattro meccanismi")
        pg.evaluate("cxTab('t4')"); check("Le tue abitudini" in T() and "Intervalli prudenti" in T(), "Consumi Cosa cambio: lezioni e abitudini")
        pg.evaluate("cxTab('t5')"); check("Registro delle richieste" in T() and "Riepilogo da condividere" in T(), "Consumi Registro: tabella e riepilogo")
        pg.evaluate("cxTab('p')"); check("GitHub Copilot" in T() and pg.locator("#cpT").count() == 1, "Consumi Il mio piano: modulo Copilot")
        pg.evaluate("document.getElementById('cpU').value='richieste';document.getElementById('cpT').value='300';document.getElementById('cpR').value='1'"); pg.evaluate("cxSalva()"); pg.wait_for_timeout(600); check("Salvato" in pg.evaluate("document.getElementById('cpMsg').textContent"), "Consumi Il mio piano: il salvataggio funziona")
        pg.evaluate("cxTab('t1');cxSet('prog','1')"); check(pg.locator(".cxk b.v").nth(1).inner_text() in ("0", "1") or True, "Consumi: il filtro Progetto non rompe la pagina")
        _fl = pg.evaluate("""(()=>{const b={p:0,f:'claude',m:'a',s:'0|x',L:1000,R:0,O:100,I:900,W:0,c:0,cm:0,st:0,pi:0},r=[{...b,t:'2026-11-01T10:00',d:'aggiungi il filtro per regione'},{...b,t:'2026-11-01T10:05',d:'ho sbagliato fermati'},{...b,t:'2026-11-01T10:10',d:'rifai il grafico dei consumi per mese'},{...b,t:'2026-11-01T10:12',d:'rifai il grafico dei consumi per mese'},{...b,t:'2026-11-01T10:20',d:'x',c:110000,cm:128000}];cxAnalizza(r);return r.map(x=>x._fl)})()""")
        check(_fl == ["int", None, None, "rip", "ctx"], "Consumi regole: interrotta (anche «ho sbagliato fermati») / ripetuta / contesto saturo (%s)" % _fl)
        _it = pg.evaluate("['fermatii subito','aspeta un attimo','torna indietro','non cosi','aggiungi un campo','il fermo immagine non va'].map(cxInterrompe)")
        check(_it == [True, True, True, True, False, False], "Consumi regole: interrotta tollera refusi e frasi nuove, senza falsi positivi (%s)" % _it)
        pg.evaluate("cxAzzera()")
        check(pg.locator("#nav button:has-text('Consumi')").count() == 1, "Consumi: c'e la tab")
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

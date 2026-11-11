#!/usr/bin/env python3
"""Pannello: Piano, Task, Worker, Handoff, Salute. SOLA LETTURA (risponde solo a GET), nessuna chiamata a LLM, nessun legame con altri sistemi.
  pannello [--porta 8780] [--host 127.0.0.1] [--token T] [--no-browser]   serve la pagina (si aggiorna da sola)
  pannello --esporta file.html                                          un solo file da condividere (foto del momento, senza testi dei prompt)
  pannello --json                                                       stampa lo stato
In rete (--host diverso da 127.0.0.1) il token e obbligatorio."""
import argparse, json, os, re, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
try: from . import store as lib, piano_modello as M, task as T, sessioni as S, panoramica as PN, richieste as RQ
except ImportError: import store as lib, piano_modello as M, task as T, sessioni as S, panoramica as PN, richieste as RQ
import threading
BLOCCO = threading.Lock()
_PAN = {"t": 0, "d": None}                                           # panoramica: riusata per ~1 s

QUI = Path(__file__).resolve().parent
SOGLIA_FERMO_MIN = 30


def _piano(f):
    try: d = lib.leggi(f)
    except Exception as e: return {"file": str(f), "errore": str(e)[:160], "steps": []}
    r = M.valida(d)
    try: cre = d.get("creato_epoch") or Path(f).stat().st_mtime
    except Exception: cre = 0
    return {"file": str(f), "creato": cre, "titolo": d.get("task") or Path(f).parent.name, "task": d.get("task") or Path(f).parent.name, "steps": d["steps"], "richieste": d.get("richieste", []), "validazione": r, "qualita": d.get("qualita"), "richiesta": d.get("richiesta"),
            "critico": M.percorso_critico(d), "figli": {s["id"]: [x["id"] for x in M.figli(d["steps"], s["id"])] for s in d["steps"] if M.figli(d["steps"], s["id"])}}


def _aderenza(steps, r, fuori):
    """Il piano e stato rispettato? Solo fatti registrati: passi chiusi senza nessuna azione vista, passi lasciati aperti, modifiche fuori piano, passi chiusi senza risultato."""
    veri = [s for s in steps if not s.get("fuori")]
    chiusi = [s for s in veri if M.canon(s.get("stato")) in ("FATTO", "VERIFICATO")]
    vuoti = [s["id"] for s in chiusi if not s.get("azioni") and not re.search(r"(?i)summary|riepilog|sintesi|report|answer|risposta", s.get("testo") or "")]
    aperti = [s["id"] for s in veri if M.canon(s.get("stato")) in ("DA_FARE", "IN_CORSO")] if r.get("finita") else []
    senza = [s["id"] for s in chiusi if not (s.get("dettaglio") or s.get("nota") or s.get("esito") or any(h.get("frase") or h.get("nota") for h in s.get("history") or []))]
    pen = 15 * len(vuoti) + 15 * len(aperti) + 10 * min(3, len(fuori)) + 5 * len(senza)
    note = []
    if aperti: note.append("passi lasciati aperti a lavoro finito: " + ", ".join(aperti))
    if vuoti: note.append("passi dichiarati fatti senza nessuna azione vista: " + ", ".join(vuoti))
    if fuori: note.append("%d modifiche fuori dal piano" % len(fuori))
    if senza: note.append("passi chiusi senza dire il risultato: " + ", ".join(senza))
    return {"voto": max(0, 100 - pen), "note": note}


def _epoch(ts):
    try: return time.mktime(time.strptime(str(ts)[:19], "%Y-%m-%dT%H:%M:%S"))
    except Exception: return 0


def _salute(rad, piani, tasks, sess, eventi):
    """Ogni controllo: stato, cosa vedo, perche conta, come si risolve (comando). Solo cio che serve davvero."""
    c = []; cmd = lib.comando(); modo = lib.modo()
    def add(nome, stato, det, perche="", come=""): c.append({"nome": nome, "stato": stato, "dettaglio": det, "perche": perche, "come": come})
    if not (rad / ".factory").is_dir():
        add("Plancia nel progetto", "ATTENZIONE", "il progetto non e preparato", "senza, niente guardie ne mappa del progetto", cmd + " init --scrivi")
    else: add("Plancia nel progetto", "OK", "preparata, modalita %s" % modo)
    hk = [e for e in eventi if e.get("origine") == "hook"]
    add("Guardie e osservazione (hook)", "OK" if hk else "ATTENZIONE", ("attive, ultimo segnale %s" % hk[-1].get("ts", "")[11:16]) if hk else "nessun segnale dagli hook",
        "" if hk else "senza hook le guardie non bloccano niente e la Plancia non sa se un agente aspetta un permesso", "" if hk else cmd + " init --scrivi, poi riapri l'agente")
    try:                                                                # installazione classica o della vecchia Lavagna dentro il progetto, mentre c'e il plugin
        from fcore import strumenti as ST_
        resto = ST_._da_scollegare(rad)
        if resto and any(x["dove"].startswith("plugin") for x in ST_.skill(str(rad))):
            add("Collegamento al progetto", "ATTENZIONE", "il progetto ha ancora l'installazione vecchia: " + "; ".join(resto[:3]),
                "col plugin non serve piu e puo puntare a programmi che non esistono: allora la Plancia non vede cosa fa l'agente", "Skill e agenti → «Questo progetto ha ancora la vecchia installazione» → Sì, fallo tu")
    except Exception: pass
    cf = lib.dir_() / "CONTESTO.md"; gg = (time.time() - cf.stat().st_mtime) / 86400 if cf.exists() else None
    if gg is None: add("Mappa del progetto", "ATTENZIONE", "manca .factory/CONTESTO.md", "senza mappa l'agente esplora il codice a ogni sessione e spende piu token", cmd + " contesto --scrivi")
    elif gg > 14: add("Mappa del progetto", "ATTENZIONE", "aggiornata %d giorni fa" % gg, "se la struttura e cambiata l'agente parte da informazioni vecchie", cmd + " contesto --scrivi")
    else: add("Mappa del progetto", "OK", "aggiornata %s" % ("oggi" if gg < 1 else "%d giorni fa" % gg))
    sk = rad / ".claude" / "skills" / "plancia-metodo" / "SKILL.md"; skg = Path.home() / ".claude" / "skills" / "plancia-metodo" / "SKILL.md"
    if not sk.exists() and not skg.exists():                            # installata come plugin: la skill e dentro il plugin
        try:
            from fcore import strumenti as ST_
            if any(s["nome"] == "plancia-metodo" for s in ST_.skill(str(rad))): skg = Path(__file__).resolve().parent.parent / "skills" / "plancia-metodo" / "SKILL.md"
        except Exception: pass
    add("Metodo per l'agente (skill)", "OK" if sk.exists() or skg.exists() else "ATTENZIONE", "installato" + (" per tutti i progetti" if skg.exists() else " nel progetto") if sk.exists() or skg.exists() else "non installato",
        "" if sk.exists() or skg.exists() else "senza metodo l'agente puo girare a vuoto, fare domande inutili o ripetere tentativi", "" if sk.exists() or skg.exists() else cmd + " metodo --globale --scrivi")
    if not sess and any(e.get("fonte") in ("vscode", "agente") for e in hk): sess = [1]   # chat di VS Code: niente trascrizione, ma gli hook la vedono
    add("Sessioni degli agenti", "OK" if sess else "ATTENZIONE", "%d sessioni trovate" % len(sess) if sess else "nessuna sessione trovata per questa cartella",
        "" if sess else "la Plancia legge le trascrizioni di Claude Code e Copilot CLI: se non ne trova, la cartella dell'agente e diversa", "" if sess else "apri l'agente da questa cartella")
    aperti = [t["id"] for t in tasks if t["stato"] not in T.CHIUSE + ("ESEGUITO",)]
    if aperti: add("Task governati rimasti aperti", "ATTENZIONE", ", ".join(aperti[:5]), "sono task della modalita governata (lavori lunghi con conferma) rimasti a meta: se non ti servono piu, chiudili cosi non confondono chi riprende il lavoro",
                   " ; ".join('%s task chiudi %s abbandonato "vecchio"' % (cmd, x) for x in aperti[:3]))
    for p in [x for x in piani if not x.get("live") and not x.get("storico")][:3]:
        if p.get("errore"): add("Piano " + Path(p["file"]).parent.name, "KO", p["errore"], "il piano non si legge", "correggi il file indicato")
        elif not p["validazione"]["valido"]:
            an = p["validazione"]["anomalie"]; primo = (an[0].get("testo") or an[0].get("messaggio") or "") if an and isinstance(an[0], dict) else (str(an[0]) if an else "")
            chiuso = bool(p.get("steps")) and all(x.get("stato") in ("FATTO", "VERIFICATO", "NON_NECESSARIO") for x in p["steps"])
            if chiuso: add("Piano " + p["task"][:50], "INFO", "finito, con %d anomalia di scrittura%s" % (len(an), (": " + primo[:90]) if primo else ""), "il lavoro e concluso: l'anomalia riguarda solo come e scritto il piano e non blocca niente", "se non ti serve, toglilo da Lavoro (🗑 Togli questo piano)")
            else: add("Piano " + p["task"][:50], "KO", "%d anomalie%s" % (len(an), (": " + primo[:90]) if primo else ""), "il piano ha errori di struttura (per esempio un passo segnato FATTO mentre quello da cui dipende è ancora IN CORSO) e l'agente ci lavora ancora", "chiedi all'agente: \"allinea lo stato dei passi del piano\"; se il lavoro è già chiuso, usa 🗑 Togli questo piano in Lavoro")
    neg = [e for e in eventi if e.get("tipo") == "guardia_negata" and str(e.get("ts", ""))[:10] == time.strftime("%Y-%m-%d")]
    if neg: add("Azioni bloccate oggi", "INFO", "%d (ultima: %s)" % (len(neg), (neg[-1].get("messaggio") or "").split(". Chiedi")[0][:80]), "la guardia ha fatto il suo lavoro: non serve fare niente, salvo che l'azione fosse voluta", "se era voluta: falla tu, oppure modifica .factory/policy.json")
    ordine = {"OK": 0, "INFO": 0, "ATTENZIONE": 1, "KO": 2}
    try: lv = _livello(rad, bool(hk), gg, cmd, not any(x["stato"] == "KO" for x in c))
    except Exception: lv = None
    return {"stato": max((x["stato"] for x in c), key=lambda s: ordine[s]), "controlli": sorted(c, key=lambda x: -ordine[x["stato"]]), "livello": lv}


NOMI_LIVELLO = ["Da preparare", "Preparato", "Sa lavorare qui", "Controllato", "Su misura"]


def _livello(rad, hook_ok, gg, cmd, piani_ok):
    """Quanto e ben preparato il progetto per lavorare con un agente, in 4 livelli. Solo fatti verificabili, zero token."""
    try:
        from fcore import strumenti as ST_, richieste as RQ_
    except ImportError:
        from . import strumenti as ST_, richieste as RQ_
    st = ST_.tutto(str(rad)); sk = st["skill"]
    qui = [x for x in sk if x["ambito"].startswith("solo") and x["nome"] != "plancia-metodo"]; ist = sum(i["token"] for i in st["istruzioni"] if i["sempre"])
    cm = [r for r in RQ_.tutte(str(rad), 30) if r.get("finita") and r.get("verifica")]; okv = sum(1 for r in cm if r["verifica"]["stato"] == "ok")
    prova_ok = len(cm) >= 3 and okv / float(len(cm)) >= 0.7
    cr = [(1, "Guardie attive (la Plancia vede e protegge)", hook_ok, "riapri l'agente dopo l'installazione"),
          (1, "Mappa del progetto fatta", gg is not None, cmd + " contesto --scrivi"),
          (2, "Metodo della Plancia installato", any(x["nome"] == "plancia-metodo" for x in sk), "Skill e agenti → Da decidere"),
          (2, "Almeno una skill del progetto (comandi, test, convenzioni)", bool(qui), "Skill e agenti → Da decidere"),
          (3, "Istruzioni fisse leggere (sotto circa 3000 token)", ist <= 3000, "Skill e agenti → Istruzioni e mappa"),
          (3, "L'agente prova quello che cambia (almeno 7 richieste su 10)" + ("" if len(cm) >= 3 else " · ancora pochi dati: servono 3 richieste con modifiche"), prova_ok, "chiedigli: \"dopo ogni modifica lancia i test\""),
          (4, "Un agente personalizzato per questo progetto", any(a["ambito"].startswith("solo") for a in st["agenti"]), "Skill e agenti → Da decidere"),
          (4, "Nessuna proposta in sospeso", not st["proposte"], "Skill e agenti → Da decidere"),
          (4, "Nessun piano in errore", piani_ok, "Salute, qui sopra")]
    n = 0
    for liv in (1, 2, 3, 4):
        if all(x[2] for x in cr if x[0] == liv): n = liv
        else: break
    crit = [{"liv": a, "testo": b, "ok": bool(c), "come": d} for a, b, c, d in cr]
    return {"n": n, "di": 4, "nome": NOMI_LIVELLO[n], "criteri": crit, "prossimo": next((x for x in crit if not x["ok"]), None)}


def _cestina_piano(prog, file):
    """Toglie un piano dalla Plancia: non lo cancella, lo sposta in .factory/piani/_cestino (si recupera a mano)."""
    if prog not in PN.progetti(): raise ValueError("progetto non registrato")
    base = (Path(prog) / ".factory" / "piani").resolve(); f = Path(file).resolve()
    if f.parent != base or f.suffix != ".json" or not f.is_file(): raise ValueError("si possono togliere solo i piani scritti dall'agente in .factory/piani")
    (base / "_cestino").mkdir(exist_ok=True); os.replace(f, base / "_cestino" / f.name)
    return {"ok": True, "messaggio": "Piano tolto. Se ti serve ancora e in .factory/piani/_cestino."}


ZIP_URL = "https://codeload.github.com/LuisAlberto90/plancia/zip/refs/heads/main"


def _scarica_zip(url=None):
    """Scarica l'ultima versione (un solo zip da GitHub). Ritorna i byte, o solleva l'errore di rete."""
    import urllib.request
    url = url or ZIP_URL
    if not url.startswith("https://"): raise ValueError("solo https")
    with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310  # nosec B310
        return r.read()


def _versione_zip(z):
    for n in z.namelist():
        if n.endswith("fcore/mcp.py") and n.count("/") == 2:
            m = re.search(r'VERSIONE\s*=\s*"([^"]+)"', z.read(n).decode("utf-8", "replace"))
            return m.group(1) if m else None
    return None


def _copia_diretta(d, z):
    """Sovrascrive file per file dentro la copia `d`, senza mai sostituire la cartella: funziona anche con chat/CLI aperte.
    Ritorna (scritti, saltati). Un file bloccato viene saltato e segnalato, mai si aspetta nessuno."""
    d = Path(d).resolve(); scritti = 0; saltati = []
    radice = z.namelist()[0].split("/")[0] + "/"
    for n in z.namelist():
        if not n.startswith(radice) or n.endswith("/"): continue
        rel = n[len(radice):]
        if not rel or rel.split("/")[0] in (".git", "__pycache__") or ".." in rel.split("/"): continue
        dest = (d / rel).resolve()
        if d not in dest.parents: continue                                # path traversal: mai fuori dalla copia
        dati = z.read(n)
        try:
            if dest.is_file() and dest.read_bytes() == dati: continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".nuovo")
            tmp.write_bytes(dati)
            if dest.is_file():
                import shutil; shutil.copymode(dest, tmp)                    # mantiene i permessi (script eseguibili) del file che sostituisce
            os.replace(tmp, dest); scritti += 1
        except OSError as e:
            saltati.append(rel)
            try: (dest.with_name(dest.name + ".nuovo")).unlink()
            except OSError: pass
    return scritti, saltati


def _aggiorna(scarica=None):
    """Aggiorna la Plancia con un clic, SENZA aspettare nessuno: scarica l'ultima versione e riscrive i file di ogni copia installata
    (VS Code, Copilot CLI, Claude Code), anche con chat o CLI aperte. Poi il pannello si riavvia da solo."""
    import io, zipfile
    from fcore import mcp as _m
    esiti = []; h = Path.home()
    copie = {QUI.parent.resolve()}
    for base, pat in ((h / ".vscode" / "agent-plugins", "*/*/*"), (h / ".copilot" / "installed-plugins", "*/*"), (h / ".copilot" / "installed-plugins", "*")):
        for d in (base.glob(pat) if base.is_dir() else []):
            if (d / "fcore" / "auto.py").is_file(): copie.add(d.resolve())
    try:
        z = zipfile.ZipFile(io.BytesIO((scarica or _scarica_zip)()))
    except Exception as e:                                                # niente rete, GitHub non raggiungibile, zip rotto
        return {"ok": False, "cambiata": False, "messaggio": "Non riesco a scaricare l'ultima versione da GitHub (%s). Controlla la connessione e riprova." % str(e)[:80], "dettagli": []}
    nuova = _versione_zip(z) or _m.VERSIONE
    for d in sorted(copie):
        try: n, saltati = _copia_diretta(d, z)
        except Exception as e: esiti.append((d, False, "NON aggiornata — %s" % str(e)[:80])); continue
        if saltati: esiti.append((d, False, "aggiornata quasi tutta, %d file in uso saltati (%s): si completano al prossimo clic" % (len(saltati), ", ".join(saltati[:3]))))
        else: esiti.append((d, True, "ok (%d file)" % n if n else "gia aggiornata"))
    ok = all(e[1] for e in esiti)
    if nuova != _m.VERSIONE: msg = "Aggiornata dalla %s alla %s: tra pochi secondi la pagina si ricarica da sola. Le chat aperte non servono chiuderle." % (_m.VERSIONE, nuova)
    elif ok: msg = "Hai gia l'ultima versione (%s)." % _m.VERSIONE
    else: msg = "Aggiornata solo in parte: guarda i dettagli sotto."
    dett = ["%s: %s" % (str(d).replace(str(h), "~"), t) for d, good, t in esiti]
    return {"ok": ok, "cambiata": nuova != _m.VERSIONE, "messaggio": msg, "dettagli": dett}


try: from fcore import prompt as PRV
except ImportError: from . import prompt as PRV


def _rk(r): return "%s|%s" % (r.get("sessione") or "", r.get("inizio") or "")


def stato_pannello(prompt=True, cc=None, cp=None):
    rad = lib.radice(); ts = list(T.stati_task().values()); cur = (lib.task_corrente() or {}).get("task_id")
    if cur and next((x["stato"] for x in ts if x["id"] == cur), None) in T.CHIUSE + ("ESEGUITO",): cur = None     # task gia finito: non e piu "corrente"
    sess, cercato = S.leggi_tutto(str(rad), prompt, cc, cp)
    files = lib.trova_piani(); att = lib.piano_attivo()
    piani = [_piano(f) for f in files[:25]]
    rich = RQ.tutte(rad); ev_all = lib.leggi_righe("eventi.jsonl", 400)
    nota_piano = None; dalle = []
    for n, r in enumerate(rich):
        if r.get("rami"):
            st = r["rami"]; dalle.append({"file": "sessione %s" % r["sessione"], "task": ("Ultima richiesta" if n == 0 else "Richiesta delle %s" % (r["inizio"] or "")[11:16]) + " · " + (r["domanda"].splitlines()[0][:70] if r["domanda"] else ""),
                "steps": st, "richieste": [], "validazione": M.valida({"steps": st}), "critico": M.percorso_critico({"steps": st}), "figli": {}, "live": n == 0, "storico": n > 0, "rk": _rk(r)})
    if rich and not rich[0].get("rami") and not rich[0].get("finita"):
        nota_piano = "L'ultima richiesta (\u201c%s\u201d) e in corso: se l'agente divide il lavoro in rami (sotto-agenti) il grafo compare qui. Intanto, sotto, cosa sta facendo passo per passo." % (rich[0]["domanda"].splitlines()[0][:90] if rich[0]["domanda"] else "")
    elif rich and not rich[0].get("rami") and len(rich[0]["attivita"]) >= 4:
        d0 = rich[0]["domanda"].splitlines()[0][:90] if rich[0]["domanda"] else ""; mod = [a for a in rich[0]["attivita"] if a["tipo"] == "modifica"]
        ini = RQ._ts(rich[0]["inizio"]) or 0
        visto = any(e.get("tipo") in ("hook:UserPromptSubmit", "hook:userPromptSubmitted") and _epoch(e.get("ts")) >= ini - 5 for e in ev_all)
        obbl = (lib.config().get("piano") or "obbligatorio") == "obbligatorio"
        if not mod: nota_piano = "Per l'ultima richiesta (\u201c%s\u201d) l'agente ha solo letto e analizzato (%d azioni, nessuna modifica): il piano non era obbligatorio, quindi niente grafo." % (d0, len(rich[0]["attivita"]))
        elif obbl and not visto: nota_piano = "L'agente ha modificato %d file senza piano perche la guardia del piano non era attiva in quella sessione: l'agente era stato aperto prima di `plancia init`. Chiudilo (/exit) e riaprilo nella cartella del progetto." % len(mod)
        elif obbl: nota_piano = "L'agente ha modificato %d file senza piano anche con la guardia attiva: controlla in Salute che gli hook siano attivi e mandami le righe di .factory/eventi.jsonl." % len(mod)
        else: nota_piano = "Per l'ultima richiesta (\u201c%s\u201d) l'agente non ha scritto il piano (%d azioni). Il piano e solo consigliato: per renderlo obbligatorio `plancia init --piano obbligatorio --scrivi`." % (d0, len(rich[0]["attivita"]))
    elif rich and not rich[0].get("rami"):
        dom = rich[0]["domanda"].splitlines()[0][:90] if rich[0]["domanda"] else ""
        if not any(a["tipo"] in ("modifica", "comando") for a in rich[0]["attivita"]) and len(rich[0]["attivita"]) <= 15:
            nota_piano = "L'ultima richiesta (\u201c%s\u201d) era una domanda: l'agente ha risposto leggendo pochi file, senza bisogno di un piano. Sotto: cosa ha letto." % dom
        else:
            nota_piano = "L'ultima richiesta (\u201c%s\u201d) non ha un piano scritto: l'agente ha lavorato passo per passo senza dichiararlo. Sotto: cosa ha fatto, poi i piani delle richieste precedenti." % dom
    inizio0 = RQ._ts(rich[0]["inizio"]) if rich else None
    for x in piani:                                                    # piano scritto dall'agente con `plancia piano nuovo` durante l'ultima richiesta
        try: d0 = json.loads(Path(x["file"]).read_text(encoding="utf-8")) if x.get("file", "").endswith(".json") else {}
        except Exception: d0 = {}
        if d0.get("fonte") == "agente" and inizio0 and max(d0.get("creato_epoch", 0), Path(x["file"]).stat().st_mtime) >= inizio0 - 5:   # anche un piano esteso con "aggiungi" in questa richiesta
            az = {}
            for a in rich[0]["attivita"]:
                if a.get("passo"): az.setdefault(a["passo"], []).append(a)
            for s in x["steps"]: s["azioni"] = az.get(s["id"], [])
            fp = rich[0].get("fuori_piano") or []
            if fp: x["steps"] = x["steps"] + [{"id": "FUORI", "testo": "fuori dal piano: %d modifiche non legate a un passo" % len(fp), "dipende_da": [], "chi": "agente", "stato": "NON_NECESSARIO", "dettaglio": "l'agente ha toccato file senza segnare il passo", "azioni": fp, "fuori": True}]
            x["aderenza"] = _aderenza(x["steps"], rich[0], fp)
            x.update(live=True, task="Ultima richiesta · " + x["task"], scritto=True); piani.remove(x); piani.insert(0, x); nota_piano = None; break
    else:
        for x in piani:
            if x.get("file", "").endswith(".json") and "/piani/" in x.get("file", "").replace("\\", "/"): x["storico"] = True
    ultima = rich[0]["sessione"] if rich else None
    pf = S.piano_da_sessioni([s for s in sess if s.get("id") == ultima] or ([] if rich else sess))     # lista esplicita dell'agente (TaskCreate/TodoWrite) della sessione piu recente
    if pf and pf.get("fonte") == "sotto-agenti": pf = None
    if pf: nota_piano = None
    piani = dalle + piani
    if pf:
        piani = [{"file": "sessione (" + pf["fonte"] + ")", "task": "Lista dell'agente (live) · " + pf["task"], "steps": pf["steps"], "richieste": [], "validazione": M.valida({"steps": pf["steps"]}), "critico": M.percorso_critico({"steps": pf["steps"]}), "figli": {}, "live": True}] + piani
    # ogni richiesta col suo piano: quella piu recente ha il piano "live"; le altre quello scritto mentre giravano
    if rich:
        for x in piani:
            if x.get("live") and not x.get("rk"): x["rk"] = _rk(rich[0])
        ini = [RQ._ts(r["inizio"]) or 0 for r in rich]
        for x in piani:
            if x.get("rk") or not x.get("creato"): continue
            for n, r in enumerate(rich):
                if n and ini[n] and ini[n] - 5 <= x["creato"] < (ini[n - 1] - 5 if ini[n - 1] else 9e12):
                    if any(y.get("rk") == _rk(r) for y in piani): break
                    az = {}
                    for a in r["attivita"]:
                        if a.get("passo"): az.setdefault(a["passo"], []).append(a)
                    for s in x["steps"]: s["azioni"] = az.get(s["id"], [])
                    x["rk"] = _rk(r); break
    eventi = lib.leggi_righe("eventi.jsonl", 40)
    sm = lib.dir_() / "STATE.md"; hl = lib.leggi_righe("handoff.jsonl", 5)
    chiusi = [t for t in ts if t["fine"]]
    ultimo = max(chiusi, key=lambda t: t["fine"]) if chiusi else None
    rq_pub = []; resto = 200000                                           # testo intero dei prompt, fino a 200 KB in tutto (i piu recenti prima)
    for r in rich:
        dm = r["domanda"] if prompt else ""; intero = len(dm) <= resto; resto -= len(dm) if intero else 0
        try: val = PRV.valuta(dm, r.get("fonte")) if prompt else None
        except Exception: val = None
        rq_pub.append(dict(r, rk=_rk(r), risposta=r["risposta"] if prompt else "", domanda=dm if intero else dm[:600] + "…", prompt_voto=val))
    return {"progetto": rad.name, "aggiornato": time.strftime("%Y-%m-%d %H:%M:%S"), "radice": rad.name, "corrente": cur, "modo": lib.modo(), "nota_piano": nota_piano,
            "richieste": rq_pub, "riprendere": RQ.riprendere(rich, eventi) if prompt else None,
            "piano_attivo": str(att) if att else None, "piani": piani, "task": ts,
            "worker": {"sessioni": sess, "totali": S.totali(sess), "cercato": cercato, "eventi": eventi,
                       "nota": "" if sess else "Nessuna sessione Claude Code o Copilot trovata per questa cartella. Ho cercato in: %s." % ", ".join(cercato)},
            "handoff": {"state_md": sm.read_text(encoding="utf-8") if sm.exists() else None, "storico": hl, "ultimo_task_chiuso": ultimo and {k: ultimo[k] for k in ("id", "esito", "fine")},
                        "ripresa": [lib.comando() + " handoff mostra", lib.comando() + " task riprendi <id>" if ts else lib.comando() + " task apri <id>", lib.comando() + " piano mostra"]},
            "salute": _salute(rad, piani, ts, sess, eventi)}


def _porta_occupata(porta):
    import socket
    s = socket.socket()
    try: s.settimeout(0.5); return s.connect_ex(("127.0.0.1", porta)) == 0
    except Exception: return False
    finally: s.close()


def html(snapshot=None):
    from fcore import mcp as _m
    h = (QUI / "pannello.html").read_text(encoding="utf-8").replace("__PLANCIA_V__", _m.VERSIONE)
    return h.replace("<script>", "<script>window.SNAPSHOT=%s;" % json.dumps(snapshot, ensure_ascii=False).replace("</", "<\\/"), 1) if snapshot is not None else h


def main(a):
    ap = argparse.ArgumentParser(add_help=False); ap.add_argument("--porta", type=int, default=8780); ap.add_argument("--host", default="127.0.0.1"); ap.add_argument("--token")
    ap.add_argument("--esporta"); ap.add_argument("--json", action="store_true"); ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--claude-dir", action="append"); ap.add_argument("--copilot-dir", action="append")
    ap.add_argument("--sfondo", action="store_true")
    o = ap.parse_args(a); cc, cp = o.claude_dir, o.copilot_dir
    if o.sfondo:                                                       # plugin: accende il pannello senza bloccare chi lo chiama e stampa l'indirizzo
        from fcore import auto
        auto.avvia_pannello()
        for _ in range(30):
            if auto.pannello_acceso(): break
            time.sleep(0.2)
        from urllib.parse import quote
        print("http://127.0.0.1:8780/?p=%s#progetti" % quote(str(lib.radice()))); return 0
    if o.json: print(json.dumps(stato_pannello(True, cc, cp), ensure_ascii=False, indent=1)); return 0
    if o.esporta:
        Path(o.esporta).write_text(html(stato_pannello(False, cc, cp)), encoding="utf-8"); print("scritto", o.esporta, "(foto del momento: nessun testo dei prompt)"); return 0
    if o.host != "127.0.0.1" and not o.token: print("In rete serve --token SEGRETO (altrimenti usa 127.0.0.1)."); return 2
    rad = lib.radice(); os.environ["FACTORY_ROOT"] = str(rad)
    if (rad / ".factory").is_dir(): PN.registra(rad)

    class Hd(BaseHTTPRequestHandler):
        def log_message(self, *x): pass
        def do_GET(self):
            u = urlparse(self.path)
            if not self._stessa_origine(): self.send_response(403); self.end_headers(); return      # altri siti nel browser non possono leggere la Plancia
            if o.token and parse_qs(u.query).get("token", [""])[0] != o.token: self.send_response(403); self.end_headers(); return
            q = parse_qs(u.query).get("p", [""])[0]
            if u.path == "/api/panoramica":
                with BLOCCO:
                    try:
                        if time.time() - _PAN["t"] > 1.2: _PAN["d"] = PN.tutte(); _PAN["t"] = time.time()
                        d = json.loads(json.dumps(_PAN["d"]))
                    except Exception:
                        import traceback; tb = traceback.format_exc(); sys.stderr.write(tb); d = {"aggiornato": "", "progetti": [], "conteggi": {}, "errore_pannello": tb[-2500:]}
                if o.token:
                    for x in d["progetti"]: [s.update(risposta="", domanda="") for s in x["sessioni"] + x["chiuse"]]
                body, ct = json.dumps(d, ensure_ascii=False).encode(), "application/json"
            elif u.path in ("/api/prove", "/api/prova"):
                with BLOCCO:
                    if q and q not in PN.progetti(): self.send_response(403); self.end_headers(); return
                    os.environ["FACTORY_ROOT"] = q or str(rad)
                    try:
                        try: from fcore import prove as PV
                        except ImportError: from . import prove as PV
                        n = parse_qs(u.query).get("n", [""])[0]
                        d = PV.valuta(int(n)) if u.path == "/api/prova" and n.isdigit() and not o.token else {"prove": PV.elenco()}
                    except Exception:
                        import traceback; d = {"errore_pannello": traceback.format_exc()[-2500:]}
                    finally: os.environ["FACTORY_ROOT"] = str(rad)
                body, ct = json.dumps(d, ensure_ascii=False).encode(), "application/json"
            elif u.path == "/api/consumi":
                with BLOCCO:
                    try:
                        try: from fcore import consumi as CO
                        except ImportError: from . import consumi as CO
                        g = parse_qs(u.query).get("g", ["7"])[0]; g = int(g) if g.isdigit() and int(g) in (0, 1, 7, 30) else 7
                        d = CO.consumi(PN.progetti(), g)
                    except Exception:
                        import traceback; d = {"errore_pannello": traceback.format_exc()[-2500:]}
                    finally: os.environ["FACTORY_ROOT"] = str(rad)
                body, ct = json.dumps(d, ensure_ascii=False).encode(), "application/json"
            elif u.path == "/api/strumenti":
                with BLOCCO:
                    if q and q not in PN.progetti(): self.send_response(403); self.end_headers(); return
                    os.environ["FACTORY_ROOT"] = q or str(rad)
                    try:
                        try: from fcore import strumenti as ST
                        except ImportError: from . import strumenti as ST
                        d = ST.tutto(q or str(rad))
                    except Exception:
                        import traceback; d = {"errore_pannello": traceback.format_exc()[-2500:]}
                    finally: os.environ["FACTORY_ROOT"] = str(rad)
                body, ct = json.dumps(d, ensure_ascii=False).encode(), "application/json"
            elif u.path == "/api/state":
                with BLOCCO:
                    if q and q not in PN.progetti(): self.send_response(403); self.end_headers(); return      # solo progetti conosciuti
                    os.environ["FACTORY_ROOT"] = q or str(rad)
                    try: body = json.dumps(stato_pannello(not o.token, cc, cp), ensure_ascii=False).encode()
                    except Exception:
                        import traceback; tb = traceback.format_exc(); sys.stderr.write(tb); sys.stderr.flush()
                        body = json.dumps({"errore_pannello": tb[-2500:]}, ensure_ascii=False).encode()
                    finally: os.environ["FACTORY_ROOT"] = str(rad)
                ct = "application/json"
            elif u.path == "/api/versione":
                from fcore import mcp as _m; body, ct = json.dumps({"versione": _m.VERSIONE, "progetto": str(rad)}).encode(), "application/json"
            elif u.path == "/api/lascia":                                   # una Plancia piu nuova chiede il posto (aggiornamento del plugin): chiudo
                from fcore import mcp as _m
                nv = parse_qs(u.query).get("v", [""])[0]
                vt = lambda s: tuple(int(x) for x in s.split(".") if x.isdigit())
                if self.client_address[0] != "127.0.0.1" or self.headers.get("X-Plancia") != "1" or not nv or vt(nv) <= vt(_m.VERSIONE): self.send_response(403); self.end_headers(); return
                self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
                import threading; threading.Thread(target=lambda: (time.sleep(0.3), os._exit(0)), daemon=True).start(); return
            elif u.path == "/": body, ct = html().encode(), "text/html; charset=utf-8"
            else: self.send_response(404); self.end_headers(); return
            self.send_response(200); self.send_header("Content-Type", ct); self._sicurezza()
            if ct.startswith("text/html"): self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers(); self.wfile.write(body)
        def _no(self): self.send_response(405); self.end_headers()
        do_PUT = do_DELETE = do_PATCH = _no

        def do_POST(self):
            """Unica scrittura: accetta/rifiuta una proposta della scheda Strumenti. Solo dal pannello stesso (stessa origine), mai da altri siti."""
            u = urlparse(self.path)
            if u.path not in ("/api/proposta", "/api/piano", "/api/aggiorna") or not self._stessa_origine(): self.send_response(403); self.end_headers(); return
            if o.token and parse_qs(u.query).get("token", [""])[0] != o.token: self.send_response(403); self.end_headers(); return
            if u.path in ("/api/piano", "/api/aggiorna"):
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                    if n > 4096 or "application/json" not in (self.headers.get("Content-Type") or ""): raise ValueError("richiesta non valida")
                    d = json.loads(self.rfile.read(n).decode("utf-8"))
                    with BLOCCO:
                        r = _aggiorna() if u.path == "/api/aggiorna" else _cestina_piano(str(d.get("p") or ""), str(d.get("file") or ""))
                        _PAN["t"] = 0
                    body = json.dumps(r, ensure_ascii=False).encode(); self.send_response(200)
                except Exception as e:
                    body = json.dumps({"ok": False, "messaggio": str(e)[:200]}).encode(); self.send_response(400)
                self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self._sicurezza(); self.end_headers(); self.wfile.write(body); return
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n > 4096 or "application/json" not in (self.headers.get("Content-Type") or ""): raise ValueError("richiesta non valida")
                d = json.loads(self.rfile.read(n).decode("utf-8"))
                q, pid, az, ag = str(d.get("p") or ""), str(d.get("id") or ""), str(d.get("azione") or ""), str(d.get("agente") or "")
                if q not in PN.progetti() or not re.fullmatch(r"[a-z0-9-]{1,60}", pid) or az not in ("rifiuta", "ripristina", "crea") or ag not in ("", "copilot", "claude", "entrambi"): raise ValueError("richiesta non valida")
                with BLOCCO:
                    try:
                        from fcore import strumenti as ST
                    except ImportError:
                        from . import strumenti as ST
                    r = ST.azione_proposta(q, pid, az, ag); PN._PROP.pop(q, None); _PAN["t"] = 0
                    os.environ["FACTORY_ROOT"] = str(rad)
                body = json.dumps(r, ensure_ascii=False).encode()
                self.send_response(200)
            except Exception as e:
                body = json.dumps({"ok": False, "messaggio": str(e)[:200]}).encode(); self.send_response(400)
            self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self._sicurezza(); self.end_headers(); self.wfile.write(body)

        def _stessa_origine(self):
            """Contro DNS rebinding e richieste da altri siti: Host deve essere il pannello, Origin (se c'e) uguale."""
            h = (self.headers.get("Host") or "").lower()
            ok_h = h in ("127.0.0.1:%d" % o.porta, "localhost:%d" % o.porta, "[::1]:%d" % o.porta) or (o.host not in ("127.0.0.1", "localhost") and bool(o.token))
            org = self.headers.get("Origin")
            return ok_h and (org is None or org.lower() in ("http://" + h,))

        def _sicurezza(self):
            self.send_header("X-Content-Type-Options", "nosniff"); self.send_header("X-Frame-Options", "DENY"); self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")

    from fcore import mcp as _m
    try:                                                              # c'e gia un pannello acceso su questa porta?
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:%d/api/versione" % o.porta, timeout=1.5) as rsp: gia = json.loads(rsp.read().decode())  # noqa: S310  # nosec B310
    except Exception: gia = None
    if gia and gia.get("versione") == _m.VERSIONE and not o.token:
        from urllib.parse import quote
        stesso = os.path.normcase(gia.get("progetto") or "") == os.path.normcase(str(rad))
        if not stesso: PN.registra(rad)
        url = "http://127.0.0.1:%d/%s" % (o.porta, "" if stesso else "?p=%s#piano" % quote(str(rad)))
        print("La Plancia %s e gia aperta: la riuso%s. %s" % (_m.VERSIONE, "" if stesso else " sul progetto " + rad.name, url))
        if not o.no_browser: import webbrowser; webbrowser.open(url)
        return 0
    if gia: print("ATTENZIONE: su %d e acceso un pannello VECCHIO (versione %s, questa e %s). Chiudi la sua finestra; intanto parto su un'altra porta." % (o.porta, gia.get("versione") or "?", _m.VERSIONE))
    elif _porta_occupata(o.porta): print("La porta %d e occupata da un vecchio pannello o da un altro programma: chiudi le finestre vecchie della Plancia. Intanto parto su un'altra porta." % o.porta)

    class Srv(ThreadingHTTPServer):
        allow_reuse_address = os.name != "nt"                          # Windows: SO_REUSEADDR permetterebbe due pannelli sulla stessa porta
        def server_bind(self):
            if os.name == "nt":
                import socket
                try: self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                except Exception: pass
            super().server_bind()
    for porta in range(o.porta, o.porta + 10):
        try: srv = Srv((o.host, porta), Hd); break
        except OSError: continue
    else: print("Nessuna porta libera tra %d e %d (pannello gia avviato?)" % (o.porta, o.porta + 9)); return 2
    o.porta = porta                                                      # la porta vera: serve al controllo Host
    url = "http://%s:%d/%s" % (o.host, porta, "?token=" + o.token if o.token else "")
    print("Pannello su", url, "(progetto %s) - Ctrl+C per fermare" % rad, flush=True)
    if not o.no_browser and o.host == "127.0.0.1":
        import threading, webbrowser; threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    riavvia = []
    def _guardia_versione():                                             # dopo un aggiornamento (git pull) il pannello si riavvia da solo con il codice nuovo
        f = QUI / "mcp.py"
        while True:
            time.sleep(5)
            try: m = re.search(r'VERSIONE\s*=\s*"([^"]+)"', f.read_text(encoding="utf-8"))
            except Exception: continue
            if m and m.group(1) != _m.VERSIONE: riavvia.append(1); srv.shutdown(); return
    import threading as _th; _th.Thread(target=_guardia_versione, daemon=True).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
    if riavvia:
        try: srv.server_close()
        except Exception: pass
        import subprocess
        kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if os.name == "nt": kw["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000
        else: kw["start_new_session"] = True
        try: subprocess.Popen([sys.executable, str(QUI.parent / "factory.py"), "pannello", "--no-browser", "--porta", str(o.porta)] + (["--host", o.host, "--token", o.token] if o.token else []), **kw)  # noqa: S603
        except Exception: pass
    return 0


if __name__ == "__main__": sys.exit(main(sys.argv[1:]))

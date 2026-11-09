#!/usr/bin/env python3
"""Piano del task: elenco di passi con stato, dipendenze, blocchi ed evidenze. Il pannello lo legge. Va scritto PRIMA di eseguire e tenuto aggiornato.
  piano crea [cartella] [--da file]               crea da un file di passi (o un modello di 3 passi) e lo rende il piano attivo
  piano passo <id> in_corso|fatto|aspetta|problema|bloccato ["frase"]    aggiorna il passo (la frase e il dettaglio, in italiano semplice)
  piano mostra                                    elenco dei passi (<=15 righe)
  piano guardia                                   passo in_corso fermo oltre la soglia del suo tipo -> bloccato + evento
  piano valida [--json] [--strict] [file]         validatore deterministico (stati, grafo, padre/figli, evidenze); sola lettura; --strict = exit 1 se anomalie
  piano classifica "<richiesta>" [--passo P]      tipo di richiesta (clarification|acceptance_criteria_update|correction|subtask|independent_branch|new_objective), senza LLM
  piano evento "<richiesta>" [--tipo T] [--passo P] [--applica]   classifica e (con --applica) aggiorna il piano SENZA rinumerare ne riaprire passi
  piano migra [--scrivi]                          anteprima della traduzione degli stati storici in canonici (+ backup .bak)
Stati canonici: DA_FARE IN_CORSO FATTO VERIFICATO BLOCCATO NON_NECESSARIO. Opzioni di `passo`: --evidenza F --verification V --bloccante si|no
--tipo-blocco T --causa T --prossimo T --motivo T --regressione T (obbligatoria per riportare a DA_FARE/IN_CORSO un passo completato).
Passo: id, testo (italiano semplice), dipende_da [ids], chi (agente|script|controllore|utente), stato, dettaglio (una riga).
Piano attivo: variabile FACTORY_PIANO oppure .factory/_stato/piano_attivo.json. Formato nativo .json; i .yaml si leggono con PyYAML."""
import os, re, sys, time
from pathlib import Path
try: from . import store as lib, piano_modello as M
except ImportError: import store as lib, piano_modello as M

STATI = ("da_fare", "in_corso", "fatto", "problema", "bloccato", "aspetta_utente") + M.CANON       # storici + canonici
CHI = ("agente", "script", "controllore", "utente")
SOGLIA_MIN = {"agente": 15, "script": 10, "controllore": 30}          # minuti senza progressi prima di «bloccato»; l'utente non scade

def attivo(): return lib.piano_attivo()
def leggi(p): return lib.leggi(p)
def scrivi(p, d): lib.scrivi(p, d)
def valida(d):
    ids = [s.get("id") for s in d["steps"]]; err = []
    if len(set(ids)) != len(ids): err.append("id duplicati")
    for s in d["steps"]:
        if M.canon(s.get("stato")) is None: err.append(f"{s.get('id')}: stato {s.get('stato')}")
        if s.get("chi", "agente") not in CHI: err.append(f"{s.get('id')}: chi {s.get('chi')}")
        for x in s.get("dipende_da") or []:
            if x not in ids: err.append(f"{s.get('id')}: dipende da {x} inesistente")
    return err

def crea(cartella=None, da=None):
    c = Path(cartella) if cartella else lib.dir_() / "task" / ("piano-" + time.strftime("%Y%m%d-%H%M%S")); c.mkdir(parents=True, exist_ok=True); p = c / "piano.json"
    d = leggi(da) if da else {"task": c.name, "steps": [
        {"id": "capire", "testo": "Capire la richiesta e leggere i file necessari", "dipende_da": [], "chi": "agente"},
        {"id": "fare", "testo": "Fare la modifica", "dipende_da": ["capire"], "chi": "agente"},
        {"id": "controllare", "testo": "Controllare che tutto funzioni", "dipende_da": ["fare"], "chi": "controllore"}]}
    d.setdefault("task", c.name)
    for s in d["steps"]: s.setdefault("stato", "DA_FARE"); s.setdefault("chi", "agente"); s.setdefault("dipende_da", []); s["agg"] = lib.ora()
    e = valida(d)
    if e: print("piano non valido: " + "; ".join(e)); return 2
    scrivi(p, d); lib.salva("piano_attivo.json", {"piano": str(p.resolve())}); print(f"piano creato: {p} ({len(d['steps'])} passi)"); return 0

OPZ = {"--evidenza": "evidence", "--verification": "verification", "--bloccante": "blocking", "--tipo-blocco": "blocker_type", "--causa": "blocker_reason", "--prossimo": "next_action", "--motivo": "motivo", "--regressione": "_regressione"}
def imposta(pid, stato, frase=None, p=None, opz=None):
    """Stato canonico + campi del modello. Rifiuta, senza --regressione, di riaprire un passo FATTO/VERIFICATO; un passo non torna DA_FARE senza una regressione dimostrata."""
    opz = opz or {}; p = p or attivo()
    if not p: print("nessun piano attivo: factory piano crea [cartella]"); return 2
    d = leggi(p); s = next((x for x in d["steps"] if x["id"] == pid), None)
    if not s: print(f"passo {pid} inesistente"); return 2
    nuovo = M.canon(stato); prima = M.canon(s.get("stato"))
    if nuovo is None: print("stato: " + "|".join(M.CANON)); return 2
    if prima in ("FATTO", "VERIFICATO") and nuovo in ("DA_FARE", "IN_CORSO"):
        if not opz.get("_regressione"): print(f"passo {pid} è {prima}: per riaprirlo serve --regressione \"cosa è regredito\" (evidenza)"); return 2
        s.setdefault("history", []).append({"ts": lib.ora(), "tipo": "regressione", "da": prima, "a": nuovo, "motivo": opz["_regressione"]})
    if prima == "BLOCCATO" and nuovo != "BLOCCATO": s.setdefault("history", []).append({"ts": lib.ora(), "tipo": "sblocco", "causa": s.get("blocker_reason"), "tipo_blocco": s.get("blocker_type")})
    s["stato"] = nuovo; s["agg"] = lib.ora()
    if frase: s["dettaglio"] = frase
    if stato == "aspetta_utente": s["blocker_type"] = "utente"; s.setdefault("blocker_reason", frase or "attende la persona"); s.setdefault("next_action", "la persona risponde o conferma")
    if stato == "problema": s.setdefault("blocker_type", "tecnico"); s.setdefault("blocker_reason", frase or "problema")
    if nuovo == "IN_CORSO": s.setdefault("started_at", lib.ora())
    if nuovo in ("FATTO", "VERIFICATO", "NON_NECESSARIO"):
        s["completed_at"] = lib.ora()
        for k in ("blocker_type", "blocker_reason"): s.pop(k, None)
        if nuovo == "FATTO": s.setdefault("verification", "pending")
    for k, v in opz.items():
        if k == "_regressione": continue
        if k == "evidence": s["evidence"] = sorted(set((s.get("evidence") or []) + [v]))
        elif k == "blocking": s[k] = v in ("si", "true", "1", True)
        else: s[k] = v
    if nuovo == "VERIFICATO" and not s.get("evidence"): print(f"avviso: {pid} VERIFICATO senza evidenza (usare --evidenza <file>)", file=sys.stderr)
    scrivi(p, d)
    tipo = {"IN_CORSO": "passo_iniziato", "FATTO": "passo_fatto", "NON_NECESSARIO": "passo_fatto", "VERIFICATO": "passo_verificato", "BLOCCATO": "passo_bloccato"}.get(nuovo)
    if tipo and (prima != nuovo or nuovo == "VERIFICATO"): lib.evento(tipo, "piano", passo=pid, messaggio=lib.redigi(frase or ""))
    if nuovo == "BLOCCATO": lib.evento("bloccato" if stato != "problema" else "errore", "piano", passo=pid, messaggio=lib.redigi(f"passo «{pid}»: {frase or stato}"))
    return 0

def guardia(silenzioso=True):
    p = attivo(); n = 0
    if not p: return 0
    d = leggi(p); ora = time.time()
    for s in d["steps"]:
        soglia = SOGLIA_MIN.get(s.get("chi", "agente"))
        if M.canon(s.get("stato")) != "IN_CORSO" or not soglia: continue
        try: t = time.mktime(time.strptime(s["agg"], "%Y-%m-%dT%H:%M:%S"))
        except Exception: continue
        if ora - t > soglia * 60:
            s["stato"] = "BLOCCATO"; s["dettaglio"] = f"nessun progresso da oltre {soglia} minuti"; s["blocker_reason"] = s["dettaglio"]; s["blocker_type"] = "tecnico"; s["next_action"] = s.get("next_action") or "verificare se il passo è ancora attivo, poi riprenderlo o segnalarlo"; s["agg"] = lib.ora(); n += 1
            lib.evento("bloccato", "piano", passo=s["id"], messaggio=f"passo «{s['id']}» fermo da oltre {soglia} min")
    if n: scrivi(p, d)
    if not silenzioso: print(f"guardia: {n} passi segnati bloccati")
    return n

def mostra():
    p = attivo()
    if not p: print("nessun piano attivo"); return 2
    d = leggi(p); print(f"{d.get('task')}: {sum(M.canon(s.get('stato')) in ('FATTO', 'VERIFICATO') for s in d['steps'])}/{len(d['steps'])} fatti ({p})")
    for s in d["steps"][:13]: print(f"  {M.canon(s.get('stato')) or s.get('stato'):<15} {s['id']:<14} {s['testo'][:50]}" + (f"  — {s['dettaglio'][:40]}" if s.get("dettaglio") else ""))
    return 0

def _opz(a):
    """Estrae le opzioni --x valore dal resto degli argomenti → (posizionali, opzioni)."""
    pos, o, i = [], {}, 0
    while i < len(a):
        if a[i] in OPZ and i + 1 < len(a): o[OPZ[a[i]]] = a[i + 1]; i += 2
        else: pos.append(a[i]); i += 1
    return pos, o

def cmd_valida(a):
    import json
    p = Path(next((x for x in a if not x.startswith("--")), "")) if any(not x.startswith("--") for x in a) else attivo()
    if not p or not p.exists(): print(f"nessun piano{(' ' + str(p)) if p else ''}: factory piano valida <piano>"); return 2
    d = leggi(p); r = M.valida(d); r["piano"] = str(p)
    if "--json" in a: print(json.dumps(r, ensure_ascii=False))           # una riga
    else:
        c = r["conteggi"]; print(f"{'VALIDO' if r['valido'] else 'NON VALIDO'} · {p.parent.name} · " + " ".join(f"{k}={v}" for k, v in c.items() if v))
        for x in r["anomalie"][:8]: print(f"  ERRORE {x['passo']}: {x['codice']} — {x['testo']} → {x['suggerimento']}")
        if r["avvisi"]: print(f"  avvisi: {len(r['avvisi'])} (" + ", ".join(sorted({x['codice'] for x in r['avvisi']})) + ") — --json per il dettaglio")
        if r["legacy"]: print(f"  stati storici letti come canonici: {len(r['legacy'])} passi (piano migra)")
        print("chiusura: " + ("ammessa" + (f" con limitazioni non bloccanti {M.chiusura_con_limitazioni(d)}" if M.chiusura_con_limitazioni(d) else "") if r["chiudibile"] else "NON ammessa — blocca: " + ", ".join(r["blocca_chiusura"][:8]) if r["blocca_chiusura"] else "NON ammessa — correggere le anomalie"))
    return 1 if "--strict" in a and not r["valido"] else 0        # exit 0 = rapporto prodotto; `--strict` = exit 1 con anomalie (senza, non conta come errore per il rilevatore di loop)

def cmd_classifica(a):
    import json
    cur = a[a.index("--passo") + 1] if "--passo" in a and a.index("--passo") + 1 < len(a) else None
    t = " ".join(x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or a[i - 1] != "--passo"))
    p = attivo(); d = leggi(p) if p else {"steps": []}
    cur = cur or next((s["id"] for s in d["steps"] if M.canon(s.get("stato")) == "IN_CORSO"), None)
    print(json.dumps(M.classifica(t, d, cur), ensure_ascii=False)); return 0

def _prossimo_id(steps, prefisso):
    n = 1
    ids = {s["id"] for s in steps}
    while f"{prefisso}{n}" in ids: n += 1
    return f"{prefisso}{n}"

def cmd_evento(a):
    """Registra la richiesta nel piano (`richieste`, append-only). Con --applica: effetto strutturale minimo, mai rinumerazioni né riaperture."""
    import json
    flag = {k: a[a.index(k) + 1] for k in ("--tipo", "--passo") if k in a}
    t = " ".join(x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or a[i - 1] not in ("--tipo", "--passo")))
    p = attivo()
    if not p: print("nessun piano attivo"); return 2
    d = leggi(p); cur = flag.get("--passo") or next((s["id"] for s in d["steps"] if M.canon(s.get("stato")) == "IN_CORSO"), None)
    r = M.classifica(t, d, cur)
    if flag.get("--tipo"):
        if flag["--tipo"] not in M.TIPI_RICHIESTA: print("tipo: " + "|".join(M.TIPI_RICHIESTA)); return 2
        r["type"] = flag["--tipo"]; r["ambiguo"] = False; r["requires_plan_change"] = r["type"] in ("subtask", "independent_branch", "new_objective")
    if flag.get("--passo"): r["target_step"] = flag["--passo"]
    per = {s["id"]: s for s in d["steps"]}; tg = per.get(r["target_step"]); eff = "nessuna modifica (solo registrata)"
    if "--applica" in a:
        if r["type"] == "new_objective": eff = "nuovo obiettivo: creare un nuovo task (factory piano crea <cartella>) collegato a questo; questo piano non cambia"
        elif r["type"] == "clarification" and tg: tg.setdefault("note", []).append({"ts": lib.ora(), "testo": r["summary"]}); eff = f"nota su {tg['id']}"
        elif r["type"] == "acceptance_criteria_update" and tg:
            tg.setdefault("acceptance_criteria", []).append(r["summary"]); tg.setdefault("history", []).append({"ts": lib.ora(), "tipo": "criteri_aggiornati", "testo": r["summary"]})
            if M.canon(tg.get("stato")) == "VERIFICATO": tg["stato"] = "FATTO"; tg["verification"] = "pending"; eff = f"criterio aggiunto a {tg['id']}: VERIFICATO → FATTO, verification=pending (da riverificare)"
            else: eff = f"criterio aggiunto a {tg['id']}"
        elif r["type"] == "correction" and tg:
            tg.setdefault("history", []).append({"ts": lib.ora(), "tipo": "correzione", "testo": r["summary"]}); tg["verification"] = "pending" if M.canon(tg.get("stato")) in ("FATTO", "VERIFICATO") else tg.get("verification", "none"); eff = f"correzione registrata su {tg['id']} (storico conservato, stato invariato)"
        elif r["type"] == "subtask" and tg:
            nid = _prossimo_id(d["steps"], tg["id"] + "."); d["steps"].append({"id": nid, "testo": r["summary"][:100], "dipende_da": [], "chi": "agente", "stato": "DA_FARE", "parent": tg["id"], "agg": lib.ora()}); eff = f"sottopasso {nid} sotto {tg['id']}"
        elif r["type"] == "independent_branch":
            nid = _prossimo_id(d["steps"], "R"); d["steps"].append({"id": nid, "testo": r["summary"][:100], "dipende_da": [], "chi": "agente", "stato": "DA_FARE", "ramo": nid, "agg": lib.ora()}); eff = f"ramo indipendente {nid} (non blocca gli altri)"
        else: eff = "tipo che richiede un passo di riferimento: usare --passo"
    d.setdefault("richieste", []).append({"ts": lib.ora(), "tipo": r["type"], "target": r["target_step"], "ambiguo": r["ambiguo"], "testo": r["summary"], "effetto": eff if "--applica" in a else "non applicato"})
    scrivi(p, d); r["effetto"] = eff; print(json.dumps(r, ensure_ascii=False)); return 0

def cmd_migra(a):
    p = attivo()
    if not p: print("nessun piano attivo"); return 2
    d = leggi(p); mod = []
    for s in d["steps"]:
        v = str(s.get("stato", "da_fare")); c = M.canon(v)
        if c is None or v == c: continue
        nota = M.LEGACY_NOTA.get(v)
        mod.append((s["id"], v, c, "AMBIGUO: serve causa/prossimo passo" if c == "BLOCCATO" and v != "aspetta_utente" else ""))
        if "--scrivi" in a:
            s["stato"] = c
            if nota and nota[0] and not s.get("blocker_type"): s["blocker_type"] = nota[0]
            if c == "BLOCCATO" and not s.get("blocker_reason") and s.get("dettaglio"): s["blocker_reason"] = s["dettaglio"]
            s.setdefault("history", []).append({"ts": lib.ora(), "tipo": "migrazione_stato", "da": v, "a": c})
    print(f"{p.parent.name}: {len(mod)} passi da migrare" + ("" if "--scrivi" in a else " (anteprima, nessuna scrittura)"))
    for x in mod[:15]: print(f"  {x[0]:<8} {x[1]:<15} → {x[2]:<14} {x[3]}")
    if mod and "--scrivi" in a:
        import shutil; shutil.copy2(p, str(p) + f".bak_{time.strftime('%Y%m%d%H%M%S')}"); scrivi(p, d); print("scritto; backup .bak accanto al piano")
    return 0

def _slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "piano"


def nuovo(args):
    """plancia piano nuovo "Titolo" "A: testo" "B: testo <- A" "C: testo <- A,B" "D: testo <-"
    Senza "<-" un passo dipende dal precedente; "<- X,Y" dipende da X e Y; "<-" da solo = indipendente (ramo parallelo)."""
    nuova = bool(args) and args[0] in ("--nuovo", "--new", "--sostituisci")
    if nuova: args = args[1:]
    if len(args) < 2: print('uso: plancia piano nuovo "Titolo" "A: testo" "B: testo <- A" ...'); return 2
    aperto = _aperto_di_recente()
    if aperto and not nuova:                                              # tipico: un sotto-agente che crea il suo piano e confonde quello del genitore
        print('A plan is already open: "%s" (%d steps open, %d min ago).\n'
              '- If you are a SUB-AGENT: do NOT create a plan and do NOT call plancia; just do your task and report to the parent.\n'
              '- If this is a NEW user request: repeat with --new as first argument (MCP: "nuovo": true).' % aperto); return 3
    steps, prev = [], None
    for n, raw in enumerate(args[1:]):
        m = re.match(r"^\s*([A-Za-z0-9][\w.-]{0,15})\s*[:)]\s*(.+?)\s*(?:<-\s*([\w.,\s-]*))?$", raw)
        pid, testo, dip = (m.group(1), m.group(2), m.group(3)) if m else (chr(65 + n) if n < 26 else "P%d" % n, raw.strip(), None)
        deps = [x.strip() for x in dip.split(",") if x.strip() and x.strip() != "-"] if dip is not None else ([prev] if prev else [])
        steps.append({"id": pid, "testo": lib.redigi(testo, 140), "dipende_da": deps, "chi": "agente", "stato": "DA_FARE", "agg": lib.ora()}); prev = pid
    ids = {s["id"] for s in steps}
    for s in steps: s["dipende_da"] = [x for x in s["dipende_da"] if x in ids and x != s["id"]]
    if len(ids) != len(steps): print("id dei passi duplicati"); return 2
    try:
        from fcore import qualita as Q
    except ImportError:
        from . import qualita as Q
    rq = Q.ultima_richiesta(); voto, consigli, note = Q.valuta(steps, rq)
    f = lib.dir_() / "piani" / ("%s-%s.json" % (time.strftime("%Y%m%d-%H%M%S"), _slug(args[0])))
    scrivi(f, {"task": lib.redigi(args[0], 120), "creato": lib.ora(), "creato_epoch": time.time(), "fonte": "agente", "richiesta": lib.redigi(rq, 200) or None,
               "qualita": {"voto": voto, "note": note}, "steps": steps})
    lib.salva("piano_attivo.json", {"piano": str(f.resolve())}); lib.evento("piano_nuovo", "piano", messaggio=args[0][:80])
    print("plan: %d steps (%s), quality %d/10. Update: plancia passo <id> [fatto|errore \"cause\"|saltato]" % (len(steps), " ".join(s["id"] for s in steps), voto))
    if voto < 8 and consigli: print("Improve it now (plancia piano nuovo --new ... or piano aggiungi):\n- " + "\n- ".join(consigli))
    return 0


def _aperto_di_recente(minuti=15):
    f = lib.piano_attivo()
    if not f or not f.is_file(): return None
    try: d = leggi(f)
    except Exception: return None
    eta = time.time() - (d.get("creato_epoch") or f.stat().st_mtime)
    aperti = [s for s in d.get("steps", []) if M.canon(s.get("stato")) in ("DA_FARE", "IN_CORSO")]
    if eta > minuti * 60 or not aperti: return None
    return (d.get("task", "")[:60], len(aperti), int(eta // 60))


def aggiungi(args):
    """plancia piano aggiungi "E: testo <- B" ...   aggiunge passi al piano attivo senza toccare gli altri."""
    f = lib.piano_attivo()
    if not args or not f or not f.is_file(): print("nessun piano attivo: plancia piano nuovo ..."); return 2
    d = leggi(f); ids = {s["id"] for s in d["steps"]}; ultimo = d["steps"][-1]["id"] if d["steps"] else None; nuovi = []
    for n, raw in enumerate(args):
        m = re.match(r"^\s*([A-Za-z0-9][\w.-]{0,15})\s*[:)]\s*(.+?)\s*(?:<-\s*([\w.,\s-]*))?$", raw)
        pid, testo, dip = (m.group(1), m.group(2), m.group(3)) if m else ("P%d" % (len(ids) + n + 1), raw.strip(), None)
        if pid in ids: print("passo %s esiste gia" % pid); return 2
        deps = [x.strip() for x in dip.split(",") if x.strip() and x.strip() != "-"] if dip is not None else ([ultimo] if ultimo else [])
        d["steps"].append({"id": pid, "testo": lib.redigi(testo, 140), "dipende_da": [x for x in deps if x in ids or x in [y["id"] for y in nuovi]], "chi": "agente", "stato": "DA_FARE", "agg": lib.ora()})
        ids.add(pid); nuovi.append(d["steps"][-1]); ultimo = pid
    scrivi(f, d); print("aggiunti: %s" % " ".join(s["id"] for s in nuovi)); return 0


ALIAS = {"inizia": "in_corso", "in_corso": "in_corso", "via": "in_corso", "fatto": "fatto", "ok": "fatto", "errore": "bloccato", "bloccato": "bloccato", "ko": "bloccato",
         "saltato": "NON_NECESSARIO", "non_necessario": "NON_NECESSARIO", "aspetta": "aspetta_utente"}


def passo_breve(a):
    """plancia passo <id> [inizia|fatto|errore|saltato|aspetta] ["nota"]   (senza stato = inizia)"""
    if not a: print('uso: plancia passo <id> [fatto|errore "motivo"|saltato]'); return 2
    pid = a[0]; st = ALIAS.get((a[1] if len(a) > 1 else "inizia").lower()); nota = " ".join(a[2:]) or None
    if st is None: st, nota = "in_corso", " ".join(a[1:])
    o = {"blocker_reason": nota, "blocker_type": "tecnico", "next_action": "vedi nota"} if st == "bloccato" and nota else ({"motivo": nota or "saltato dall'agente"} if st == "NON_NECESSARIO" else {})
    import contextlib, io
    buf = io.StringIO(); f = lib.piano_attivo(); chiusi = []
    if f and st in ("in_corso", "fatto", "bloccato", "NON_NECESSARIO"):      # se X parte o finisce, i passi da cui dipende sono per forza finiti
        try:
            d = leggi(f); by = {s["id"]: s for s in d["steps"]}
            for dep in (by.get(pid) or {}).get("dipende_da", []):
                if M.canon(by.get(dep, {}).get("stato")) == "IN_CORSO":
                    with contextlib.redirect_stdout(io.StringIO()): imposta(dep, "fatto", "chiuso in automatico: il passo %s e partito" % pid)
                    chiusi.append(dep)
        except Exception: pass
    with contextlib.redirect_stdout(buf): rc = imposta(pid, st, nota, opz=o)
    if chiusi: print("(chiusi in automatico: %s)" % " ".join(chiusi))
    print(buf.getvalue().strip() or "%s: %s" % (pid, M.canon(st) or st)); return rc


def main(a):
    if not a: print(__doc__); return 2
    if a[0] == "nuovo": return nuovo(a[1:])
    if a[0] == "aggiungi": return aggiungi(a[1:])
    if a[0] == "crea":
        da = a[a.index("--da") + 1] if "--da" in a else None
        pos = [x for i, x in enumerate(a[1:], 1) if not x.startswith("--") and (i < 2 or a[i - 1] != "--da")]
        return crea(pos[0] if pos else None, da)
    if a[0] == "passo" and len(a) > 2:
        pos, o = _opz(a[1:]); st = pos[1]
        if st not in STATI and st != "aspetta": print("stato: " + "|".join(M.CANON) + " (storici: da_fare in_corso fatto problema aspetta bloccato)"); return 2
        return imposta(pos[0], "aspetta_utente" if st == "aspetta" else st, pos[2] if len(pos) > 2 else None, opz=o)
    if a[0] == "mostra": return mostra()
    if a[0] == "guardia": guardia(False); return 0
    if a[0] == "valida": return cmd_valida(a[1:])
    if a[0] == "classifica": return cmd_classifica(a[1:])
    if a[0] == "evento": return cmd_evento(a[1:])
    if a[0] == "migra": return cmd_migra(a[1:])
    print(__doc__); return 2

if __name__ == "__main__": sys.exit(main(sys.argv[1:]))

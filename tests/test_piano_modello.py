"""Test del modello di piano (Lotto 2): validatore, classificazione, transizioni, compatibilità con piani storici. Sandbox in cartella temporanea; V62 solo letto."""
import os as _os; _os.environ.setdefault("FACTORY_EVENT_SOURCE", "test")      # i test non contaminano gli indicatori di produzione
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
QUI = Path(__file__).resolve().parent; ROOT = QUI.parent; sys.path.insert(0, str(ROOT / 'fcore'))
import piano_modello as M
ok = ko = 0
def v(nome, cond, det=""):
    global ok, ko
    if cond: ok += 1; print(f"  ok  {nome}")
    else: ko += 1; print(f"  KO  {nome} {det}")
P = lambda *s: {"steps": [dict(zip(("id", "stato"), x[:2]), **(x[2] if len(x) > 2 else {})) for x in s]}
cod = lambda d: {a["codice"] for a in M.valida(d)["anomalie"]}

v("canon: storici → canonici", [M.canon(x) for x in ("da_fare", "fatto", "problema", "aspetta_utente", "VERIFICATO")] == ["DA_FARE", "FATTO", "BLOCCATO", "BLOCCATO", "VERIFICATO"])
v("padre VERIFICATO con figlio BLOCCATO obbligatorio → anomalia", "PADRE_VERIFICATO_FIGLIO_APERTO" in cod(P(("A", "VERIFICATO", {"evidence": ["e"]}), ("A.1", "BLOCCATO", {"parent": "A", "blocker_reason": "x", "next_action": "y"}))))
v("figlio BLOCCATO non bloccante non blocca il padre", "PADRE_VERIFICATO_FIGLIO_APERTO" not in cod(P(("A", "VERIFICATO", {"evidence": ["e"]}), ("A.1", "BLOCCATO", {"parent": "A", "blocking": False, "blocker_reason": "x", "next_action": "y"}))))
v("BLOCCATO senza causa e prossimo passo", {"BLOCCO_SENZA_CAUSA", "BLOCCO_SENZA_PROSSIMO_PASSO"} <= cod(P(("A", "BLOCCATO"))))
v("VERIFICATO senza evidenza", "VERIFICATO_SENZA_EVIDENZA" in cod(P(("A", "VERIFICATO"))))
v("FATTO senza evidenza e verification=passed", "FATTO_SENZA_EVIDENZA" in cod(P(("A", "FATTO", {"verification": "passed"}))) and not cod(P(("A", "FATTO"))))
v("NON_NECESSARIO richiede motivo", "NON_NECESSARIO_SENZA_MOTIVO" in cod(P(("A", "NON_NECESSARIO"))) and not cod(P(("A", "NON_NECESSARIO", {"motivo": "dup"}))))
v("dipendenza mancante e ciclo", {"DIPENDENZA_MANCANTE", "CICLO_DIPENDENZE"} <= cod(P(("A", "DA_FARE", {"dipende_da": ["Z"]}), ("B", "DA_FARE", {"dipende_da": ["C"]}), ("C", "DA_FARE", {"dipende_da": ["B"]}))))
v("FATTO con dipendenza aperta", "COMPLETO_CON_DIPENDENZA_APERTA" in cod(P(("A", "DA_FARE"), ("B", "FATTO", {"dipende_da": ["A"]}))))
r = M.valida(P(("A", "FATTO", {"evidence": ["e"]}), ("B", "BLOCCATO", {"blocking": False, "blocker_reason": "limite", "next_action": "chip"})))
v("chiusura con limitazione non bloccante ammessa", r["chiudibile"] and M.chiusura_con_limitazioni(P(("B", "BLOCCATO", {"blocking": False}))) == ["B"])
v("chiusura con requisito bloccato NON ammessa", not M.valida(P(("B", "BLOCCATO", {"blocker_reason": "x", "next_action": "y"})))["chiudibile"])
v("percorso critico", M.percorso_critico(P(("A", "FATTO"), ("B", "DA_FARE", {"dipende_da": ["A"]}), ("C", "DA_FARE", {"dipende_da": ["B"]}), ("D", "DA_FARE"))) == ["B", "C"])

pi = P(("P6", "IN_CORSO"), ("P7", "DA_FARE"))
c = lambda t, cur="P6": M.classifica(t, pi, cur)
v("chiarimento", c("intendo dire le concluse, cioè quelle del 2025")["type"] == "clarification")
v("criterio di accettazione su passo esplicito", (lambda x: x["type"] == "acceptance_criteria_update" and x["target_step"] == "P7" and x["acceptance_changes"])(c("per P7 la tabella deve mostrare almeno 3 colonne")))
v("correzione", c("hai capito male, intendevo la tabella nativa")["type"] == "correction")
v("sottopasso", (lambda x: x["type"] == "subtask" and x["requires_plan_change"] and x["target_step"] == "P6")(c("per farlo serve anche misurare lo sticky")))
v("ramo indipendente", (lambda x: x["type"] == "independent_branch" and not x["blocking"])(c("inoltre aggiungi anche il filtro per ente")))
v("nuovo obiettivo", c("passiamo a un'altra dashboard per un nuovo cliente")["type"] == "new_objective")
v("ambiguo: prudente, mai scartato", (lambda x: x["ambiguo"] and x["type"] in ("subtask", "clarification"))(c("ok")))

# CLI in sandbox: transizioni, regressione, migrazione
tmp = Path(tempfile.mkdtemp()); env = {**os.environ, "FACTORY_ROOT": str(tmp / "radice"), "FACTORY_PIANO": str(tmp / "t" / "piano.yaml")}
(tmp / "t").mkdir()
(tmp / "t" / "piano.yaml").write_text("task: t\nsteps:\n- {id: P1, testo: uno, dipende_da: [], chi: agente, stato: fatto}\n- {id: P2, testo: due, dipende_da: [P1], chi: agente, stato: problema, dettaglio: boh}\n", encoding="utf-8")
cli = lambda *a: subprocess.run([sys.executable, str(ROOT / "fcore" / "piano.py"), *a], capture_output=True, text=True, env=env, cwd=ROOT)
x = cli("passo", "P1", "in_corso"); v("riaprire un passo FATTO senza regressione è rifiutato", x.returncode == 2 and "regressione" in x.stdout)
x = cli("passo", "P1", "in_corso", "--regressione", "il numero non torna"); v("con regressione dimostrata si riapre e resta nello storico", x.returncode == 0 and "regressione" in (tmp / "t" / "piano.yaml").read_text())
x = cli("migra"); v("migra: anteprima, nessuna scrittura", "anteprima" in x.stdout and "problema" in (tmp / "t" / "piano.yaml").read_text())
x = cli("migra", "--scrivi"); t = (tmp / "t" / "piano.yaml").read_text(); v("migra --scrivi: canonico + backup + storico", "stato: BLOCCATO" in t and "migrazione_stato" in t and list((tmp / "t").glob("piano.yaml.bak_*")))
x = cli("valida", "--strict"); v("valida --strict segnala il blocco senza prossimo passo (exit 1)", x.returncode == 1 and "BLOCCO_SENZA_PROSSIMO_PASSO" in x.stdout)
x = cli("evento", "per farlo serve anche un controllo", "--passo", "P2", "--applica"); t = (tmp / "t" / "piano.yaml").read_text()
v("evento subtask: sottopasso P2.1, nessuna rinumerazione, richiesta registrata", "id: P2.1" in t and "parent: P2" in t and "richieste:" in t and "id: P1" in t)
x = cli("evento", "inoltre aggiungi anche il filtro", "--applica"); v("evento ramo indipendente: R1", "id: R1" in (tmp / "t" / "piano.yaml").read_text())
shutil.rmtree(tmp)

# compatibilità: V62 (fixture, sola lettura) deve restare leggibile e invariato
v62 = ROOT / "08_LAVORI/in_corso/2026-10-13_V62_dash30_completamento/piano.yaml"
if v62.exists():
    import yaml, hashlib
    h = hashlib.sha256(v62.read_bytes()).hexdigest(); d = yaml.safe_load(v62.read_text(encoding="utf-8")); r = M.valida(d)
    v("V62 leggibile: nessuno stato sconosciuto", not any(a["codice"] == "STATO_SCONOSCIUTO" for a in r["anomalie"]), r["anomalie"][:2])
    v("V62 invariato dopo la lettura", hashlib.sha256(v62.read_bytes()).hexdigest() == h)
print(f"\n{ok} ok, {ko} KO"); sys.exit(1 if ko else 0)

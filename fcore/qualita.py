"""Controllo di qualita del piano, senza LLM: l'agente riceve subito poche righe su cosa migliorare.
Regole: ogni passo e UNA azione su un oggetto preciso (file, modulo, comando) con un controllo verificabile;
niente passi vaghi o segnaposto; baseline prima di cambiare; verifica alla fine; rami paralleli espliciti."""
import re
from pathlib import Path

try: from fcore import store as lib
except ImportError: from . import store as lib

VAGHI = re.compile(r"(?i)^\s*(analy[sz]e|analisi|analizza|check|controlla|review|improve|migliora|fix|sistema|handle|gestisci|investigate|verifica|look at|explore|esplora|understand|capire|work on|implement(?:a)?|update|aggiorna|refactor)\b\W*(?:the |il |la |lo |i |gli |le )?(?:code|codice|project|progetto|backend|frontend|app|things|cose|issue|problem|problema|stuff|it|everything|tutto)?\s*\.?\s*$")
SEGNAPOSTO = re.compile(r"(?i)\b(TBD|TODO|etc\.?|and so on|e cosi via|as needed|se serve|appropriate|appropriat[oa]|edge cases|casi limite|various|vari[ei])\b")
OGGETTO = re.compile(r"([\w.-]+[/\\][\w./\\-]+|\b[\w-]+\.(?:java|ts|tsx|js|py|xml|yml|yaml|json|md|sql|html|scss|css|properties|gradle|kt|go|rs|cs)\b|`[^`]+`|\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b|\b(?:mvnw?|gradlew?|npm|npx|ng|pytest|python|pip|git|grep|rg|go|cargo|dotnet|make|docker)\b)")
CAMBIA = re.compile(r"(?i)\b(modify|edit|change|add|write|create|refactor|fix|implement|rename|delete|remove|update|migrate|modifica|cambia|aggiungi|scrivi|crea|rifattorizza|correggi|implementa|rinomina|elimina|rimuovi|aggiorna)\b")
VERIFICA = re.compile(r"(?i)\b(test|tests|build|compile|verify|verifica|run|esegui|lint|baseline|confront|compare|diff|check)\b")
PARALLELO = re.compile(r"(?i)(parallel|parallelo|independent|indipendent|\bbranches\b|\brami\b|\bBE\b.*\bFE\b|backend.*frontend|frontend.*backend|subagent|sotto-agent)")   # "git branch" non e un ramo parallelo


def _livelli(steps):
    by = {s["id"]: s for s in steps}; liv = {}
    def L(i, vis=()):
        if i in liv: return liv[i]
        liv[i] = 0 if i in vis else max([L(x, vis + (i,)) + 1 for x in by[i].get("dipende_da", []) if x in by] or [0]); return liv[i]
    for i in by: L(i)
    return liv


def _nomi_progetto(rad):
    """Nomi utili dalla mappa del progetto (sottoprogetti, moduli): un passo che li cita ha un oggetto preciso."""
    f = Path(rad) / ".factory" / "CONTESTO.md"; nomi = set()
    try:
        for m in re.finditer(r"`([^`]+)`", f.read_text(encoding="utf-8")):
            for p in re.split(r"[/:\\ ]", m.group(1)):
                if len(p) > 3 and not p.startswith("-"): nomi.add(p.lower())
    except Exception: pass
    return nomi


def _comandi(rad):
    f = Path(rad) / ".factory" / "CONTESTO.md"
    try: return re.findall(r"^- ([\w./-]+: (?:build|test)): `([^`]+)`", f.read_text(encoding="utf-8"), re.M)
    except Exception: return []


def valuta(steps, richiesta="", rad=None):
    """-> (voto 0-10, [problemi in inglese per l'agente], [note in italiano per il pannello])"""
    rad = rad or lib.radice(); nomi = _nomi_progetto(rad); out, it = [], []
    def con_oggetto(t): return bool(OGGETTO.search(t)) or any(n in t.lower() for n in nomi)
    FINALE = re.compile(r"(?i)\b(summary|summari[sz]e|riepilogo|sintesi|report|answer|risposta|ask|chiedi|conclusion[ei]?)\b")
    vaghi = [s["id"] for s in steps if not FINALE.search(s["testo"]) and (VAGHI.match(s["testo"]) or (len(s["testo"].split()) < 3 and not con_oggetto(s["testo"])))]
    senza = [s["id"] for s in steps if s["id"] not in vaghi and not con_oggetto(s["testo"]) and not FINALE.search(s["testo"])]
    segn = [s["id"] for s in steps if SEGNAPOSTO.search(s["testo"])]
    cambia = [s for s in steps if CAMBIA.search(s["testo"])]
    voto = 10
    if vaghi: voto -= min(4, 2 * len(vaghi)); out.append("steps %s are vague: name the exact file, module or command (see .factory/CONTESTO.md)" % ",".join(vaghi)); it.append("passi vaghi: " + ", ".join(vaghi))
    if senza: voto -= min(2, len(senza)); out.append("steps %s have no object: add the file/module/command they act on" % ",".join(senza)); it.append("passi senza oggetto preciso: " + ", ".join(senza))
    if segn: voto -= 1; out.append("steps %s contain placeholders (TBD/etc/edge cases): spell them out" % ",".join(segn)); it.append("segnaposto nei passi: " + ", ".join(segn))
    if cambia:
        i0 = steps.index(cambia[0])
        if not any(VERIFICA.search(s["testo"]) for s in steps[:i0]): voto -= 1; out.append("add a baseline step (build/tests BEFORE the first change)"); it.append("manca la baseline prima della prima modifica")
        if not any(VERIFICA.search(s["testo"]) for s in steps[steps.index(cambia[-1]) + 1:]): voto -= 2; out.append("add a final verification step after the last change (tests vs baseline)"); it.append("manca la verifica dopo l'ultima modifica")
    n = len(steps)
    if n < 3: voto -= 1; out.append("only %d steps: show the whole job (3-5 for analysis, 6-12 for a change)" % n); it.append("troppo pochi passi (%d)" % n)
    if n > 15: voto -= 1; out.append("%d steps: merge the trivial ones (max ~12)" % n); it.append("troppi passi (%d)" % n)
    liv = _livelli(steps); larg = max([list(liv.values()).count(x) for x in set(liv.values())] or [0])
    if richiesta and PARALLELO.search(richiesta) and larg < 2: voto -= 2; out.append("the request has independent parts but the plan is a single chain: give independent steps `<-` (no dependency) or `<- A` so they show as parallel branches"); it.append("la richiesta chiede rami paralleli ma il piano e una catena")
    cm = _comandi(rad)
    if cm and (vaghi or senza or any(VERIFICA.search(s["testo"]) and not OGGETTO.search(s["testo"]) for s in steps)):
        out.append("project commands: " + "; ".join("%s=`%s`" % (k, v) for k, v in cm[:6]))
    return max(0, voto), out, it


def ultima_richiesta(rad=None):
    for e in reversed(lib.leggi_righe("eventi.jsonl", 400)):
        if str(e.get("tipo", "")).lower() in ("hook:userpromptsubmit", "hook:userpromptsubmitted") and e.get("testo"): return e["testo"]
    return ""

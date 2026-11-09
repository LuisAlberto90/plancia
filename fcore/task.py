#!/usr/bin/env python3
"""Registro dei task: ciclo DRAFT -> CONFERMATO -> IN_ESECUZIONE -> ESEGUITO -> VERIFICATO (chiusure alternative: ABBANDONATO, CONFLUITO).
  task apri <id> ["titolo"] [--da piano] [--analisi]   crea .factory/task/<id>/ con il piano, stato DRAFT, lo rende corrente
                                          --analisi: sola lettura (le guardie negano modifiche fuori da .factory/), nessuna conferma per avviare/chiudere
  task conferma <id> "frase della persona"  DRAFT -> CONFERMATO (la frase e obbligatoria: e la conferma esplicita della persona)
  task avvia <id>                           CONFERMATO -> IN_ESECUZIONE
  task eseguito <id>                        IN_ESECUZIONE -> ESEGUITO (rifiutato se il piano ha passi che bloccano la chiusura)
  task verifica <id> --utente NOME          ESEGUITO -> VERIFICATO: lo dichiara la persona, non l'agente
  task chiudi <id> abbandonato|confluito "motivo"
  task riprendi <id> | task elenco [--json] | task stato
Registro append-only: .factory/registro.jsonl (lo stato si calcola dalle righe, nessun file da tenere allineato)."""
import json, re, sys
from pathlib import Path
try: from . import store as lib, piano_modello as M, piano as P
except ImportError: import store as lib, piano_modello as M, piano as P

FLUSSO = ["DRAFT", "CONFERMATO", "IN_ESECUZIONE", "ESEGUITO", "VERIFICATO"]
CHIUSE = ("VERIFICATO", "ABBANDONATO", "CONFLUITO")
REG = "registro.jsonl"


def _id(x):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,60}", x or ""): raise SystemExit("id task non valido (lettere, numeri, . _ -): %r" % x)
    return x


def stati_task():
    """Calcola lo stato di ogni task dalle righe del registro."""
    out = {}
    for r in lib.leggi_righe(REG):
        t = out.setdefault(r.get("task_id"), {"id": r.get("task_id"), "stato": None, "titolo": "", "inizio": None, "fine": None, "esito": None, "storico": [], "cartella": None})
        if r.get("tipo") == "apri": t.update(titolo=r.get("titolo", ""), inizio=r["ts"], cartella=r.get("cartella"), analisi=bool(r.get("analisi")))
        t["stato"] = r.get("a") or t["stato"]
        t["storico"].append({k: r.get(k) for k in ("ts", "da", "a", "chi", "nota")})
        if r.get("a") in CHIUSE: t["fine"] = r["ts"]; t["esito"] = r["a"]
    cur = (lib.task_corrente() or {}).get("task_id")
    for t in out.values():
        t["corrente"] = t["id"] == cur
        t["piano"] = next((str(f) for f in (Path(t["cartella"] or "") / "piano.json", Path(t["cartella"] or "") / "piano.yaml") if f.exists()), None) if t["cartella"] else None
    return out


def _passa(tid, a, chi="agente", nota=None, ammessi=None):
    st = stati_task().get(tid)
    if not st: print("task %s inesistente (task elenco)" % tid); return 2
    da = st["stato"]
    if da in CHIUSE: print("task %s e gia chiuso (%s)" % (tid, da)); return 2
    if ammessi and da not in ammessi: print("task %s e %s: questo passaggio parte da %s" % (tid, da, "/".join(ammessi))); return 2
    lib.scrivi_riga(REG, {"ts": lib.ora(), "task_id": tid, "tipo": "stato", "da": da, "a": a, "chi": chi, "nota": lib.redigi(nota, 300) if nota else None})
    lib.evento("task_" + a.lower(), "task", task_id=tid, messaggio=lib.redigi(nota or ""))
    print("%s: %s -> %s" % (tid, da, a)); return 0


def apri(tid, titolo="", da=None, analisi=False):
    tid = _id(tid)
    if tid in stati_task(): print("task %s esiste gia (task riprendi %s)" % (tid, tid)); return 2
    c = lib.dir_() / "task" / tid
    if P.crea(str(c), da) != 0: return 2
    lib.scrivi_riga(REG, {"ts": lib.ora(), "task_id": tid, "tipo": "apri", "titolo": lib.redigi(titolo, 160), "cartella": str(c), "da": None, "a": "DRAFT", "chi": "agente", "analisi": analisi or None})
    lib.salva("task_corrente.json", {"task_id": tid, "cartella": str(c), "inizio": lib.ora()}); lib.evento("task_apri", "task", task_id=tid)
    if analisi: print("task %s aperto (DRAFT, sola analisi: nessuna modifica ai file del progetto). Piano: %s. Avvia con: task avvia %s" % (tid, c / "piano.json", tid)); return 0
    print("task %s aperto (DRAFT). Piano: %s. Niente parte finche la persona non conferma: task conferma %s \"<frase>\"" % (tid, c / "piano.json", tid)); return 0


def eseguito(tid):
    t = stati_task().get(tid)
    if t and t["piano"]:
        r = M.valida(lib.leggi(t["piano"]))
        if not r["chiudibile"]: print("task %s non puo passare a ESEGUITO: %s" % (tid, ("passi che bloccano: " + ", ".join(r["blocca_chiusura"][:8])) if r["blocca_chiusura"] else "il piano ha anomalie (piano valida)")); return 2
    if t and t.get("analisi") and t["stato"] in ("DRAFT", "CONFERMATO"): _passa(tid, "IN_ESECUZIONE")
    return _passa(tid, "ESEGUITO", ammessi=["IN_ESECUZIONE"])


def riprendi(tid):
    t = stati_task().get(tid)
    if not t: print("task %s inesistente" % tid); return 2
    if t["stato"] in CHIUSE: print("task %s chiuso (%s)" % (tid, t["stato"])); return 2
    lib.salva("task_corrente.json", {"task_id": tid, "cartella": t["cartella"], "inizio": t["inizio"]})
    if t["piano"]: lib.salva("piano_attivo.json", {"piano": str(Path(t["piano"]).resolve())})
    print("task %s ripreso (%s)" % (tid, t["stato"])); return 0


def elenco(a):
    ts = list(stati_task().values())
    if "--json" in a: print(json.dumps(ts, ensure_ascii=False)); return 0
    if not ts: print("nessun task (task apri <id>)"); return 0
    for t in ts[-15:]: print("%s %-12s %-14s %s" % ("*" if t["corrente"] else " ", t["id"][:12], t["stato"], t["titolo"][:50]))
    return 0


def main(a):
    if not a: print(__doc__); return 2
    c, r = a[0], a[1:]
    pos = [x for i, x in enumerate(r) if not x.startswith("--") and (i == 0 or r[i - 1] not in ("--utente", "--da"))]
    if c == "apri" and pos: return apri(pos[0], pos[1] if len(pos) > 1 else "", r[r.index("--da") + 1] if "--da" in r else None, "--analisi" in r)
    if c == "conferma" and len(pos) > 1: return _passa(_id(pos[0]), "CONFERMATO", chi="persona", nota=" ".join(pos[1:]), ammessi=["DRAFT"])
    if c == "conferma": print("serve la frase con cui la persona ha confermato: task conferma <id> \"ok, procedi\""); return 2
    if c == "avvia" and pos:
        t = stati_task().get(_id(pos[0])) or {}
        return _passa(pos[0], "IN_ESECUZIONE", ammessi=["DRAFT", "CONFERMATO"] if t.get("analisi") else ["CONFERMATO"])
    if c == "eseguito" and pos: return eseguito(_id(pos[0]))
    if c == "verifica" and pos:
        if "--utente" not in r: print("VERIFICATO lo dichiara la persona: task verifica <id> --utente NOME"); return 2
        return _passa(_id(pos[0]), "VERIFICATO", chi="persona:" + r[r.index("--utente") + 1], ammessi=["ESEGUITO"])
    if c == "chiudi" and len(pos) > 1 and pos[1].lower() in ("abbandonato", "confluito"): return _passa(_id(pos[0]), pos[1].upper(), nota=" ".join(pos[2:]) or None)
    if c == "riprendi" and pos: return riprendi(_id(pos[0]))
    if c == "elenco": return elenco(r)
    if c == "stato":
        cur = lib.task_corrente(); t = stati_task().get((cur or {}).get("task_id")) if cur else None
        print("nessun task corrente" if not t else "%s: %s - %s" % (t["id"], t["stato"], t["titolo"])); return 0
    print(__doc__); return 2


if __name__ == "__main__": sys.exit(main(sys.argv[1:]))

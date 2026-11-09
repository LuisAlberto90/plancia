#!/usr/bin/env python3
"""Handoff: lascia lo stato per la prossima sessione o per un collega.
  handoff                 scrive .factory/STATE.md (task corrente, passi, blocchi, ultimi eventi) e CHECKPOINT.md nella cartella del task
  handoff mostra          stampa STATE.md
Per riprendere senza trascrizione: STATE.md + CHECKPOINT.md del task + piano."""
import sys
from pathlib import Path
try: from . import store as lib, piano_modello as M, task as T
except ImportError: import store as lib, piano_modello as M, task as T


def costruisci():
    ts = T.stati_task(); cur = (lib.task_corrente() or {}).get("task_id"); t = ts.get(cur) if cur else None
    righe = ["# Stato del lavoro", "", "Aggiornato: " + lib.ora(), ""]
    if not t: righe += ["Nessun task corrente. Ultimi task:", ""] + ["- %s: %s %s" % (x["id"], x["stato"], x["titolo"]) for x in list(ts.values())[-5:]]
    else:
        righe += ["## Task corrente: %s (%s)" % (t["id"], t["stato"]), t["titolo"], ""]
        if t["piano"]:
            d = lib.leggi(t["piano"]); r = M.valida(d)
            righe += ["## Passi", ""] + ["- [%s] %s: %s%s" % (M.canon(s.get("stato")), s["id"], s.get("testo", ""), (" - " + s["dettaglio"]) if s.get("dettaglio") else "") for s in d["steps"]]
            if r["blocca_chiusura"]: righe += ["", "Bloccano la chiusura: " + ", ".join(r["blocca_chiusura"])]
            righe += ["", "Prossimo passo: " + (next((s["id"] + " " + s.get("testo", "") for s in d["steps"] if M.canon(s.get("stato")) in ("IN_CORSO", "DA_FARE")), "nessuno: tutto completato"))]
        righe += ["", "## Come riprendere", "", "1. Leggi questo file e il piano.", "2. `" + lib.comando() + " task riprendi %s`" % t["id"], "3. Continua dal prossimo passo."]
    ev = lib.leggi_righe("eventi.jsonl", 8)
    if ev: righe += ["", "## Ultimi eventi", ""] + ["- %s %s %s" % (e.get("ts"), e.get("tipo"), e.get("messaggio") or e.get("passo") or "") for e in ev]
    return "\n".join(righe) + "\n", t


def main(a):
    if lib.modo() == "leggera" and a[:1] != ["mostra"]:
        try: from . import richieste as RQ
        except ImportError: import richieste as RQ
        testo = RQ.riprendere(RQ.tutte(lib.radice()), lib.leggi_righe("eventi.jsonl", 200))
        if not testo: print("nessuna richiesta trovata nelle sessioni di questo progetto"); return 0
        lib.dir_().mkdir(parents=True, exist_ok=True); (lib.dir_() / "RIPRENDERE.md").write_text(testo, encoding="utf-8")
        lib.evento("handoff", "handoff"); print("scritto %s (dalle sessioni, nessun LLM)" % (lib.dir_() / "RIPRENDERE.md")); return 0
    if a[:1] == ["mostra"]:
        p = lib.dir_() / "STATE.md"; print(p.read_text(encoding="utf-8") if p.exists() else "nessun handoff (handoff)"); return 0
    testo, t = costruisci(); lib.dir_().mkdir(parents=True, exist_ok=True)
    (lib.dir_() / "STATE.md").write_text(testo, encoding="utf-8")
    if t and t["cartella"] and Path(t["cartella"]).is_dir(): (Path(t["cartella"]) / "CHECKPOINT.md").write_text(testo, encoding="utf-8")
    lib.scrivi_riga("handoff.jsonl", {"ts": lib.ora(), "task_id": t and t["id"], "stato": t and t["stato"]}); lib.evento("handoff", "handoff")
    print("scritto %s%s" % (lib.dir_() / "STATE.md", " e CHECKPOINT.md del task" if t else "")); return 0


if __name__ == "__main__": sys.exit(main(sys.argv[1:]))

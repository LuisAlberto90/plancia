"""plancia archivia  — mette da parte lo storico (piani, eventi, prove) per ripartire puliti. Nulla si cancella:
tutto va in .factory/archivio/<data-ora>/ e da quel momento pannello e prove ignorano le sessioni precedenti."""
import json, shutil, time
try: from . import store as lib
except ImportError: import store as lib

DA_SPOSTARE = ["piani", "prove.jsonl", "eventi.jsonl", "piano_attivo.json", "RIPRENDERE.md"]


def archivia(scrivi=True):
    fac = lib.dir_()
    if not fac.is_dir(): print("Questa cartella non ha la Plancia (.factory mancante)."); return 2
    dest = fac / "archivio" / time.strftime("%Y%m%d-%H%M%S"); mossi = []
    for n in DA_SPOSTARE:
        p = fac / n
        if p.exists():
            mossi.append(n)
            if scrivi: dest.mkdir(parents=True, exist_ok=True); shutil.move(str(p), str(dest / n))
    if scrivi:
        (fac / "piani").mkdir(exist_ok=True)
        c = lib.config(); c["storico_da"] = time.time()
        (fac / "config.json").write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(("Archiviato in %s: %s" % (dest, ", ".join(mossi) or "niente")) if scrivi else "Archivierei: " + ", ".join(mossi))
    print("Il pannello ora mostra solo il lavoro da adesso in poi. Per rivedere il vecchio: apri la cartella archivio.")
    return 0


def da():
    """Epoch da cui mostrare il lavoro (0 = tutto)."""
    try: return float(lib.config().get("storico_da") or 0)
    except Exception: return 0.0

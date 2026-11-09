"""Zip di diagnosi da mandare a chi supporta la Plancia, SENZA codice sorgente.
  plancia diagnosi        crea .factory/diagnosi-<data>.zip
Contiene: versione, sistema, mappa del progetto, struttura delle cartelle (solo nomi e dimensioni), configurazioni Plancia, eventi e piani
(gia ripuliti dai segreti), esiti delle prove, riepilogo delle richieste (risposte accorciate), e l'errore esatto se il pannello si rompe.
Non contiene: contenuto dei file del progetto, trascrizioni complete degli agenti, file .env o chiavi."""
import io, json, os, platform, sys, time, traceback, zipfile
from pathlib import Path
try: from . import store as lib
except ImportError: import store as lib


def _prova(nome, fn):
    try: return {"ok": True, "esito": fn()}
    except Exception: return {"ok": False, "errore": traceback.format_exc()[-4000:]}


def main(a):
    if a[:1] in (["-h"], ["--help"]): print(__doc__); return 0
    rad = lib.radice(); fd = lib.dir_(); out = {}
    from . import mcp, contesto, pannello, panoramica, richieste as RQ
    out["versione"] = mcp.VERSIONE; out["sistema"] = {"os": platform.platform(), "python": sys.version, "comando": lib.comando(), "progetto": str(rad), "modo": lib.modo(), "config": lib.config()}
    out["pannello"] = _prova("pannello", lambda: {k: (v if k in ("salute", "nota_piano", "modo") else (len(v) if isinstance(v, list) else None)) for k, v in pannello.stato_pannello(False).items()})
    out["panoramica"] = _prova("panoramica", lambda: [{k: p[k] for k in ("nome", "stato", "attenzione")} | {"sessioni": [{k: s.get(k) for k in ("fonte", "stato", "eta", "da_hook")} for s in p["sessioni"]]} for p in panoramica.tutte()["progetti"]])
    out["richieste"] = _prova("richieste", lambda: [dict(r, risposta=(r.get("risposta") or "")[:200]) for r in RQ.tutte(rad, 15)])
    struttura = []
    for d, dirs, fs in os.walk(rad):
        dirs[:] = sorted(x for x in dirs if x not in contesto.SALTA and not x.startswith("."))
        rel = Path(d).relative_to(rad)
        for x in fs:
            if len(struttura) >= 4000: break
            try: struttura.append("%s\t%d" % ((rel / x).as_posix(), (Path(d) / x).stat().st_size))
            except Exception: pass
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("diagnosi.json", json.dumps(out, indent=1, ensure_ascii=False, default=str))
        z.writestr("struttura.txt", "\n".join(struttura))
        z.writestr("CONTESTO.md", _prova("ctx", lambda: contesto.mappa(rad))["esito"] or "")
        for f in ("config.json", "policy.json", "prove.jsonl", "eventi.jsonl", "piano_attivo.json"):
            p = fd / f
            if p.exists():
                t = p.read_text(encoding="utf-8", errors="replace"); z.writestr(".factory/" + f, "\n".join(t.splitlines()[-1500:]) if f.endswith(".jsonl") else t)
        for p in sorted((fd / "piani").glob("*.json"))[-15:] if (fd / "piani").is_dir() else []: z.writestr(".factory/piani/" + p.name, p.read_text(encoding="utf-8", errors="replace"))
        for p in (rad / ".claude" / "settings.json", rad / ".github" / "hooks" / "plancia.json", rad / ".vscode" / "mcp.json", rad / "AGENTS.md"):
            if p.exists(): z.writestr("config_progetto/" + p.relative_to(rad).as_posix(), lib.redigi_testo(p.read_text(encoding="utf-8", errors="replace"), 20000))
    f = fd / ("diagnosi-%s.zip" % time.strftime("%Y%m%d-%H%M%S")); fd.mkdir(parents=True, exist_ok=True); f.write_bytes(buf.getvalue())
    print("scritto %s (%d KB). Contiene struttura, configurazioni, eventi e piani: nessun file sorgente." % (f, len(buf.getvalue()) // 1024))
    if not out["pannello"]["ok"]: print("ATTENZIONE: il pannello va in errore su questo progetto: l'errore e dentro lo zip (diagnosi.json).")
    return 0


if __name__ == "__main__": sys.exit(main(sys.argv[1:]))

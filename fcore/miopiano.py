"""Il mio piano: i limiti dei tuoi abbonamenti, per misurare i consumi in "% del limite" invece che in token.
- Claude: letti in automatico dalla statusline di Claude Code (rate_limits: sessione 5 ore e settimana), salvati in ~/.plancia/limiti.json. Zero rete, zero credenziali.
- Copilot: il tetto e il giorno di reset stanno sui server GitHub e non esistono in locale: si scrivono una volta (~/.plancia/miopiano.json).
Vuoto di default: finche non lo compili la pagina Consumi mostra solo token. Mai nessuna scrittura in settings.json senza `limiti-installa --scrivi`."""
import json, os, re, sys, time
from pathlib import Path

UNITA = ("richieste", "crediti")
STATUSLINE = '''"""Plancia: salva i limiti di Claude Code (sessione e settimana) in ~/.plancia/limiti.json e stampa una riga corta. Mai bloccante."""
import json, os, subprocess, sys, time
from pathlib import Path
casa = Path(os.environ.get("PLANCIA_HOME") or Path.home() / ".plancia")
raw = sys.stdin.read()
try:
    d = json.loads(raw); rl = d.get("rate_limits") or {}; out = {"t": int(time.time())}
    for k in ("five_hour", "seven_day"):
        x = rl.get(k) or {}
        if x.get("used_percentage") is not None: out[k] = {"pct": float(x["used_percentage"]), "reset": x.get("resets_at")}
    if len(out) > 1:
        casa.mkdir(parents=True, exist_ok=True); tmp = casa / "limiti.json.tmp"; tmp.write_text(json.dumps(out), encoding="utf-8"); os.replace(tmp, casa / "limiti.json")
except Exception: pass
try:
    nxt = (casa / "statusline_next.txt").read_text(encoding="utf-8").strip()
except Exception: nxt = ""
if nxt:
    try: sys.stdout.write(subprocess.run(nxt, input=raw, capture_output=True, text=True, shell=True, timeout=5).stdout)
    except Exception: pass
else:
    try:
        a = (json.loads(raw).get("rate_limits") or {}); f, s = (a.get("five_hour") or {}).get("used_percentage"), (a.get("seven_day") or {}).get("used_percentage")
        if f is not None or s is not None: print("5h %s%% . 7g %s%%" % ("-" if f is None else round(f), "-" if s is None else round(s)))
    except Exception: pass
'''


def casa(): return Path(os.environ.get("PLANCIA_HOME") or Path.home() / ".plancia")


def _leggi(nome, difetto):
    try: return json.loads((casa() / nome).read_text(encoding="utf-8"))
    except Exception: return difetto


def _num(v, lo, hi):
    try: x = float(v)
    except (TypeError, ValueError): raise ValueError("numero non valido") from None
    if not (lo <= x <= hi) or x != x: raise ValueError("numero fuori misura")
    return x


def impostazioni():
    """Quello che hai scritto tu (Copilot) piu quello che Claude Code ha comunicato (limiti.json). Sempre completo, mai un errore."""
    s = _leggi("miopiano.json", {}); c = s.get("copilot") if isinstance(s.get("copilot"), dict) else {}
    lim = _leggi("limiti.json", {})
    cl = {"auto": bool(lim.get("five_hour") or lim.get("seven_day")), "aggiornato": int(lim.get("t") or 0), "cinque_ore": lim.get("five_hour"), "sette_giorni": lim.get("seven_day"),
          "installata": statusline_installata(), "comando": comando_installa()}
    mol = c.get("moltiplicatori") if isinstance(c.get("moltiplicatori"), dict) else {}
    return {"adesso": int(time.time()), "claude": cl,
            "copilot": {"unita": c.get("unita") if c.get("unita") in UNITA else "", "tetto": c.get("tetto") or 0, "reset_giorno": c.get("reset_giorno") or 0,
                        "usati": c.get("usati") or 0, "usati_t": c.get("usati_t") or 0, "moltiplicatori": {str(k)[:60]: v for k, v in mol.items() if isinstance(v, (int, float))}}}


def salva(d):
    """Scrive solo i campi di Copilot, validati. ValueError se qualcosa non torna."""
    if not isinstance(d, dict): raise ValueError("richiesta non valida")
    c = d.get("copilot") if isinstance(d.get("copilot"), dict) else {}; out = {}
    if c.get("unita") not in UNITA + ("",): raise ValueError("unita non valida")
    out["unita"] = c.get("unita") or ""
    out["tetto"] = _num(c.get("tetto") or 0, 0, 10_000_000); out["reset_giorno"] = int(_num(c.get("reset_giorno") or 0, 0, 31))
    out["usati"] = _num(c.get("usati") or 0, 0, 10_000_000); out["usati_t"] = int(time.time()) if out["usati"] else 0
    mol = c.get("moltiplicatori") if isinstance(c.get("moltiplicatori"), dict) else {}
    if len(mol) > 60: raise ValueError("troppi modelli")
    out["moltiplicatori"] = {re.sub(r"[^\w.\- /:]", "", str(k))[:60]: _num(v, 0, 1000) for k, v in mol.items() if str(k).strip()}
    casa().mkdir(parents=True, exist_ok=True); p = casa() / "miopiano.json"; tmp = casa() / "miopiano.json.tmp"
    tmp.write_text(json.dumps({"copilot": out}, ensure_ascii=False, indent=1), encoding="utf-8"); os.replace(tmp, p)
    return {"ok": True}


def _settings_claude(): return Path.home() / ".claude" / "settings.json"


def comando_installa():
    return '%s "%s" limiti-installa --scrivi' % ("python" if os.name == "nt" else "python3", Path(__file__).resolve().parent.parent / "factory.py")


def _nostro(cmd): return "statusline.py" in str(cmd) and ".plancia" in str(cmd).replace("\\", "/")


def statusline_installata():
    try: return _nostro(((json.loads(_settings_claude().read_text(encoding="utf-8")).get("statusLine")) or {}).get("command"))
    except Exception: return False


def installa(scrivi, out, rimuovi=False):
    """Mette (o toglie) la statusline Plancia in ~/.claude/settings.json. A vuoto di default. Se ne avevi gia una, la richiama: non la perdi."""
    sp = _settings_claude()
    try: cfg = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    except Exception: out.append("settings.json di Claude Code non leggibile: non lo tocco."); return 1
    if not isinstance(cfg, dict): out.append("settings.json di Claude Code non e un oggetto: non lo tocco."); return 1
    c = casa(); script = c / "statusline.py"; nxt = c / "statusline_next.txt"; cur = cfg.get("statusLine") if isinstance(cfg.get("statusLine"), dict) else {}
    if rimuovi:
        if not _nostro(cur.get("command")): out.append("La statusline di Claude Code non e quella di Plancia: niente da togliere."); return 0
        prev = nxt.read_text(encoding="utf-8").strip() if nxt.exists() else ""
        if prev: cfg["statusLine"] = {"type": "command", "command": prev}
        else: cfg.pop("statusLine", None)
        out.append(("ripristinata la statusline precedente" if prev else "tolta la statusline di Plancia") + " in " + str(sp))
    else:
        cmd = '%s "%s"' % (sys.executable or "python3", script)
        if _nostro(cur.get("command")): out.append("Gia attiva: " + str(sp));
        else:
            if cur.get("command") and scrivi: c.mkdir(parents=True, exist_ok=True); nxt.write_text(str(cur["command"]), encoding="utf-8")
            cfg["statusLine"] = {"type": "command", "command": cmd}
            out.append(("impostata" if scrivi else "imposterei") + " la statusline di Plancia in %s%s" % (sp, " (la tua precedente continua a funzionare: la richiama lei)" if cur.get("command") else ""))
    if not scrivi: out.append("(prova a vuoto: aggiungi --scrivi per applicare)"); return 0
    try:
        c.mkdir(parents=True, exist_ok=True); script.write_text(STATUSLINE, encoding="utf-8")
        sp.parent.mkdir(parents=True, exist_ok=True)
        if sp.exists(): (sp.parent / "settings.json.plancia.bak").write_text(sp.read_text(encoding="utf-8"), encoding="utf-8")
        tmp = sp.parent / "settings.json.tmp"; tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"); os.replace(tmp, sp)
    except OSError as e: out.append("non riesco a scrivere: %s" % e); return 1
    return 0


def main(a, rimuovi=False):
    out = []; r = installa("--scrivi" in a, out, rimuovi); print("\n".join(out)); return r

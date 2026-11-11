"""Chat di VS Code (Copilot Chat): legge le sessioni salvate da VS Code sul PC, in sola lettura, zero token e zero rete.
VS Code le tiene in <User>/workspaceStorage/<hash>/chatSessions/*.json|jsonl; workspace.json dice a quale cartella appartiene l'hash.
Se la sessione contiene i token reali (promptTokens/outputTokens) si usano; altrimenti si STIMA dal testo scambiato (4 caratteri = 1 token),
e il numero e marcato come stima: e un minimo, perche il contesto che l'agente rilegge (file, istruzioni, strumenti) non e nel testo salvato."""
import json, os, re, time
from pathlib import Path
from urllib.parse import unquote

_C = {}


def _utenti():
    h = Path.home(); out = []
    if os.name == "nt": base = Path(os.environ.get("APPDATA") or h / "AppData" / "Roaming")
    elif os.uname().sysname == "Darwin": base = h / "Library" / "Application Support"
    else: base = h / ".config"
    for n in ("Code", "Code - Insiders", "VSCodium"):
        if (base / n / "User" / "workspaceStorage").is_dir(): out.append(base / n / "User")
    return out


def _norm(p):
    p = unquote(str(p))
    if p.startswith("file://"): p = p[7:]
    p = p.replace("\\", "/").rstrip("/")
    if len(p) > 2 and p[0] == "/" and p[2] == ":": p = p[1:]               # /c:/Users/x -> c:/Users/x
    return p.lower() if (os.name == "nt" or (len(p) > 1 and p[1] == ":")) else p


def _cartella(ws):
    try: return _norm(json.loads((ws / "workspace.json").read_text(encoding="utf-8")).get("folder") or "")
    except Exception: return ""


def _leggi(f):
    """Una sessione -> dict con `requests`. Gestisce il .json intero e il .jsonl a mutazioni (kind 0 = stato, 1 = imposta, 2 = aggiunge)."""
    t = Path(f).read_text(encoding="utf-8", errors="replace")
    if str(f).endswith(".json"):
        try: return json.loads(t)
        except Exception: return {}
    s = {}
    for riga in t.splitlines():
        try: m = json.loads(riga)
        except Exception: continue
        k, v, kind = m.get("k") or [], m.get("v"), m.get("kind")
        if kind == 0 and isinstance(v, dict): s = v; continue
        cur = s
        try:
            for p in k[:-1]: cur = cur[p]
            if kind == 1 and k: cur[k[-1]] = v
            elif kind == 2:
                dst = cur[k[-1]] if k else s
                i = m.get("i")
                if isinstance(dst, list) and isinstance(v, list):
                    if i is None: dst.extend(v)
                    else: dst[i:] = v
        except Exception: continue
    return s


def _testo(x, prof=0):
    """Tutto il testo leggibile dentro una risposta (stringhe `value`/`text`/`content`), senza i dettagli degli strumenti."""
    if prof > 6: return ""
    if isinstance(x, str): return x
    if isinstance(x, list): return "\n".join(_testo(i, prof + 1) for i in x)
    if isinstance(x, dict):
        if str(x.get("kind") or "").startswith("toolInvocation"): return ""
        return "\n".join(_testo(x[k], prof + 1) for k in ("value", "text", "content") if k in x)
    return ""


def _num(x, nomi):
    """Primo valore numerico trovato con uno di questi nomi, ovunque dentro `x`."""
    if isinstance(x, dict):
        for k, v in x.items():
            if k in nomi and isinstance(v, (int, float)) and v > 0: return int(v)
        for v in x.values():
            r = _num(v, nomi)
            if r: return r
    elif isinstance(x, list):
        for v in x[:50]:
            r = _num(v, nomi)
            if r: return r
    return 0


def richieste(rad, giorni_max=None):
    """Richieste della chat di VS Code per la cartella `rad`: [{inizio, domanda, token_in, token_out, stimato, modello}]. Mai un errore."""
    chiave = str(rad); ora = time.time()
    if chiave in _C and ora - _C[chiave][0] < 60: return _C[chiave][1]
    mia = _norm(rad); out = []
    for u in _utenti():
        for ws in (u / "workspaceStorage").glob("*"):
            if _cartella(ws) != mia: continue
            for f in list((ws / "chatSessions").glob("*.json")) + list((ws / "chatSessions").glob("*.jsonl")):
                try: sess = _leggi(f)
                except Exception: continue
                for q in sess.get("requests") or []:
                    try:
                        dom = (q.get("message") or {}).get("text") or ""
                        ris = _testo(q.get("response"))
                        res = q.get("result") or {}
                        ti = _num(res, ("promptTokens", "inputTokens")); to = _num(res, ("outputTokens", "completionTokens"))
                        stim = not (ti or to)
                        if stim: ti, to = max(1, len(dom) // 4), len(ris) // 4
                        ts = q.get("timestamp") or sess.get("creationDate") or 0
                        ini = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts / 1000)) if ts else ""
                        out.append({"inizio": ini, "domanda": dom, "token_in": ti, "token_out": to, "stimato": stim, "modello": str(q.get("modelId") or (res.get("metadata") or {}).get("modelId") or "")[:40]})
                    except Exception: continue
    out.sort(key=lambda r: r["inizio"], reverse=True)
    _C[chiave] = (ora, out)
    return out


CAMPO = re.compile(r"(?i)token|context|window|limit|usage|cache|prompt|output|input|budget|total")


def _numeri(x, perc, out, prof=0):
    """Raccoglie i percorsi dei campi NUMERICI il cui nome parla di token/contesto. Mai testo, mai valori stringa."""
    if prof > 12: return
    if isinstance(x, dict):
        for k, v in x.items():
            p = perc + "." + str(k)[:40]
            if isinstance(v, bool): continue
            if isinstance(v, (int, float)):
                if CAMPO.search(str(k)): d = out.setdefault(p, [0, v, v]); d[0] += 1; d[1] = min(d[1], v); d[2] = max(d[2], v)
            else: _numeri(v, p, out, prof + 1)
    elif isinstance(x, list):
        for v in x[:200]: _numeri(v, perc + "[]", out, prof + 1)


def struttura(max_file=4):
    """Diagnosi: dove VS Code salva i dati della chat e quali campi numerici (token, contesto) contengono. SOLO nomi di campi e numeri: nessun testo di conversazione."""
    righe = []
    for u in _utenti():
        righe.append("VS Code: %s" % u.parent.name)
        ws_tutti = sorted((u / "workspaceStorage").glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
        righe.append("  cartelle di lavoro: %d" % len(ws_tutti))
        visti = 0
        for ws in ws_tutti:
            cart = {"chatSessions": ws / "chatSessions", "debug-logs": ws / "GitHub.copilot-chat" / "debug-logs", "transcripts": ws / "GitHub.copilot-chat" / "transcripts"}
            if not any(p.is_dir() for p in cart.values()): continue
            visti += 1
            if visti > max_file: break
            righe.append("  [%s]" % ws.name[:8])
            for nome, d in cart.items():
                if not d.is_dir(): continue
                fs = sorted((f for f in d.rglob("*") if f.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)
                righe.append("    %s: %d file, es. %s" % (nome, len(fs), ", ".join("%s (%d KB)" % (f.suffix or "?", f.stat().st_size // 1024) for f in fs[:3])))
                for f in fs[:2]:
                    if f.suffix not in (".json", ".jsonl"): continue
                    num = {}
                    try:
                        t = f.read_text(encoding="utf-8", errors="replace")
                        if f.suffix == ".json": _numeri(json.loads(t), "", num)
                        else:
                            for riga in t.splitlines()[:3000]:
                                try: _numeri(json.loads(riga), "", num)
                                except Exception: continue
                    except Exception: pass
                    for p, (n, lo, hi) in sorted(num.items())[:40]: righe.append("      %s  x%d  min %s  max %s" % (p, n, lo, hi))
                    if not num: righe.append("      (%s: nessun campo numerico di token/contesto)" % f.suffix)
    return "\n".join(righe) or "Nessuna installazione di VS Code trovata."

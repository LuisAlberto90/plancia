"""Modello canonico del piano (Lotto 2, V-63): stati, validatore deterministico, classificazione delle richieste. Nessun LLM, nessuna scrittura: funzioni pure.
Compatibilità: i piani storici (stati minuscoli: da_fare/in_corso/fatto/problema/bloccato/aspetta_utente) restano leggibili; canon() li traduce SOLO in lettura.
Passo (campi opzionali oltre a quelli di piano.py): stato canonico, verification (none|pending|partial|passed), blocking (bool, default true se BLOCCATO), blocker_type
(capability|dato|utente|ambiente|tecnico), blocker_reason, next_action, progress, evidence[], started_at, completed_at, agent, resource, acceptance_criteria[], parent, motivo, history[]."""
import re

CANON = ("DA_FARE", "IN_CORSO", "FATTO", "VERIFICATO", "BLOCCATO", "NON_NECESSARIO")
LEGACY = {"da_fare": "DA_FARE", "in_corso": "IN_CORSO", "fatto": "FATTO", "bloccato": "BLOCCATO", "problema": "BLOCCATO", "aspetta_utente": "BLOCCATO"}
# stato legacy → (blocker_type implicito, ambiguo?): «problema» non dice se è un blocco vero → la migrazione lo registra, non lo decide
LEGACY_NOTA = {"problema": ("tecnico", True), "aspetta_utente": ("utente", False), "bloccato": (None, True)}
VERIFICATION = ("none", "pending", "partial", "passed")
TIPI_RICHIESTA = ("clarification", "acceptance_criteria_update", "correction", "subtask", "independent_branch", "new_objective")
COMPLETI = ("FATTO", "VERIFICATO", "NON_NECESSARIO")

def canon(s):
    """Stato canonico di uno stato scritto in qualunque forma (None se sconosciuto)."""
    s = (s or "da_fare").strip()
    return s.upper() if s.upper() in CANON else LEGACY.get(s.lower())

# Semantica dei quattro assi (indipendenti, mai dedotti dalla precedenza degli operatori):
#   stato (status)   dove è il passo: DA_FARE / IN_CORSO / FATTO / VERIFICATO / BLOCCATO / NON_NECESSARIO
#   verification     quanto è provato: none / pending / partial / passed (non influisce sulla chiusura, genera solo avvisi)
#   required         il passo serve al risultato del task (default True; NON_NECESSARIO implica False)
#   blocking         se il passo è BLOCCATO, il blocco impedisce la chiusura (default True: prudente)
def obbligatorio(p):
    """True se il passo è necessario per il risultato del task (asse `required`)."""
    if canon(p.get("stato")) == "NON_NECESSARIO":
        return False                                   # dichiarato non necessario (con motivo): mai richiesto
    return p.get("required", True) is not False        # solo un `required: false` esplicito lo toglie dal risultato

def bloccante(p):
    """True se il passo è BLOCCATO e il blocco impedisce la chiusura (asse `blocking`, vale solo per i passi obbligatori)."""
    if canon(p.get("stato")) != "BLOCCATO":
        return False
    if not obbligatorio(p):
        return False                                   # un passo opzionale bloccato non ferma il task
    return p.get("blocking", True) is not False        # prudente: senza dichiarazione, il blocco è bloccante

def blocca_chiusura(p):
    """True se il passo impedisce la chiusura del task: obbligatorio e (non iniziato | in corso | bloccato in modo bloccante)."""
    if not obbligatorio(p):
        return False
    c = canon(p.get("stato"))
    if c in ("DA_FARE", "IN_CORSO"):
        return True
    return bloccante(p)

def figli(steps, pid): return [s for s in steps if s.get("parent") == pid]

def _ciclo(g):
    """Ciclo in un grafo {nodo: [nodi]} → lista del ciclo o None."""
    stato = {}
    def vai(n, via):
        stato[n] = 1
        for m in g.get(n, []):
            if m not in g: continue
            if stato.get(m) == 1: return via + [n, m]
            if m not in stato:
                r = vai(m, via + [n])
                if r: return r
        stato[n] = 2
    for n in g:
        if n not in stato:
            r = vai(n, [])
            if r: return r
    return None

def valida(d):
    """→ {valido, anomalie:[{passo,codice,testo,suggerimento}], legacy:[passo], blocca_chiusura:[passo], chiudibile}. Non corregge nulla."""
    steps = d.get("steps", []); ids = [s.get("id") for s in steps]; per = {s.get("id"): s for s in steps}; an = []; avv = []; legacy = []; st = {}
    def a(p, codice, testo, sugg): an.append({"passo": p, "codice": codice, "testo": testo, "suggerimento": sugg})
    def w(p, codice, testo, sugg): avv.append({"passo": p, "codice": codice, "testo": testo, "suggerimento": sugg})
    for i in {x for x in ids if ids.count(x) > 1}: a(i, "ID_DUPLICATO", "id duplicato", "rinominare uno dei due; mai rinumerare i passi esistenti")
    for s in steps:
        i = s.get("id"); c = canon(s.get("stato")); st[i] = c
        if c is None: a(i, "STATO_SCONOSCIUTO", f"stato «{s.get('stato')}»", "usare " + "|".join(CANON)); continue
        if str(s.get("stato")) != c: legacy.append(i)
        if s.get("verification", "none") not in VERIFICATION: a(i, "VERIFICATION", f"verification «{s.get('verification')}»", "|".join(VERIFICATION))
        for x in s.get("dipende_da") or []:
            if x not in per: a(i, "DIPENDENZA_MANCANTE", f"dipende da {x} inesistente", "correggere dipende_da")
        if s.get("parent") and s["parent"] not in per: a(i, "PADRE_MANCANTE", f"parent {s['parent']} inesistente", "correggere parent")
        ev = s.get("evidence") or []
        if c == "BLOCCATO":
            if not (s.get("blocker_reason") or s.get("dettaglio")): a(i, "BLOCCO_SENZA_CAUSA", "BLOCCATO senza blocker_reason", "indicare la causa")
            if not s.get("next_action"): a(i, "BLOCCO_SENZA_PROSSIMO_PASSO", "BLOCCATO senza next_action", "indicare il prossimo passo")
        if c == "VERIFICATO" and not ev: a(i, "VERIFICATO_SENZA_EVIDENZA", "VERIFICATO senza evidence", "aggiungere almeno un'evidenza o riportare a FATTO")
        if c == "VERIFICATO" and s.get("verification") in ("none", "pending", "partial"): a(i, "VERIFICATO_VERIFICATION_INCOERENTE", f"VERIFICATO ma verification={s['verification']}", "impostare verification=passed o riportare a FATTO")
        if c == "FATTO" and obbligatorio(s) and s.get("verification", "pending") in ("none", "pending", "partial"): w(i, "FATTO_NON_VERIFICATO", f"FATTO, verification={s.get('verification', 'pending')}", "verificare e portare a VERIFICATO con evidenza")
        if c == "BLOCCATO" and s.get("blocking") is False: w(i, "LIMITAZIONE_NON_BLOCCANTE", "BLOCCATO non bloccante: la chiusura è ammessa con limitazione documentata", "riportarla nel checkpoint di chiusura")
        if c == "FATTO" and not ev and s.get("verification", "pending") == "passed": a(i, "FATTO_SENZA_EVIDENZA", "FATTO senza evidenza ma verification=passed", "impostare verification=pending")
        if c == "NON_NECESSARIO" and not s.get("motivo"): (w if d.get("fonte") == "agente" else a)(i, "NON_NECESSARIO_SENZA_MOTIVO", "NON_NECESSARIO senza motivo", "scrivere motivo")
    g = {s["id"]: list(s.get("dipende_da") or []) for s in steps if s.get("id")}
    cy = _ciclo(g)
    if cy: a(cy[-1], "CICLO_DIPENDENZE", " → ".join(map(str, cy)), "rimuovere una dipendenza del ciclo")
    cy = _ciclo({s["id"]: [s["parent"]] if s.get("parent") else [] for s in steps if s.get("id")})
    if cy: a(cy[-1], "CICLO_PADRI", " → ".join(map(str, cy)), "correggere parent")
    for s in steps:                                                       # coerenza ordine e padre/figli
        i = s.get("id"); c = st.get(i)
        if c in ("FATTO", "VERIFICATO"):
            for x in s.get("dipende_da") or []:
                if st.get(x) in ("DA_FARE", "IN_CORSO", "BLOCCATO"): (w if d.get("fonte") == "agente" and st.get(x) == "BLOCCATO" else a)(i, "COMPLETO_CON_DIPENDENZA_APERTA", f"{c} ma {x} è {st.get(x)}", f"ripristinare {i} o completare {x}")
        if c == "VERIFICATO":
            for f in figli(steps, i):
                fc = st.get(f["id"])
                if not obbligatorio(f) or fc == "BLOCCATO" and not bloccante(f): continue          # figlio non obbligatorio o BLOCCATO non bloccante: non blocca il padre
                if fc != "VERIFICATO": a(i, "PADRE_VERIFICATO_FIGLIO_APERTO", f"VERIFICATO ma il figlio obbligatorio {f['id']} è {fc}", f"portare {i} a FATTO (verification=partial) o chiudere {f['id']}")
    blocca = [s["id"] for s in steps if blocca_chiusura(s)]
    return {"valido": not an, "anomalie": an, "avvisi": avv, "legacy": legacy, "blocca_chiusura": blocca, "chiudibile": not blocca and not an,
            "conteggi": {c: sum(1 for x in st.values() if x == c) for c in CANON}}

def chiusura_con_limitazioni(d):
    """Passi BLOCCATI non bloccanti: la chiusura è ammessa se documentati (causa + prossimo passo)."""
    return [s["id"] for s in d.get("steps", []) if canon(s.get("stato")) == "BLOCCATO" and s.get("blocking") is False]

def percorso_critico(d):
    """Catena più lunga (per numero di passi) di passi non completati sulle dipendenze; deterministico."""
    per = {s["id"]: s for s in d.get("steps", [])}; memo = {}
    def lung(i, vis=()):
        if i in memo: return memo[i]
        if i in vis or i not in per: return []
        if canon(per[i].get("stato")) in COMPLETI: memo[i] = []; return []
        best = max((lung(x, vis + (i,)) for x in per[i].get("dipende_da") or []), key=len, default=[])
        memo[i] = best + [i]; return memo[i]
    best = []
    for i in per:
        c = lung(i)
        if len(c) > len(best): best = c
    return best

# ---------- classificazione delle richieste (regole, non LLM) ----------
_R = [   # (tipo, pattern) in ordine di priorità
    ("new_objective", r"\b(nuovo (task|obiettivo|progetto)|cambiamo obiettivo|cambio di obiettivo|passiamo (a|ad)|lasciamo (stare|perdere) (questo|il task)|un['’]?altra dashboard|altro cliente|nuovo database)\b"),
    ("correction", r"\b(hai (sbagliato|capito male|frainteso)|non è (così|quello)|errat[oa]|sbagliat[oa]|intendevo|in realtà|invece di|correggi|correzione|ti avevo detto|non ho chiesto)\b"),
    ("acceptance_criteria_update", r"\b(criteri[oa]? (di )?accettazione|deve (essere|avere|mostrare|restare|rimanere|funzionare)|dev['’]essere|non deve|solo se|almeno \d|entro \d|in ogni caso|a condizione che|considera(to)? (riuscito|valido)|è (accettabile|completo) quando)\b"),
    ("independent_branch", r"\b(inoltre|in più|oltre a (questo|ciò)|separatamente|in parallelo|indipendente(mente)?|un['’]?altra cosa|e poi anche|aggiungi anche|vorrei anche)\b"),
    ("subtask", r"\b(prima (serve|bisogna|devi)|serve anche|devi anche|è necessario|per farlo|bisogna (anche )?(controllare|verificare|misurare|aggiungere)|aggiungi (un|il) controllo)\b"),
    ("clarification", r"\b(intendo|cioè|ovvero|per chiarire|chiarisco|si riferisce|quello che voglio dire|nel senso|per precisare|specifico che)\b"),
]
_PASSO = re.compile(r"\b((?:[A-Z]{1,2}\d+[a-z]?(?:\.\d+)?)|(?:passo|step)\s+(\S+))\b")

def classifica(testo, piano=None, corrente=None):
    """Input minimo: richiesta + piano (solo id/stato/testo letti) + passo corrente. → dict dello schema del prompt + `ambiguo` e `motivo_regola`."""
    t = (testo or "").strip(); ids = [s["id"] for s in (piano or {}).get("steps", [])]; bas = t.lower()
    tipo = regola = None
    for k, p in _R:
        m = re.search(p, bas, re.I)
        if m: tipo, regola = k, m.group(0); break
    target = None
    for m in _PASSO.finditer(t):
        cand = m.group(2) or m.group(1)
        if cand in ids: target = cand; break
    ambiguo = tipo is None
    if tipo is None:                                                       # nessuna regola: scelta prudente = proporre un sottopasso (richiede conferma), mai scartare un requisito
        tipo = "subtask" if re.search(r"\b(fai|crea|aggiungi|modifica|sostituisci|rimuovi|togli|costruisci|implementa)\b", bas) else "clarification"
        regola = "default"
    if tipo in ("clarification", "acceptance_criteria_update", "correction") and not target: target = corrente
    if tipo == "subtask" and not target: target = corrente
    cambia = tipo in ("subtask", "independent_branch", "new_objective")
    blocc = tipo in ("correction", "new_objective") or bool(re.search(r"\b(prima di|stop|fermati|bloccante|non procedere)\b", bas))
    crit = [t] if tipo == "acceptance_criteria_update" else []
    return {"type": tipo, "target_step": target, "requires_plan_change": cambia, "blocking": blocc, "summary": t[:160], "acceptance_changes": crit,
            "new_dependencies": [target] if tipo == "subtask" and target else [], "ambiguo": ambiguo, "motivo_regola": regola}

"""Valuta un prompt con regole fisse (zero token, nessuna AI): le regole vengono dalle guide ufficiali di GitHub Copilot e Claude Code.
Non giudica il contenuto: controlla se ci sono gli ingredienti che quelle guide chiedono, e dice cosa aggiungere. Serve a imparare, non a dare voti."""
import re

FONTI = {"copilot": ["Prompt engineering for GitHub Copilot Chat", "https://docs.github.com/en/copilot/concepts/prompting/prompt-engineering"],
         "claude": ["Best practices for Claude Code", "https://code.claude.com/docs/en/best-practices"]}
MODIFICA = re.compile(r"(?i)\b(aggiung\w*|implement\w*|crea\w*|scriv\w*|modific\w*|cambi\w*|corregg\w*|sistem\w*|fix\w*|risolv\w*|refactor\w*|rinomin\w*|rimuov\w*|elimin\w*|togli\w*|spost\w*|migr\w*|aggiorn\w*|add|create|write|change|update|remove|delete|rename|move|migrate|build|make|rewrite|replace|merge|unisc\w*)\b")
FILE = re.compile(r"(\b[\w./\\-]+\.(?i:java|py|ts|tsx|js|jsx|vue|sql|ya?ml|json|xml|html|s?css|md|properties|kt|sh|ps1|toml|gradle)\b|`[^`]{2,}`|#file:|@workspace|\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b|\b\w+\(\)|[\w-]+/[\w-]+/[\w./-]+)")
VERIFICA = re.compile(r"(?i)\b(test\w*|build|compil\w*|verific\w*|verify|check\w*|controll\w*|lint\w*|mvn|npm|pytest|gradle|jest|expected|atteso|mi aspetto|deve (restituire|dare|passare)|should (return|pass)|done when|fatto quando|finito quando|criteri\w*|accept\w*|screenshot|riprodu\w*|reproduc\w*)\b")
VAGO = re.compile(r"(?i)\b(questo|questa|quello|quella|questa cosa|la cosa|sta cosa|il coso|roba|this|that|it|stuff|the thing)\b")
VINCOLI = re.compile(r"(?i)\b(non (toccare|modificare|cambiare|cancellare)|senza (toccare|modificare|cambiare)|solo (in|il|la|nel|nella|lettura)|soltanto|do not|don't|without (changing|touching)|only|read-only|sola lettura|keep|mantieni|lascia)\b")
ESEMPIO = re.compile(r"(?i)(\bes(empio)?[.:]|\bexample|\be\.g\.|```|\bcome (in|fa|per)\b|\blike in\b|input|output|\bstack ?trace\b|\berror[e]?:|exception)")
PASSI = re.compile(r"(?im)(^\s*(\d+[.)]|[-*•])\s+\S|\b(e poi|dopodich[eé]|inoltre|infine|and then|after that|also|finally)\b)")
LETTURA = re.compile(r"(?i)(sola lettura|read-only|read only|in lettura|non (modificare|toccare|cambiare|creare)|do not (modify|change|edit|create)|without (modifying|changing)|solo (analisi|lettura|revisione))")
PIANO = re.compile(r"(?i)\b(pian\w*|plan\w*|prima (di|dimmi|spiega|proponi)|proponi|non scrivere codice|before (coding|writing|you)|step by step|passo passo)\b")


def _voce(ok, regola, perche, come, fonte):
    return {"ok": bool(ok), "regola": regola, "perche": perche, "come": come, "fonte": fonte}


def valuta(testo, agente=""):
    """-> {tipo, voti:[...], da_migliorare, giudizio, modello, fonti}. Mai un'eccezione: un prompt vuoto torna None."""
    t = str(testo or "").strip()
    if not t or t.startswith("(domanda nella chat"): return None
    tagliato = t.endswith("…"); parole = len(re.findall(r"\w+", t)); modifica = bool(MODIFICA.search(t)); domanda_semplice = not modifica and (t.rstrip().endswith("?") or parole <= 25)
    lettura = bool(LETTURA.search(t)); modifica = modifica and not lettura                                   # «sola lettura»: le parole come «crea» o «modifica» sono divieti, non richieste
    n_file = len(set(m.group(0) for m in FILE.finditer(t))); vaghi = len(VAGO.findall(t)); passi = len(PASSI.findall(t)); voci = []
    voci.append(_voce(parole >= 8 or (domanda_semplice and parole >= 4), "Di' cosa vuoi ottenere, non solo cosa fare",
                      "Con poche parole l'agente deve indovinare lo scopo, e spesso indovina una cosa diversa da quella che hai in mente.",
                      "Aggiungi una frase sul risultato: «voglio che… così che…».", "copilot"))
    if not domanda_semplice or vaghi > 1:
        voci.append(_voce(n_file >= 1 and vaghi <= max(1, n_file), "Nomina file, classi o funzioni (niente «questo», «quello»)",
                          "L'agente non vede cosa stai guardando: «sistema questo» lo costringe a cercare in tutto il progetto, e consuma tempo e token.",
                          "Scrivi il nome: «in OrderService.java, metodo calcolaTotale()» oppure il percorso della cartella.", "copilot"))
    if modifica:
        voci.append(_voce(VERIFICA.search(t), "Dagli un modo per verificare da solo",
                          "È la cosa che conta di più: se sa quale test o comando deve passare, si corregge da solo; altrimenti si ferma quando «sembra» finito.",
                          "Aggiungi: «hai finito quando `mvn test -Dtest=OrderServiceTest` passa» oppure il risultato atteso su un esempio.", "claude"))
        voci.append(_voce(VINCOLI.search(t), "Di' cosa non deve toccare",
                          "Senza confini l'agente può «migliorare» anche codice che non c'entra, e la modifica diventa difficile da controllare.",
                          "Aggiungi: «modifica solo la cartella X», «non cambiare le API pubbliche», «non toccare i test esistenti».", "claude"))
        if parole >= 15:
            voci.append(_voce(ESEMPIO.search(t), "Dai un esempio (input, output o l'errore esatto)",
                              "Un esempio toglie i dubbi meglio di tre frasi di spiegazione.",
                              "Incolla il messaggio di errore, oppure «con input X mi aspetto Y».", "copilot"))
    if modifica and (passi >= 6 or parole > 400):
        voci.append(_voce(PIANO.search(t), "Lavoro grande: chiedi prima un piano, o dividilo",
                          "Tante cose in un solo prompt: l'agente ne fa bene alcune e ne dimentica altre. Con un piano vedi subito se ha capito.",
                          "Inizia con «prima scrivi il piano e aspetta il mio ok», oppure manda una richiesta per volta.", "claude"))
    if len(t) > 6000 and not tagliato:
        voci.append(_voce(False, "Prompt molto lungo: le regole fisse mettile in una skill o nelle istruzioni",
                          "Se incolli ogni volta le stesse regole paghi quei token a ogni richiesta e rischi versioni diverse.",
                          "Sposta le parti che non cambiano in AGENTS.md / copilot-instructions.md o in una skill, e nel prompt lascia solo il compito.", "claude"))
    manca = [v for v in voci if not v["ok"]]
    giudizio = "Prompt completo: ha tutto quello che le guide consigliano." if not manca else ("Buon prompt, con %s da aggiungere." % ("una cosa" if len(manca) == 1 else "%d cose" % len(manca)) if len(manca) <= 2 else "Prompt migliorabile: mancano %d ingredienti." % len(manca))
    if tagliato: giudizio = "Valutazione parziale: della richiesta ho solo l'inizio, quindi manca il resto del testo." + (" Dall'inizio risulta che mancano %d cose." % len(manca) if manca else "")
    modello = ""
    if manca and modifica:
        riga1 = t.splitlines()[0][:200]
        modello = "\n".join(["Goal: " + riga1,
                             "Where: <file, class or folder to change>" if any("Nomina" in v["regola"] for v in manca) else "",
                             "Do not touch: <what must stay as it is>" if any("non deve toccare" in v["regola"] for v in manca) else "",
                             "Example: <exact error, or input -> expected output>" if any("esempio" in v["regola"] for v in manca) else "",
                             "Done when: <test or command that must pass>" if any("verificare" in v["regola"] for v in manca) else "",
                             "First write the plan and wait for my OK." if any("piano" in v["regola"] for v in manca) else ""])
        modello = re.sub(r"\n{2,}", "\n", modello).strip()
    rivedi = ("Review the prompt below before I use it. Do NOT run it. Read it like a new colleague would and tell me, briefly: "
              "(1) instructions that contradict each other or can be read two ways; (2) what is missing to do the job without guessing "
              "(scope, files, allowed commands, what must not change, how to check it is done); (3) anything that costs tokens for no reason. "
              "Then give me a rewritten version.\n\n--- PROMPT ---\n" + t[:12000])
    return {"tipo": "lettura" if lettura else "modifica" if modifica else "domanda", "rivedi": rivedi, "voci": voci, "da_migliorare": len(manca), "giudizio": giudizio, "modello": modello, "parziale": tagliato,
            "fonti": [FONTI[k] for k in ("copilot", "claude")]}


def valuta_skill(nome, descrizione, corpo, cartella=""):
    """Consigli sulla scrittura di una skill (formato Agent Skills): elenco di frasi, vuoto se va bene."""
    c = []; d = str(descrizione or "").strip()
    if not d: c.append("Manca la descrizione: senza, l'agente non sa quando usarla e non la carica mai.")
    else:
        if len(d) < 40: c.append("Descrizione troppo corta: di' cosa fa e quando usarla («Use when…»).")
        if not re.search(r"(?i)\b(use (this )?(when|before|after|for|whenever)|quando|usa(la)? (quando|per|prima|dopo)|triggers?)\b", d): c.append("La descrizione non dice quando usarla: aggiungi «Use when…», è quello che l'agente legge per decidere.")
        if len(d) > 1024: c.append("Descrizione oltre 1024 caratteri: viene tagliata.")
    if cartella and nome and nome != cartella: c.append("Il nome (%s) è diverso dalla cartella (%s): devono coincidere." % (nome, cartella))
    if nome and not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", nome): c.append("Nome non valido: solo minuscole, numeri e trattini.")
    righe = str(corpo or "").count("\n") + 1
    if righe > 500: c.append("Corpo di %d righe: oltre 500 conviene spostare i dettagli in file separati nella stessa cartella." % righe)
    if corpo is not None and len(str(corpo).strip()) < 80: c.append("Il corpo è quasi vuoto: scrivi i passi concreti, con i comandi esatti.")
    return c

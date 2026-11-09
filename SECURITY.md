# Sicurezza

**Segnalare un problema:** apri una *Security advisory* privata su GitHub (scheda Security → Report a vulnerability), non una issue pubblica.

## Come è fatta la Plancia, in breve

- **Solo sul tuo PC.** Il pannello ascolta su `127.0.0.1` (non è raggiungibile da altri computer). Per esporlo in rete servono `--host` e `--token` espliciti.
- **Nessun dato esce.** Nessuna chiamata a servizi esterni, nessuna telemetria, nessuna dipendenza oltre a Python standard.
- **Il browser non può essere usato contro di te.** Il pannello rifiuta richieste con `Host` diverso dal suo (DNS rebinding) e scritture da altri siti (controllo `Origin`); manda `Content-Security-Policy`, `X-Frame-Options: DENY`, `nosniff`.
- **Unica scrittura dal pannello:** accetta/rifiuta una proposta della scheda Strumenti (`POST /api/proposta`, JSON, solo stessa origine, solo progetti registrati, id validati).
- **Segreti.** Gli hook non salvano gli input degli strumenti; domande e risposte sono accorciate e ripulite da password, token, chiavi e stringhe di connessione prima di essere scritte. Tutto resta in `.factory/` del progetto, esclusa da git.
- **Guardie.** File protetti (`.env`, chiavi, `.git`, `secrets/`) e comandi pericolosi (`rm -rf`, `push --force`, `DROP TABLE`, `curl | sh`…) vengono negati all'agente prima dell'esecuzione. Le guardie fermano errori dell'agente: non sostituiscono permessi veri (utenti DB in sola lettura, branch protetti).
- **Fail-open voluto.** Un errore interno degli hook non blocca mai l'agente (per questo nel codice ci sono `try/except` silenziosi: sono intenzionali).
- **Processi.** Nessun `shell=True`, nessun `eval`/`exec`/`pickle`; i sottoprocessi usano liste di argomenti.

## Controlli automatici
Ogni push esegue: test (Windows e Linux, Python 3.9 e 3.13), `ruff` (lint + regole di sicurezza) e `bandit`.

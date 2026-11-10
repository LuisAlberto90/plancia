# Sicurezza

**Segnalare un problema:** apri una *Security advisory* privata su GitHub (scheda Security → Report a vulnerability), non una issue pubblica.

## Come è fatta la Plancia, in breve

- **Solo sul tuo PC.** Il pannello ascolta su `127.0.0.1` (non è raggiungibile da altri computer). Per esporlo in rete servono `--host` e `--token` espliciti.
- **Nessun dato esce.** Nessuna chiamata a servizi esterni, nessuna telemetria, nessuna dipendenza oltre a Python standard.
- **Il browser non può essere usato contro di te.** Il pannello rifiuta richieste con `Host` diverso dal suo (DNS rebinding) e scritture da altri siti (controllo `Origin`); manda `Content-Security-Policy`, `X-Frame-Options: DENY`, `nosniff`.
- **Blocchi da provare insieme:** calcolati in lettura dai file sorgente del progetto (prime 40 KB di ciascuno, max 4000 file); non scrivono nulla e non c'è un endpoint dedicato.
- **Unica scrittura dal pannello:** accetta/rifiuta una proposta della scheda Strumenti (`POST /api/proposta`, JSON, solo stessa origine, solo progetti registrati, id validati). Le proposte che creano un file (skill dai comandi ripetuti, agente di sola lettura) vengono ricalcolate dal motore: dal browser arriva solo l'id e la scelta Copilot/Claude, mai il contenuto; non sovrascrivono file esistenti e finiscono in `.git/info/exclude`.
- **Segreti.** Gli hook non salvano gli input degli strumenti; domande e risposte sono accorciate e ripulite da password, token, chiavi e stringhe di connessione prima di essere scritte. Tutto resta in `.factory/` del progetto, esclusa da git.
- **Guardie.** File protetti (`.env`, chiavi, `.git`, `secrets/`) e comandi pericolosi (`rm -rf`, `push --force`, `DROP TABLE`, `curl | sh`…) vengono negati all'agente prima dell'esecuzione. Le guardie fermano errori dell'agente: non sostituiscono permessi veri (utenti DB in sola lettura, branch protetti).
- **Segreti: nemmeno in lettura.** L'agente non può leggere `.env`, chiavi (`*.pem`, `*.key`, `id_rsa`…), `credentials.*` e la cartella `secrets/`, né con lo strumento di lettura né con un comando (`cat`, `type`, `Get-Content`…): il contenuto finirebbe nella chat e nei log. I modelli (`.env.example`) si leggono. Si spegne con `"segreti": false` in `.factory/config.json`.
- **Comandi distruttivi: decide la persona.** Cancellare cartelle intere (`rm -r`, `Remove-Item -Recurse`, `rmdir /s`), `git clean`, `git checkout -- .`, `git branch -D` non sono vietati ma richiedono il tuo sì in chat; la Plancia ti avvisa che la chat aspetta.
- **Fail-open voluto.** Un errore interno degli hook non blocca mai l'agente (per questo nel codice ci sono `try/except` silenziosi: sono intenzionali).
- **Processi.** Nessun `shell=True`, nessun `eval`/`exec`/`pickle`; i sottoprocessi usano liste di argomenti.

## Controlli automatici
Ogni push esegue: test (Windows e Linux, Python 3.9 e 3.13), `ruff` (lint + regole di sicurezza) e `bandit`.

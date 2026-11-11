# Plancia

**La plancia di comando per i tuoi agenti di codice.**
*The bridge for your coding agents: Claude Code, Copilot CLI, VS Code chat.*

Una pagina nel browser che ti fa vedere, per tutti i tuoi progetti, cosa fanno gli agenti:
chi lavora, chi aspetta te, chi aspetta un permesso, chi sbaglia o gira in tondo, quanto consuma.
Per ogni domanda l'agente scrive prima un **piano a passi** (con rami paralleli) e la Plancia lo disegna come grafo,
con le azioni e gli errori di ogni passo. Le **guardie** bloccano file protetti (`.env`, chiavi, `.git`) e comandi pericolosi.

**Come funziona dentro** (hook, plugin, MCP locale, dati, sicurezza, con schemi): [docs/ARCHITETTURA.md](docs/ARCHITETTURA.md).

Zero token per guardare: la Plancia legge le trascrizioni e gli hook, non chiede niente al modello.
Serve solo **Python 3.9+** (su Windows il comando `py`) e **git**.

---

## 1. Installare: una volta sola, vale per tutti i progetti

Serve Python 3.9+ (su Windows il comando `py`). Non tocca i file dei tuoi progetti: ogni progetto si prepara da solo al primo uso
(cartella `.factory/`, esclusa da git solo sul tuo PC).

**Chat di VS Code (Copilot)**
1. `Ctrl+Shift+P` → **Chat: Install Plugin from Source** → incolla `https://github.com/LuisAlberto90/plancia` → scegli **User**.
2. `Ctrl+Shift+P` → **Developer: Reload Window**.
3. Impostazioni (`Ctrl+,`) → cerca `hooks` → attiva gli hook della chat (una volta sola).

**Copilot CLI**
```
copilot plugin install LuisAlberto90/plancia
```

**Claude Code**
```
/plugin marketplace add LuisAlberto90/plancia
/plugin install plancia@plancia
```

Fatto. Alla prima domanda in un progetto la Plancia si accende da sola: apri **http://127.0.0.1:8780** (mettilo nei preferiti)
oppure scrivi `/plancia` in chat. Aggiornamenti: il bottone **Aggiorna la Plancia** nel pannello scarica l'ultima versione e riscrive i file di ogni copia installata, **anche con chat di VS Code o Copilot CLI aperte** (non aspetta e non chiede di chiuderle); in alternativa dalla pagina dei plugin di VS Code / `copilot plugin update plancia` / `/plugin update` in Claude Code.

**Alternativa senza plugin** (se l'azienda blocca i plugin): `git clone https://github.com/LuisAlberto90/plancia C:\Strumenti\plancia`,
poi doppio clic su **Installa-in-un-progetto.cmd** per ogni progetto (scrive regola e hook nel progetto).

## 2. Usarla ogni giorno

| Cosa vuoi fare | Doppio clic su |
|---|---|
| Vedere tutti i progetti e gli agenti | **Apri-Plancia.cmd** |
| Preparare un progetto nuovo | **Installa-in-un-progetto.cmd** |
| Ripartire puliti (lo storico va in `.factory\archivio`, niente si cancella) | **Archivia-storico.cmd** |
| Mandare un problema a chi ti supporta (zip **senza codice sorgente**) | **Diagnosi.cmd** |
| Prendere l'ultima versione | **Aggiorna-Plancia.cmd** |

Nel pannello:
- **Progetti**: una scheda per progetto, scritta in chiaro: cosa sta facendo l'agente adesso, **l'ultima cosa che hai chiesto** (anche se è di settimane fa), se è finita, quanti file ha toccato e il **piano** ("l'agente sta scrivendo il piano…" → "Piano pronto → Vedi il piano"). Le conversazioni più vecchie sono raccolte sotto *Altre conversazioni*. Il pulsante 🔔 attiva le notifiche.
- **Piano**: il grafo dei passi dell'ultima richiesta, con voto di qualità (0-10). Clic su un passo = cosa ha fatto (file, comandi, errori).
- **Richieste**, **Riprendere**: cosa è successo e da dove ripartire.
- **Prompt intero e valutato**: in Lavoro vedi tutta la richiesta (riquadro che scorre) e «Com'era scritto questo prompt?»: regole fisse prese dalle guide ufficiali di GitHub Copilot e Claude Code, senza AI, con cosa aggiungere e uno schema da copiare. Stessa cosa per le skill scritte da te.
- **Consumi per progetto**: tab «Consumi» (e bottone nella Home): token di lavoro e riletti per progetto, per giorno, per agente e le richieste più pesanti; periodo a scelta e CSV scaricabile. Dati letti dalle trascrizioni di Claude Code e Copilot CLI; la chat di VS Code non fornisce i token, quindi quelle richieste si contano ma non si misurano. Nessuna conversione in euro.
- **Tema scuro o chiaro**: bottone in alto a destra; la scelta resta salvata nel browser (la prima volta segue il sistema).
- **Cosa provare insieme**: per ogni richiesta che ha modificato codice, i blocchi toccati e chi li usa (letti dagli import, senza AI): se un blocco molto usato cambia, conviene provare anche chi lo usa. Compare nelle richieste e nel prompt pronto del box «Oggi».
- **Salute**: cosa non va e come sistemarlo, e il **livello del progetto** (da 0 a 4) con il prossimo passo.
- **Avvisi nella Home**: "modificato ma non provato" (nessun test dopo le modifiche), chat troppo lunga, due chat sullo stesso file, riepilogo di oggi su tutti i progetti, bottone *Apri in VS Code*. Tutti calcolati dai fatti registrati: zero token.
- **Strumenti**: le *skill* (guide che l'agente legge solo quando servono), le istruzioni fisse (lette a ogni domanda: costano sempre) e le **proposte**: per ognuna dici *Sì* (la Plancia la crea da sola, o ti dà il testo pronto da incollare in chat) o *No* (non te la ripropone più per quel progetto). Le skill "per tutti i progetti" valgono ovunque; quelle "solo questo progetto" restano lì, escluse da git.
- **Prove** (nascosta): `http://127.0.0.1:8780/?prove=1` — 10 prove guidate per chi sviluppa la Plancia.

**Non succede niente?** Nel terminale: `py "<cartella del plugin>\factory.py" controlla` — dice in italiano cosa manca (Python, plugin, hook, pannello, progetti) e come sistemarlo.
In VS Code: `Ctrl+Shift+P` → *Customizations* → **Hooks** deve elencare gli hook di *plancia*; *View → Output → GitHub Copilot Chat Hooks* mostra se partono.

## 3. Aggiornare

Apri la Plancia (http://127.0.0.1:8780) e premi **⟳ Aggiorna la Plancia** in alto a destra. Fa tutto lei: scarica la versione nuova in tutte le copie installate (VS Code e Copilot CLI) e si riavvia da sola; la pagina si ricarica.

A mano, se serve — VS Code: `git -C "$HOME\.vscode\agent-plugins\github.com\LuisAlberto90\plancia" pull` · **Copilot CLI**: `copilot plugin update plancia` · **Claude Code**: `/plugin update plancia` · **Installazione classica**: doppio clic su **Aggiorna-Plancia.cmd**.

**Progetti preparati con la versione classica o con la vecchia Lavagna**: col plugin non servono più hook e regola dentro il progetto.
In **Strumenti** trovi la proposta *"Questo progetto ha ancora la vecchia installazione"* → **Sì, fallo tu**; oppure da terminale nel progetto:
`py "$HOME\.vscode\agent-plugins\github.com\LuisAlberto90\plancia\factory.py" scollega --scrivi` (toglie solo le parti della Plancia).

## 4. Cosa scrive nei progetti

Con il plugin: solo `.factory/` (piani, eventi, mappa, guardie), esclusa da git in `.git/info/exclude`. La regola del piano arriva all'agente a inizio sessione (~200 token).
Con l'installazione classica in piu: la regola in `AGENTS.md`, gli hook in `.claude/settings.json` e `.github/hooks/plancia.json`, i 3 strumenti del piano in `.vscode/mcp.json`.
Gli hook non salvano mai segreti; i prompt sono salvati accorciati e ripuliti. `.factory/` è escluso da git.

## Comandi (per chi usa il terminale)

`py C:\Strumenti\plancia\factory.py <comando>` (Linux: `python3 ~/plancia/factory.py <comando>`)

| Comando | A cosa serve |
|---|---|
| `init --scrivi` | prepara il progetto corrente (come Installa-in-un-progetto) |
| `pannello` | apre la Plancia |
| `progetti` | lo stato di tutti i progetti nel terminale |
| `piano nuovo "Titolo" "A: ..." "B: ... <- A"` / `passo B fatto "nota"` | il piano (di solito lo scrive l'agente) |
| `contesto --scrivi` | rigenera `.factory/CONTESTO.md`: stack, comandi build/test (anche Maven/JDK fuori dal PATH), moduli |
| `strumenti` / `skill-progetto --scrivi` | inventario degli strumenti / skill del progetto con i comandi di build e test |
| `prove`, `prove verifica N` | le prove guidate |
| `archivia`, `diagnosi`, `salute` | storico, zip di supporto, controlli |

Test della Plancia stessa: `python tests/run_tests.py` (il test del pannello nel browser richiede `playwright`, altrimenti viene saltato). Lint e sicurezza: `ruff check .` e `bandit -r fcore -ll`. Vedi anche [SECURITY.md](SECURITY.md).



## Consumi: chi consuma cosa

La schermata **Consumi** legge solo file gia presenti sul PC (zero token, zero rete) e separa, per progetto: cosa hai dato da leggere (input), le risposte scritte dall'agente, la cache scritta e la cache riletta. Claude Code e Copilot CLI danno i token reali. Anche la chat di VS Code li salva (`workspaceStorage/*/chatSessions`: `promptTokens`, `outputTokens`, finestra massima e ripartizione del contesto per categoria): Plancia mostra la **finestra di contesto** come l'indicatore di VS Code (ultima richiesta, picco, cosa la occupa) e non somma la cronologia ai token di lavoro, perché viene riletta a ogni richiesta. Solo dove VS Code non salva nulla il numero e una **stima dal testo** (4 caratteri = 1 token), marcata come tale. La Plancia non usa token: la sua voce e solo il testo che inietta nelle chat (regola del piano e descrizione della skill una volta per chat, promemoria dal secondo messaggio); se in un periodo non e stato scritto nessun piano, Consumi lo dice (costo senza beneficio) e spiega come spegnere la regola.

**Per modello**: ogni richiesta registra quale modello ha risposto (Claude Code e Copilot CLI dai transcript, chat di VS Code da `modelId`); Consumi mostra tabella e torte per modello, agente e progetto e dice in una frase quale consuma di piu per richiesta. Confronta il consumo, non la qualita; i numeri della chat di VS Code (solo output) non sono 1:1 con gli altri. Ogni voce ha una frase semplice e ogni agente una spiegazione.

**Skill intelligenti**: la scheda Skill mostra per ognuna il costo fisso (nome + descrizione, letti a inizio chat) e quante richieste l'hanno davvero usata; «Da decidere» propone di migliorare una skill che copre un tema ma continui a rifare a mano, di ampliarla, o di crearne una nuova solo se nessuna assomiglia. Tutto calcolato sul PC dalle richieste passate, 0 token.

Il comando `plancia chat-campi` mostra dove VS Code salva la chat e quali campi numerici contiene (solo nomi e numeri, mai il testo): utile se VS Code cambia formato.

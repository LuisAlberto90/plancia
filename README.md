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
oppure scrivi `/plancia` in chat. Aggiornamenti: dalla pagina dei plugin di VS Code / `copilot plugin update plancia` / `/plugin update` in Claude Code.

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
- **Salute**: cosa non va e come sistemarlo.
- **Strumenti**: le *skill* (guide che l'agente legge solo quando servono), le istruzioni fisse (lette a ogni domanda: costano sempre) e le **proposte**: per ognuna dici *Sì* (la Plancia la crea da sola, o ti dà il testo pronto da incollare in chat) o *No* (non te la ripropone più per quel progetto). Le skill "per tutti i progetti" valgono ovunque; quelle "solo questo progetto" restano lì, escluse da git.
- **Prove** (nascosta): `http://127.0.0.1:8780/?prove=1` — 10 prove guidate per chi sviluppa la Plancia.

## 3. Aggiornare

**Plugin di VS Code** (PowerShell, una riga):
```
git -C "$HOME\.vscode\agent-plugins\github.com\LuisAlberto90\plancia" pull
```
poi in VS Code `Ctrl+Shift+P` → **Developer: Reload Window** e fai una domanda qualsiasi: il pannello nuovo prende il posto di quello vecchio da solo.
Linux/Mac: `git -C ~/.vscode/agent-plugins/github.com/LuisAlberto90/plancia pull`.

**Copilot CLI**: `copilot plugin update plancia` · **Claude Code**: `/plugin update plancia` · **Installazione classica**: doppio clic su **Aggiorna-Plancia.cmd**.

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


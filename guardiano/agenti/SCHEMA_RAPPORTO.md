# Il rapporto degli agenti — `rapporto.json`, campo per campo

Lo scrive il direttore ogni notte (vedi `PROCEDURA.md`), lo legge la pagina (sezione «Oggi»). Il controllo automatico è `valida_rapporto.py`; un esempio completo, con nomi e numeri inventati, è `esempio_rapporto.json`.

## Livello principale

| Campo | Tipo | Significato |
|---|---|---|
| `data` | `AAAA-MM-GG` | Giorno dell'analisi. |
| `generato_il` | data e ora ISO, fuso di Roma | Quando il rapporto è stato scritto. |
| `dati_del` | data e ora ISO | Il `generato_il` di `stato.json` su cui si basa: la pagina avvisa se è più vecchio dei dati mostrati. |
| `clima` | oggetto | `sintesi` (due o tre frasi) e `mercati`: per `IT`, `EU`, `US`, `CRYPTO` un `giudizio` (`favorevole`, `incerto`, `sfavorevole`, uguale allo stato del motore) e una `nota` di una frase. |
| `proposte` | elenco, da 0 a 5 | Le idee che hanno superato analista, supervisore e responsabile del rischio. Vuoto è un esito normale. |
| `posizioni` | elenco | Un giudizio per ogni posizione aperta dell'utente. |
| `scartate` | elenco | Le idee esaminate e respinte: `strumento`, `nome`, `motivo`. |
| `pac` | oggetto | `nota` (testo breve) e `controlli` (elenco di frasi, con fonte quando serve). |
| `avvertenze` | testo | Limiti dello strumento e note del giorno. |
| `esempio` | `true` (facoltativo) | Solo nell'esempio: la pagina lo marca «Rapporto di esempio». |

## Una proposta

| Campo | Valori | Note |
|---|---|---|
| `id` | `<data>-<strumento>` | |
| `strumento`, `nome` | testo | `strumento` è l'`id` del motore (per esempio `ENI.MI`, `BTC-EUR`). |
| `tipo` | `azione`, `crypto`, `etf` | |
| `mercato` | `IT`, `EU`, `US`, `CRYPTO` | |
| `azione` | `COMPRA`, `ATTENDI` | `ATTENDI` quando serve una conferma (prezzo, evento, clima). |
| `orizzonte` | testo | Di solito «2-6 settimane». |
| `fiducia` | `bassa`, `media`, `alta` | La più bassa tra analista e supervisore. |
| `tesi` | due frasi | Perché ha senso, in parole semplici. |
| `perche` | tre frasi | Motivi concreti, verificabili. |
| `piano.prezzo_riferimento`, `piano.stop`, `piano.obiettivo`, `piano.rischio_pct` | numeri | **Dal motore** (`segnali_attivi`): lo stop sta sotto il prezzo. |
| `piano.ingresso` | una frase | Come entrare (ordine limite, orario, condizione). |
| `piano.dimensione` | una frase | Dal responsabile del rischio: quantità, importo, perdita allo stop; o formula con esempio. |
| `rischi` | elenco | Cosa può andare storto, eventi vicini compresi. |
| `affidabilita_segnale` | una frase con numeri | Operazioni, vincenti, media netta e giudizio della regola in quel mercato (`affidabilita.json`). |
| `solidita` | `giudizio` + `punti` | Per le azioni: redditività, debito, flusso di cassa, con fonte. Per le crypto: fondamentali del progetto e rischi. |
| `notizie` | elenco di `titolo`, `fonte`, `url` (http/https), `data` | Notizie degli ultimi 14 giorni. |
| `vagli` | `analista`, `supervisore`, `rischio` | Una frase ciascuno: il percorso della decisione. |

## Una posizione

| Campo | Valori |
|---|---|
| `strumento`, `nome` | come sopra |
| `azione` | `MANTIENI`, `RIDUCI`, `VENDI` |
| `motivo` | una o due frasi |
| `stop_aggiornato` | numero (mai più basso dello stop dell'utente) oppure `null` |

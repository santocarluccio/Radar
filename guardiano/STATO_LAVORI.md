# Stato dei lavori — Il Guardiano dei Mercati

Repository: GitHub `santocarluccio/Radar`, ramo di lavoro `guardiano` (codice), ramo `dati` (dati del motore, scritto solo da GitHub Actions).
Specifica: `guardiano/SPECIFICA.md`. Questo file sta nel repository apposta: se una sessione si interrompe, la successiva riparte da qui.

Vincolo: il piano Claude dell'utente ha un limite di utilizzo ogni 5 ore. Pochi agenti, compiti mirati, poca ricerca web, salvataggi frequenti su GitHub.

## Come riprendere (per Santo e per Claude)

> **In pausa dal 21/11/2026, fino a nuova data (decisione di Santo).** L'attività programmata «Guardiano: analisi notturna» è disattivata (non cancellata) e i giri programmati del motore sono sospesi (blocco `schedule` commentato in `.github/workflows/guardiano-dati.yml`; restano l'avvio a mano e quello su push del codice). La pagina resta online con i dati di venerdì 20/11. **Per ripartire**: togliere i `#` dal blocco `schedule`, avviare a mano un giro del motore (Actions → «Guardiano - dati di mercato» → Run workflow) e riattivare l'attività programmata (elenco delle attività programmate nell'app Claude, oppure `update_trigger` con `enabled: true`).

- **Pagina privata** con dati, segnali e rapporti: https://claude.ai/artifact/JqhrbXM6wGBuW1eRzee2xB (slug `90783c6c-0c6b-4dcd-88d7-04f7413a11dc`; database con `guardiano/portafoglio`, `guardiano/impostazioni`, `guardiano/storico`).
- **Motore**: GitHub Actions `guardiano-dati.yml`, tre giri a notte (22:17, 00:47 e 04:17 UTC); dati sul ramo `dati`.
- **Agenti**: attività programmata «Guardiano: analisi notturna», ogni giorno alle 06:35 (ora di Roma), direttore su Opus, notifica push. Procedura in `guardiano/agenti/PROCEDURA.md`, ruoli in `.claude/agents/`, a mano con il comando `/guardiano`.
- **Configurazione scelta da Santo (16/11)**: analisi ogni notte con il direttore su Opus, per la massima affidabilità. Alternativa a risparmio, se il limite del piano Pro diventa un problema: agenti due volte a settimana (mercoledì e venerdì alle 06:35, che coprono tutti i segnali grazie alla validità di 3 sedute) e direttore su Sonnet.

## Piano

1. [x] Specifica e stato dei lavori nel repository
2. [x] Universi (`config/universo_*.json`) e `parametri.json`
3. [x] Motore, test, flusso GitHub Actions, README
4. [x] Primo giro con dati reali, correzione dei ticker, `main` aggiornato (attiva l'esecuzione notturna)
5. [x] Interfaccia (`guardiano/interfaccia/index.html`) provata su telefono e PC
6. [x] Squadra di agenti: ruoli in `.claude/agents/`, `guardiano/agenti/PROCEDURA.md`, schema ed esempio del rapporto, comando `/guardiano`
7. [x] Pubblicazione dell'artifact privato con i dati reali e database (slug `90783c6c-0c6b-4dcd-88d7-04f7413a11dc`)
8. [x] Attività programmata notturna «Guardiano: analisi notturna» ogni giorno alle 01:35 (ora di Roma), notifica push, approvazione automatica
9. [x] Verifica finale (revisione indipendente del motore: nessun uso di dati futuri, backtest conforme; corretti registro, «frenato dal clima» e dati vecchi)
10. [ ] Ricerca con fonti, a piccole dosi: metodo PAC, dettagli operativi dei broker, strumenti GitHub, metodologia dei segnali

## Diario

- 15/11 21:50–04:12 — Prima sessione (Claude Fable 5.2): specifica scritta, agenti avviati due volte, interrotti dal limite di utilizzo; nulla salvato su GitHub.
- 16/11 06:30 — Seconda sessione (Claude Opus 5.5): specifica ricostruita dalla chat, con il ramo `dati` separato; lavoro diretto, salvataggi frequenti.
- 16/11 06:50 — Motore, 27 test e flusso pubblicati. Primo giro reale (Actions, 9 min): 196 strumenti su 199; prezzi verificati con le notizie (FTSE MIB 51.805 il 29/9, Technoprobe 32,32 €) e con CoinGecko (BTC 58.167 € il 15/11 alle 00:00 UTC). Correzioni: nuovi tentativi a lotti con tetto di tempo, Kraken completa le ultime barre crypto (Yahoo di notte resta indietro di un giorno), 7 crypto solo da Kraken, ETP bitcoin sostituito da VanEck VBTC.
- 16/11 07:10 — Terzo giro reale: 199 strumenti su 199, 78 s; `main` aggiornato in avanti (esecuzione notturna attiva alle 23:20 UTC).
- 16/11 07:40 — Interfaccia scritta e provata con Playwright (390×844 e 1280×800, tema chiaro e scuro): viste, scheda con grafico, portafoglio, calcolatore, simulatore PAC; nessun errore in console a parte i font bloccati nella prova.
- 16/11 07:20 — Pagina privata pubblicata con i dati reali (https://claude.ai/artifact/JqhrbXM6wGBuW1eRzee2xB), database dichiarato (`guardiano/*` leggibile e scrivibile solo dal proprietario). Squadra di agenti: 9 ruoli, procedura del direttore, schema, validatore del rapporto con test, comando `/guardiano`.
- 16/11 07:20 — Attività programmata creata (prima esecuzione 17/11 01:35). Controllo dell'esito programmato in questa conversazione per il 17/11 alle 07:40. Revisione indipendente del motore avviata.
- 16/11 07:30 — Revisione indipendente: nessun dato futuro (riprodotto troncando le serie), regole e backtest conformi alla specifica. Corretti: registro con un'operazione alla volta per coppia strumento–regola, «frenato dal clima» solo con punteggio da COMPRA, strumenti con dati vecchi esclusi da COMPRA e dall'ampiezza; chiariti in specifica i livelli 20/55 giorni e `indice_periodo_pct` nullo per TUTTI. 29 test.

## Da fare nelle prossime sessioni

- Controllare l'esito della prima analisi notturna (17/11): pubblicazione nella pagina, budget rispettato, qualità del rapporto.
- Passo 10: ricerca con fonti a piccole dosi (metodo PAC, broker, strumenti GitHub, metodologia dei segnali); verificare i campi `da_verificare` degli universi (TER, simboli, disponibilità crypto su Trade Republic e Revolut X).
- 16/11 19:50 — Santo mantiene la configurazione ogni notte con Opus; vuole che il Guardiano diventi un progetto Claude da riaprire direttamente. Aggiunta la sezione «Come riprendere».
- 17/11 07:50 — Prima analisi notturna (01:36–01:55): completata, rapporto valido e pubblicato (nessuna proposta; DiaSorin respinta dal supervisore, Interpump scartata; portafoglio non ancora nel database). Problemi: GitHub ha avviato il motore con quasi 6 ore di ritardo (06:08), quindi gli agenti hanno usato i prezzi di venerdì; nel giro delle 06:08 Yahoo non aveva la seduta di lunedì per le azioni europee e italiane (sì per indici e USA). Correzioni: motore tre volte a notte, secondo tentativo su un mese per i titoli in ritardo e qualità `in_ritardo` (niente COMPRA, fuori dall'ampiezza), analisi spostata alle 06:35, attesa fino a 40 minuti nella procedura se i dati non sono della seduta giusta. 30 test.
- 17/11 08:00 — Yahoo non aveva ancora la seduta di lunedì per 117 titoli europei ed ETF neanche alle 07:46: aggiunta la ricostruzione dai dati orari (recuperati 117 su 117; verifica su DiaSorin: 82,82 ricostruito contro 83,10 ufficiale, scarto 0,3% per l'asta di chiusura). Pagina aggiornata con i dati di lunedì; in fondo a «Oggi» ora c'è «Note sui dati di questo aggiornamento» (chiusure ricostruite, crypto solo da Kraken), chiusa di default. 31 test.
- 17/11 08:05 — Pagina ripubblicata a mano (versione 1794898897-a822) con i dati di lunedì e la nuova vista Oggi; il rapporto resta quello delle 01:52 e la pagina avvisa che si basa su dati precedenti. Nota tecnica: la pubblicazione del direttore aveva avvolto index.html in una cornice HTML (`<!doctype html>…<body>` prima della pagina): verificato con schermate a confronto che la resa è identica, nessuna azione.
- 21/11 18:15 — Rapporto del 21/11 pubblicato alle 05:21 (nessuna proposta: i 42 COMPRA venivano tutti dal ritracciamento, 12 esaminati e scartati); l'attività delle 06:35 l'ha ricontrollato sugli stessi dati senza ripetere l'analisi. Poi, su richiesta di Santo, Guardiano messo in pausa fino a nuova data: vedi «Come riprendere».

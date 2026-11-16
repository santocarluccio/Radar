# Stato dei lavori — Il Guardiano dei Mercati

Repository: GitHub `santocarluccio/Radar`, ramo di lavoro `guardiano` (codice), ramo `dati` (dati del motore, scritto solo da GitHub Actions).
Specifica: `guardiano/SPECIFICA.md`. Questo file sta nel repository apposta: se una sessione si interrompe, la successiva riparte da qui.

Vincolo: il piano Claude dell'utente ha un limite di utilizzo ogni 5 ore. Pochi agenti, compiti mirati, poca ricerca web, salvataggi frequenti su GitHub.

## Piano

1. [x] Specifica e stato dei lavori nel repository
2. [x] Universi (`config/universo_*.json`) e `parametri.json`
3. [x] Motore, test, flusso GitHub Actions, README
4. [x] Primo giro con dati reali, correzione dei ticker, `main` aggiornato (attiva l'esecuzione notturna)
5. [x] Interfaccia (`guardiano/interfaccia/index.html`) provata su telefono e PC
6. [ ] Squadra di agenti: ruoli in `.claude/agents/`, `guardiano/agenti/PROCEDURA.md`, schema ed esempio del rapporto, comando `/guardiano`
7. [ ] Pubblicazione dell'artifact privato con i dati reali e database
8. [ ] Attività programmata notturna (analisi degli agenti verso le 02:00, ora di Roma) con notifica
9. [ ] Verifica finale
10. [ ] Ricerca con fonti, a piccole dosi: metodo PAC, dettagli operativi dei broker, strumenti GitHub, metodologia dei segnali

## Diario

- 15/11 21:50–04:12 — Prima sessione (Claude Fable 5.2): specifica scritta, agenti avviati due volte, interrotti dal limite di utilizzo; nulla salvato su GitHub.
- 16/11 06:30 — Seconda sessione (Claude Opus 5.5): specifica ricostruita dalla chat, con il ramo `dati` separato; lavoro diretto, salvataggi frequenti.
- 16/11 06:50 — Motore, 27 test e flusso pubblicati. Primo giro reale (Actions, 9 min): 196 strumenti su 199; prezzi verificati con le notizie (FTSE MIB 51.805 il 29/9, Technoprobe 32,32 €) e con CoinGecko (BTC 58.167 € il 15/11 alle 00:00 UTC). Correzioni: nuovi tentativi a lotti con tetto di tempo, Kraken completa le ultime barre crypto (Yahoo di notte resta indietro di un giorno), 7 crypto solo da Kraken, ETP bitcoin sostituito da VanEck VBTC.
- 16/11 07:10 — Terzo giro reale: 199 strumenti su 199, 78 s; `main` aggiornato in avanti (esecuzione notturna attiva alle 23:20 UTC).
- 16/11 07:40 — Interfaccia scritta e provata con Playwright (390×844 e 1280×800, tema chiaro e scuro): viste, scheda con grafico, portafoglio, calcolatore, simulatore PAC; nessun errore in console a parte i font bloccati nella prova.

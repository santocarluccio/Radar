# Stato dei lavori — Il Guardiano dei Mercati

Repository: GitHub `santocarluccio/Radar`, ramo di lavoro `guardiano` (codice), ramo `dati` (dati del motore, scritto solo da GitHub Actions).
Specifica: `guardiano/SPECIFICA.md`. Questo file sta nel repository apposta: se una sessione si interrompe, la successiva riparte da qui.

Vincolo: il piano Claude dell'utente ha un limite di utilizzo ogni 5 ore. Pochi agenti, compiti mirati, poca ricerca web, salvataggi frequenti su GitHub.

## Piano

1. [x] Specifica e stato dei lavori nel repository
2. [ ] Universi (`config/universo_*.json`) e `parametri.json`
3. [ ] Motore, test, flusso GitHub Actions, README
4. [ ] Primo giro con dati reali, correzione dei ticker, `main` aggiornato (attiva l'esecuzione notturna)
5. [ ] Interfaccia (`guardiano/interfaccia/index.html`) provata su telefono e PC
6. [ ] Squadra di agenti: ruoli in `.claude/agents/`, `guardiano/agenti/PROCEDURA.md`, schema ed esempio del rapporto, comando `/guardiano`
7. [ ] Pubblicazione dell'artifact privato con i dati reali e database
8. [ ] Attività programmata notturna (analisi degli agenti verso le 02:00, ora di Roma) con notifica
9. [ ] Verifica finale
10. [ ] Ricerca con fonti, a piccole dosi: metodo PAC, dettagli operativi dei broker, strumenti GitHub, metodologia dei segnali

## Diario

- 15/11 21:50–04:12 — Prima sessione (Claude Fable 5.2): specifica scritta, agenti avviati due volte, interrotti dal limite di utilizzo; nulla salvato su GitHub.
- 16/11 06:30 — Seconda sessione (Claude Opus 5.5): specifica ricostruita dalla chat, con il ramo `dati` separato; lavoro diretto, salvataggi frequenti.

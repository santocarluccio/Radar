# Il Guardiano dei Mercati — motore dati

Strumento personale di supporto alle decisioni. Il motore scarica ogni notte i prezzi giornalieri di circa 140 azioni (Italia, Europa, USA), 31 ETF per i piani di accumulo e 28 crypto, calcola indicatori, segnali e clima di mercato, verifica sullo storico le regole che usa e tiene un registro dei segnali emessi. **Non esegue ordini e non promette rendimenti**: segnala, spiega, misura. Le decisioni restano tue.

La specifica completa è in [SPECIFICA.md](SPECIFICA.md); lo stato dei lavori in [STATO_LAVORI.md](STATO_LAVORI.md).

## Cosa fa, in breve

1. **Scarica i prezzi** da Yahoo Finance (libreria `yfinance`); per le crypto, se Yahoo non risponde, ripiega sull'API pubblica di Kraken. Un ticker che non risponde non ferma il giro: finisce nell'elenco dei problemi.
2. **Calcola gli indicatori**: medie a 20, 50 e 200 giorni, RSI, ATR, massimi e minimi, momentum, forza relativa rispetto all'indice del mercato.
3. **Cerca tre tipi di segnale d'ingresso** (rottura dei massimi, ritracciamento in tendenza, ripartenza del trend) e **quattro avvisi d'uscita**, assegna a ogni titolo un punteggio da 0 a 100 e uno stato: COMPRA, OSSERVA, ESCI, DEBOLE o NEUTRO.
4. **Valuta il clima** di ogni mercato (favorevole, incerto, sfavorevole): con clima sfavorevole i nuovi acquisti vengono frenati.
5. **Verifica le regole sullo storico** (circa 5 anni, costi compresi) e scrive quanto sono state affidabili, mercato per mercato.
6. **Aggiorna il registro dei segnali**: ogni segnale COMPRA emesso viene seguito nei giorni successivi con le stesse regole, per misurare dal vivo se funzionano.
7. **Per gli ETF** calcola rendimenti, volatilità, ribassi massimi e una simulazione di PAC da 100 € al mese.

## Dove finiscono i dati

Il flusso GitHub Actions `guardiano-dati.yml` pubblica i file JSON sul ramo **`dati`** del repository, in `guardiano/dati/`. Il ramo contiene sempre un solo commit (l'ultimo giro), così il repository non si gonfia. I file si leggono anche da:

```
https://raw.githubusercontent.com/santocarluccio/Radar/dati/guardiano/dati/stato.json
```

Se un giro fallisce, i dati della volta precedente restano al loro posto e accanto compare `errore_ultimo_giro.json` con la diagnosi; `ultimo_log.txt` contiene sempre la coda dell'ultima esecuzione.

## Quando gira

- Ogni giorno alle **23:20 UTC** (00:20 ora di Roma d'inverno, 01:20 d'estate), dopo la chiusura di Wall Street. L'esecuzione programmata parte solo dal ramo `main`.
- A mano, dalla scheda **Actions → Guardiano - dati di mercato → Run workflow**.
- Da sola quando cambia il codice del motore o la configurazione.

**Attenzione:** GitHub sospende i flussi programmati dopo 60 giorni senza attività sul repository. Se succede, nella scheda Actions compare un avviso: apri il flusso e premi **Enable workflow**.

## Come si esegue sul computer

```
pip install -r guardiano/requirements.txt
python -m guardiano.motore.esegui --demo          # dati inventati, senza rete
python -m guardiano.motore.esegui                 # dati reali (serve l'accesso a Yahoo)
python -m pytest -q guardiano/test                # test
```

Opzioni: `--cartella-config` e `--cartella-dati` per cambiare cartelle, `--solo azioni|etf|crypto`, `--limite N` per provare con pochi strumenti.

## Come cambiare l'universo

Gli elenchi di titoli, ETF e crypto sono in `guardiano/config/universo_*.json`; i parametri delle regole in `guardiano/config/parametri.json` (niente numeri nascosti nel codice). Dopo una modifica il flusso riparte da solo e verifica i ticker: quelli senza dati compaiono in `stato.json → problemi`.

## Limiti da tenere a mente

- Dati giornalieri, non in tempo reale.
- I segnali sbagliano spesso: anche una regola «positiva» perde in molte operazioni.
- La verifica storica usa i titoli di oggi (distorsione da sopravvivenza) e costi stimati.
- Il passato non garantisce il futuro.

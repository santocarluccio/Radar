# Il Guardiano dei Mercati — specifica tecnica (v1.1)

> v1.1 (16/11/2026): i dati non si salvano più nel ramo del codice ma nel ramo orfano `dati` (sezioni 2, 10, 12, 14). Lo stato dei lavori è in `guardiano/STATO_LAVORI.md`.

## 1. Scopo

Strumento personale di supporto alle decisioni per un investitore privato italiano che opera a mano su Trade Republic (azioni, ETF, crypto, PAC) e Revolut X (crypto). Tre livelli:

1. **Motore** (Python, GitHub Actions, gratuito): scarica prezzi giornalieri, calcola indicatori, segnali, clima di mercato, backtest e registro dei segnali; scrive file JSON in `guardiano/dati/` e li pubblica sul ramo `dati`.
2. **Squadra di agenti** (Claude, di notte): legge i JSON, approfondisce i candidati (notizie, sentiment, solidità), li fa vagliare da supervisori e responsabile del rischio; il direttore scrive `rapporto.json`.
3. **Interfaccia** (pagina privata in Claude): mostra dati, segnali, rapporto, PAC, portafoglio, registro.

Orizzonte: da giorni a settimane, su barre giornaliere. Niente intraday. Lo strumento non esegue ordini e non promette rendimenti: segnala, spiega, misura. Ogni testo rivolto all'utente è in italiano semplice.

## 2. Struttura del repository

```
radar-dei-mercati.html          (app precedente: non toccare)
.github/workflows/guardiano-dati.yml
.claude/agents/                 (definizioni degli agenti)
.claude/commands/guardiano.md
guardiano/
  __init__.py
  SPECIFICA.md
  STATO_LAVORI.md
  README.md
  requirements.txt
  .gitignore                    (esclude dati/)
  config/
    universo_azioni.json
    universo_etf.json
    universo_crypto.json
    parametri.json
  motore/
    __init__.py
    fonti.py        scarico prezzi (yfinance + ripieghi), pulizia
    indicatori.py   medie, RSI, ATR, canali, momentum
    segnali.py      regole di ingresso, avvisi di uscita, punteggio, stato
    clima.py        clima di mercato per area
    backtest.py     verifica storica delle regole
    registro.py     registro dei segnali emessi (stato persistente)
    pac.py          metriche ETF e simulazione PAC
    esporta.py      scrittura dei JSON
    demo.py         dati sintetici deterministici
    esegui.py       ingresso da riga di comando
  dati/             (generata dal motore; NON versionata qui: pubblicata sul ramo `dati`)
  test/
  agenti/           (procedura e schema del rapporto)
  interfaccia/      (pagina)
```

## 3. Configurazione

### 3.1 `config/universo_azioni.json`

```json
{"aggiornato": "2026-11-15",
 "titoli": [{"nome": "Eni", "ticker_yahoo": "ENI.MI", "isin": "IT0003132476", "mercato": "IT", "paese": "Italia", "indice": "FTSE MIB", "settore": "Energia", "valuta": "EUR"}],
 "indici_riferimento": [{"mercato": "IT", "nome": "FTSE MIB", "ticker_yahoo": "FTSEMIB.MI", "principale": true}],
 "da_verificare": []}
```

`mercato` vale `IT`, `EU` o `US`. `isin` può essere `null`. Indici: IT `FTSEMIB.MI`; EU `^STOXX50E` (principale) e `^STOXX`; US `^GSPC` (principale) e `^NDX`; con mercato `GLOBALE`: `^VIX`, `EURUSD=X`.

Settori ammessi: `Energia`, `Finanza`, `Tecnologia`, `Salute`, `Industria`, `Beni di consumo`, `Lusso`, `Auto`, `Utility`, `Telecomunicazioni`, `Materiali`, `Immobiliare`, `Difesa`, `Media`.

### 3.2 `config/universo_etf.json`

```json
{"aggiornato": "2026-11-15",
 "etf": [{"nome": "Vanguard FTSE All-World UCITS ETF Acc", "isin": "IE00BK5BQT80", "ticker_yahoo": "VWCE.DE", "categoria": "Azionario globale", "indice_replicato": "FTSE All-World", "ter_pct": 0.19, "politica": "acc", "emittente": "Vanguard", "valuta_fondo": "USD", "copertura_cambio": false, "note": ""}],
 "da_verificare": []}
```

Categorie ammesse: `Azionario globale`, `Azionario USA`, `Azionario Europa`, `Mercati emergenti`, `Small cap globali`, `Fattoriali e dividendi`, `Bilanciati multi-asset`, `Obbligazionario globale`, `Titoli di Stato euro`, `Obbligazioni societarie euro`, `Monetari`, `Oro`, `Crypto ETP`.

### 3.3 `config/universo_crypto.json`

```json
{"aggiornato": "2026-11-15",
 "crypto": [{"nome": "Bitcoin", "simbolo": "BTC", "categoria": "Riserva di valore", "yahoo": "BTC-EUR", "kraken_pair_eur": "XBTEUR", "coingecko_id": "bitcoin", "su_trade_republic": true, "su_revolut_x": true, "note": ""}],
 "da_verificare": []}
```

Categorie ammesse: `Riserva di valore`, `Piattaforme smart contract`, `Pagamenti`, `DeFi`, `Infrastruttura e oracoli`, `Layer 2`, `Meme`, `AI e DePIN`, `Exchange token`, `Altro`. L'`id` di una crypto nei dati è sempre `<SIMBOLO>-EUR`. Il riferimento del mercato `CRYPTO` è Bitcoin.

### 3.4 `config/parametri.json` (valori predefiniti; il motore li legge, niente numeri nel codice)

```json
{
  "versione": 1,
  "storico_anni": 5,
  "barre_anno": {"azione": 252, "etf": 252, "crypto": 365},
  "costi_per_lato_pct": {"azione": 0.20, "etf": 0.15, "crypto": 0.40},
  "regole": {
    "rottura": {"finestra_massimo": 55, "volume_min_rapporto": 1.5, "usa_volume": {"azione": true, "crypto": false}, "finestra_uscita": 20},
    "ritracciamento": {"rsi_periodo": 2, "rsi_ingresso": 10, "rsi_uscita": 70, "max_barre": 10},
    "ripartenza": {"barre_osservate": 30, "barre_sotto_min": 20, "uscita_sotto_sma200_pct": 3.0}
  },
  "stop_atr_multiplo": 2.5,
  "obiettivo_multiplo_rischio": 2.0,
  "validita_segnale_barre": 3,
  "punteggio": {"tendenza": 40, "momentum": 25, "forza_relativa": 10, "setup": 15, "rischio": 10},
  "soglie": {"compra": 65, "osserva": 60, "debole": 35},
  "clima": {"ampiezza_favorevole": 55, "ampiezza_sfavorevole": 40},
  "candidati": {"max_acquisto": 8, "max_osservati": 6, "max_uscita": 15},
  "backtest": {"min_operazioni": 30, "riscaldamento_barre": 252},
  "pac": {"versamento_mensile_simulato": 100, "anni_simulazione": 5}
}
```

I costi per lato comprendono 1 € di commissione su un ordine di riferimento di 1.000 € (0,10%) più una stima di spread e slittamento.

## 4. Fonti dati

- **Primaria**: `yfinance`, `yf.download(lista, period="5y", interval="1d", auto_adjust=True, group_by="ticker", threads=True, progress=False)` a lotti di 40 con pausa di 2 s; i ticker falliti si riprovano uno a uno fino a 3 volte con attese di 5, 15, 45 s. Per gli ETF `period="max"`.
- **Crypto**: simbolo Yahoo da config (`BTC-EUR`). Ripiego se Yahoo fallisce o dà meno di 250 barre: Kraken pubblico `https://api.kraken.com/0/public/OHLC?pair=<kraken_pair_eur>&interval=1440` (fino a 720 candele giornaliere: tempo, apertura, massimo, minimo, chiusura, vwap, volume, conteggio).
- **Pulizia**: indice di date senza fuso, ordine crescente, colonne `apertura, massimo, minimo, chiusura, volume` in float; via le righe senza chiusura. **Barra parziale**: per le crypto si scarta l'ultima barra se ha la data UTC di oggi; per azioni, ETF e indici si scarta l'ultima barra se ha la data di oggi e l'ora UTC dell'esecuzione è tra le 07:00 e le 21:10 di un giorno feriale.
- **Qualità** per strumento: `storico_corto` sotto 260 barre; `dati_vecchi` se l'ultima barra ha più di 5 giorni di calendario (azioni, ETF) o più di 2 (crypto); altrimenti `ok`. Sotto 60 barre lo strumento è escluso e finisce in `stato.json → problemi`.
- Il motore non deve mai fallire per pochi ticker mancanti: produce comunque tutti i file e documenta i problemi. Esce con errore solo se manca più della metà degli strumenti o per errore fatale, e anche allora scrive `stato.json`.

## 5. Indicatori (barra corrente `t`; C chiusura, H massimo, L minimo, O apertura, V volume)

- `SMA_n[t]` media semplice di C su n barre (20, 50, 200).
- `RSI_n` e `ATR14` con lisciatura di Wilder. `atr_pct = ATR14/C·100`.
- `MaxPrec_n[t] = max(H[t-n..t-1])`, `MinPrec_n[t] = min(L[t-n..t-1])` (la barra corrente è esclusa).
- `max52`, `min52` su un anno di barre (`barre_anno`); `dist_max52_pct = C/max52 − 1`.
- `volume_rapporto = V[t] / media(V[t-20..t-1])`.
- `volatilita_ann_pct`: deviazione standard dei rendimenti logaritmici a 20 barre per radice di `barre_anno`.
- `drawdown_pct = C / massimo mobile a un anno − 1`.
- `momentum_6m_pct = C[t-5]/C[t-131] − 1`; `momentum_12_1_pct = C[t-21]/C[t-252] − 1` (per le crypto stesse distanze in barre).
- `forza_relativa_3m_pct`: rendimento a 63 barre dello strumento meno quello dell'indice principale del suo mercato sulle stesse date.
- `percentile_momentum`: rango percentuale (0–100) di `momentum_6m_pct` dentro il mercato.
- `tendenza`: `rialzista` se C > SMA200 e SMA50 > SMA200; `ribassista` se C < SMA200 e SMA50 < SMA200; altrimenti `laterale`.
- `var_pct`: variazioni a 1, 5, 21, 63, 126, 252 barre (`g1, g5, m1, m3, m6, a1`).

## 6. Regole

Tutte usano solo dati fino a `t`. Stop iniziale comune: `stop = C[t] − 2,5·ATR14[t]`. Obiettivo indicativo (solo visualizzato, non usato come uscita): `C[t] + 2·(C[t] − stop)`. `rischio_pct = (C[t] − stop)/C[t]·100`.

| Regola | Nome mostrato | Ingresso alla barra t | Uscita di regola alla barra u |
|---|---|---|---|
| `rottura` | Rottura dei massimi | C[t] > MaxPrec_55[t] e C[t-1] ≤ MaxPrec_55[t-1] e C[t] > SMA200[t] e, dove `usa_volume`, V[t] ≥ 1,5·media(V[t-20..t-1]) | C[u] < MinPrec_20[u] |
| `ritracciamento` | Ritracciamento in tendenza | C[t] > SMA200[t] e SMA50[t] > SMA200[t] e RSI2[t] < 10 e RSI2[t-1] ≥ 10 | RSI2[u] > 70 oppure 10 barre in posizione |
| `ripartenza` | Ripartenza del trend | C[t] > SMA200[t] e C[t-1] ≤ SMA200[t-1] e SMA200[t] ≥ SMA200[t-20] e almeno 20 delle 30 barre precedenti chiuse sotto la SMA200 | C[u] < SMA200[u]·0,97 |

Avvisi di uscita, calcolati per tutti gli strumenti e mostrati se scattati nelle ultime 5 barre:

| Avviso | Nome mostrato | Condizione alla barra t | Gravità |
|---|---|---|---|
| `persa_media_200` | Persa la media a 200 giorni | C[t] < SMA200[t] e C[t-1] ≥ SMA200[t-1] | alta |
| `rottura_supporto` | Rottura del supporto a 20 giorni | C[t] < MinPrec_20[t] e C[t-1] ≥ MinPrec_20[t-1] | alta se C[t] < SMA200[t], altrimenti media |
| `incrocio_ribassista` | Incrocio ribassista delle medie | SMA50[t] < SMA200[t] e SMA50[t-1] ≥ SMA200[t-1] | alta |
| `ipercomprato` | Rialzo molto esteso | RSI14[t] > 80 e C[t] > SMA20[t] + 3·ATR14[t] | bassa |

## 7. Punteggio (0–100) e stato

Conteggio delle barre: `giorni_fa` = 0 è l'ultima barra; «nelle ultime k barre» ed «entro k barre» significano `giorni_fa` da 0 a k−1, «tra 4 e 10 barre» significa `giorni_fa` da 3 a 9. `segnali_attivi` elenca il segnale più recente di ogni regola nelle ultime 10 barre. Il controllo della condizione d'uscita vale anche alla chiusura della barra d'ingresso (backtest e registro). Per le crypto le variazioni `var_pct` usano distanze riscalate a 365 barre l'anno (g5 = 7 barre, m1 = 30, …); il momentum usa le stesse distanze delle azioni.

- **tendenza** (40): C > SMA200 → 15; SMA50 > SMA200 → 10; SMA200[t] > SMA200[t-20] → 5; C > SMA50 → 10.
- **momentum** (25): 0,15·percentile di `momentum_6m_pct` + 0,10·percentile di `momentum_12_1_pct`.
- **forza_relativa** (10): lineare da 0 (≤ −10%) a 10 (≥ +10%) su `forza_relativa_3m_pct`.
- **setup** (15): segnale d'ingresso entro 3 barre → 15; tra 4 e 10 barre → 8; altrimenti 0.
- **rischio** (10): parte da 10; −4 se la volatilità è nel quintile più alto del mercato; −3 se `drawdown_pct` < −25; −3 se `atr_pct` > 5 (azioni, ETF) o > 10 (crypto); minimo 0.

Stato, in ordine di precedenza:

1. `ESCI`: c'è un avviso di gravità alta nelle ultime 3 barre.
2. `COMPRA`: c'è un segnale d'ingresso nelle ultime 3 barre, punteggio ≥ 65 e clima del mercato diverso da `sfavorevole`.
3. `OSSERVA`: punteggio ≥ 60; oppure segnale d'ingresso recente con clima `sfavorevole` (in tal caso `frenato_dal_clima: true`).
4. `DEBOLE`: punteggio < 35.
5. `NEUTRO`.

Gli ETF ricevono indicatori, tendenza e metriche PAC ma non stato di trading.

## 8. Clima di mercato (`IT`, `EU`, `US`, `CRYPTO`)

Per ogni mercato: indice principale sopra o sotto SMA200 e SMA50; `ampiezza_sopra_sma200_pct` e `ampiezza_sopra_sma50_pct` (quota degli strumenti del mercato sopra le medie); variazione dell'indice a 1 e 3 mesi. Stato: `favorevole` se indice sopra SMA200 e ampiezza a 200 ≥ 55; `sfavorevole` se indice sotto SMA200 e ampiezza a 200 < 40; altrimenti `incerto`. In più: ultimo valore del VIX con etichetta (`calmo` < 15, `normale` 15–25, `teso` 25–35, `panico` > 35) ed EUR/USD. Ogni mercato ha una `descrizione` di una frase in italiano generata dal motore.

## 9. Backtest (verifica storica)

Per ogni regola e ogni strumento, dopo 252 barre di riscaldamento:

- Segnale alla chiusura di `t`, ingresso all'apertura di `t+1`. Se `O[t+1] ≤ stop` il segnale è annullato.
- Barra d'ingresso: se `L ≤ stop` uscita allo stop. Barre successive: se `O ≤ stop` uscita a `O`; altrimenti se `L ≤ stop` uscita allo stop; altrimenti, se alla chiusura vale la condizione d'uscita della regola, uscita all'apertura successiva (alla chiusura se è l'ultima barra).
- Un'operazione alla volta per strumento e regola. Le operazioni ancora aperte a fine dati non entrano nelle statistiche (si contano in `aperte`).
- Rendimento netto = lordo − 2·costo per lato.
- Statistiche per (regola, mercato) e per (regola, `TUTTI`): `operazioni`, `vincenti_pct`, `guadagno_medio_pct`, `perdita_media_pct`, `rendimento_medio_netto_pct`, `mediana_giorni`, `fattore_profitto`, `peggior_serie_perdite`, `prima_meta` e `seconda_meta` (operazioni divise alla data mediana del periodo: `operazioni`, `rendimento_medio_netto_pct`), `indice_periodo_pct` (variazione dell'indice principale nello stesso periodo), `giudizio`.
- `giudizio`: `dati insufficienti` sotto 30 operazioni; `positiva` se rendimento medio netto > 0,5 ed entrambe le metà > 0; `debole` se > 0; altrimenti `negativa`.
- **Forza relativa** (statistica di coorte, non regola d'ingresso): a ogni fine mese, rendimento a 21 barre del quintile più alto per `momentum_6m_pct` meno la media del mercato → `eccesso_medio_mensile_pct`, `mesi_positivi_pct`, `mesi`.
- `avvertenze` fisse nel file: universo composto dai titoli di oggi (distorsione da sopravvivenza); storico di circa 5 anni; costi stimati; il passato non garantisce il futuro.
- Nessuna ottimizzazione di parametri per singolo strumento.

## 10. Registro dei segnali (misura in avanti)

`dati/registro_segnali.json` è persistente: a ogni esecuzione il flusso lo recupera dal ramo `dati`, il motore lo carica, aggiunge i nuovi segnali e aggiorna quelli aperti con le stesse regole del backtest. Si registra un segnale quando uno strumento è in stato `COMPRA` per un segnale la cui data non è già registrata per quella coppia strumento–regola. `id = "<data>-<strumento>-<regola>"`. Prezzo d'ingresso: apertura della barra successiva al segnale; finché non c'è, stato `in attesa`. Riepilogo: chiusi, vincenti, rendimento medio netto, aperti.

## 11. ETF e PAC

Per ogni ETF, da tutto lo storico disponibile: rendimenti `ytd, a1, a3_annuo, a5_annuo, a10_annuo` (null se manca lo storico), `volatilita_ann_pct`, `max_drawdown_pct`, `drawdown_attuale_pct`, `tendenza`, `anni_storico`, e `pac_simulato` (versamento di 100 € il primo giorno di borsa di ogni mese per 5 anni o per lo storico disponibile se almeno 1 anno: `mesi, versato, valore, rendimento_annuo_pct` come tasso interno annualizzato). `dati/etf_mensili.json` contiene i rendimenti mensili percentuali (fino a 180 mesi) per il simulatore dell'interfaccia.

Profili illustrativi mostrati nell'interfaccia (esempi, non consulenza): **Prudente** azionario 20–40%, obbligazionario 40–60%, monetario 10–20%, oro 0–10%; **Bilanciato** azionario 50–70%, obbligazionario 25–40%, monetario 0–10%, oro 0–10%; **Dinamico** azionario 80–100%, obbligazionario 0–20%, oro 0–10%.

## 12. File prodotti (contratto dati)

Il motore li scrive in `guardiano/dati/`; il flusso li pubblica sul ramo `dati` nello stesso percorso. Si leggono da `https://raw.githubusercontent.com/santocarluccio/Radar/dati/guardiano/dati/<file>` oppure con `git clone --depth 1 --branch dati https://github.com/santocarluccio/Radar`.

JSON UTF-8, `ensure_ascii=False`, compatti. Prezzi con 4 cifre significative utili, percentuali con 2 decimali, date `AAAA-MM-GG`, orari ISO con fuso Europe/Rome.

**`stato.json`**
```json
{"generato_il": "2026-11-16T00:21:05+01:00", "modalita": "reale", "versione_motore": "1.0.0",
 "conteggi": {"azioni": 130, "etf": 30, "crypto": 25, "esclusi": 3},
 "ultima_seduta": {"IT": "2026-11-13", "EU": "2026-11-13", "US": "2026-11-13", "CRYPTO": "2026-11-15"},
 "fonti": {"azioni": "yfinance 1.0", "crypto": "yfinance, Kraken"},
 "problemi": [{"strumento": "XYZ.MI", "motivo": "nessun dato"}],
 "avvisi": ["testo"], "durata_secondi": 85}
```
`modalita` vale `reale` o `demo`.

**`azioni.json`** e **`crypto.json`**
```json
{"generato_il": "...", "strumenti": [{
  "id": "ENI.MI", "tipo": "azione", "nome": "Eni", "isin": "IT0003132476", "mercato": "IT", "settore": "Energia", "valuta": "EUR",
  "data": "2026-11-13", "prezzo": 14.52,
  "var_pct": {"g1": 0.4, "g5": 1.2, "m1": 3.4, "m3": 5.1, "m6": 8.0, "a1": 12.3},
  "indicatori": {"sma20": 14.2, "sma50": 13.9, "sma200": 13.4, "rsi14": 61.2, "rsi2": 78.0, "atr14": 0.21, "atr_pct": 1.45, "max52": 14.9, "min52": 11.8, "dist_max52_pct": -2.6, "volume_rapporto": 1.1, "volatilita_ann_pct": 19.5, "drawdown_pct": -2.6, "momentum_6m_pct": 8.0, "momentum_12_1_pct": 10.2, "forza_relativa_3m_pct": 2.1, "percentile_momentum": 72},
  "tendenza": "rialzista", "punteggio": 78,
  "componenti_punteggio": {"tendenza": 40, "momentum": 18, "forza_relativa": 6, "setup": 15, "rischio": 10},
  "stato": "COMPRA", "frenato_dal_clima": false,
  "segnali_attivi": [{"regola": "rottura", "nome": "Rottura dei massimi", "data": "2026-11-13", "giorni_fa": 0, "prezzo_segnale": 14.52, "stop": 13.99, "obiettivo": 15.58, "rischio_pct": 3.65, "descrizione": "Chiusura sopra il massimo degli ultimi 55 giorni con volumi 1,8 volte la media."}],
  "avvisi_uscita": [{"regola": "ipercomprato", "nome": "Rialzo molto esteso", "gravita": "bassa", "data": "2026-11-12", "giorni_fa": 1, "descrizione": "..."}],
  "livelli": {"stop_suggerito": 13.99, "supporto_20g": 13.8, "massimo_55g": 14.9},
  "qualita": "ok"}]}
```
Per le crypto: `tipo` `crypto`, `mercato` `CRYPTO`, `categoria` al posto di `settore`, `valuta` `EUR`, più `su_trade_republic` e `su_revolut_x`. `giorni_fa` conta le barre. `stop_suggerito` è sempre `prezzo − 2,5·ATR14`.

**`etf.json`**
```json
{"generato_il": "...", "strumenti": [{"id": "VWCE.DE", "tipo": "etf", "nome": "...", "isin": "IE00BK5BQT80", "categoria": "Azionario globale", "ter_pct": 0.19, "politica": "acc", "emittente": "Vanguard",
  "data": "2026-11-13", "prezzo": 142.3, "rendimenti_pct": {"ytd": 9.1, "a1": 14.2, "a3_annuo": 11.0, "a5_annuo": 10.4, "a10_annuo": null},
  "volatilita_ann_pct": 13.1, "max_drawdown_pct": -33.4, "drawdown_attuale_pct": -1.2, "tendenza": "rialzista", "anni_storico": 7.3,
  "pac_simulato": {"mesi": 60, "versato": 6000, "valore": 7910, "rendimento_annuo_pct": 10.9}, "qualita": "ok"}]}
```

**`etf_mensili.json`**: `{"VWCE.DE": {"mesi": ["2019-08", "..."], "rendimenti_pct": [1.2, -0.4]}}`

**`clima.json`**
```json
{"generato_il": "...", "mercati": [{"mercato": "IT", "nome": "Italia", "indice": "FTSE MIB", "stato": "favorevole", "indice_sopra_sma200": true, "indice_sopra_sma50": true, "indice_var_m1_pct": 2.1, "indice_var_m3_pct": 5.4, "ampiezza_sopra_sma200_pct": 68.0, "ampiezza_sopra_sma50_pct": 55.0, "descrizione": "..."}],
 "vix": {"valore": 15.2, "etichetta": "normale"}, "eurusd": 1.08}
```

**`serie_IT.json`, `serie_EU.json`, `serie_US.json`, `serie_CRYPTO.json`, `serie_ETF.json`**: ultime 260 barre per i grafici.
`{"ENI.MI": {"date": ["2025-11-14", "..."], "chiusura": [13.1], "sma50": [12.9], "sma200": [12.4]}}`

**`candidati_IT.json`** e analoghi per `EU`, `US`, `CRYPTO`: materiale per gli agenti.
`{"mercato": "IT", "clima": {…}, "acquisto": [oggetti strumento in stato COMPRA per punteggio decrescente, massimo 8], "osservati": [massimo 6 in stato OSSERVA], "uscita": [massimo 15 in stato ESCI], "affidabilita": [statistiche del backtest per quel mercato]}`

**`affidabilita.json`**
```json
{"generato_il": "...", "periodo": {"dal": "2022-11-15", "al": "2026-11-13"}, "avvertenze": ["..."],
 "regole": [{"regola": "rottura", "nome": "Rottura dei massimi", "mercato": "IT", "operazioni": 143, "aperte": 3, "vincenti_pct": 41.2, "guadagno_medio_pct": 9.8, "perdita_media_pct": -4.1, "rendimento_medio_netto_pct": 1.6, "mediana_giorni": 18, "fattore_profitto": 1.45, "peggior_serie_perdite": 7, "prima_meta": {"operazioni": 70, "rendimento_medio_netto_pct": 1.9}, "seconda_meta": {"operazioni": 73, "rendimento_medio_netto_pct": 1.3}, "indice_periodo_pct": 38.0, "giudizio": "positiva"}],
 "forza_relativa": [{"mercato": "IT", "mesi": 47, "eccesso_medio_mensile_pct": 0.4, "mesi_positivi_pct": 55.3}]}
```

**`registro_segnali.json`**
```json
{"aggiornato_il": "...", "segnali": [{"id": "2026-11-13-ENI.MI-rottura", "data": "2026-11-13", "strumento": "ENI.MI", "nome": "Eni", "mercato": "IT", "regola": "rottura", "prezzo_segnale": 14.52, "prezzo_ingresso": 14.55, "stop_iniziale": 13.99, "stato": "aperto", "data_chiusura": null, "prezzo_chiusura": null, "motivo_chiusura": null, "ultimo_prezzo": 14.8, "rendimento_pct": 1.72, "rendimento_netto_pct": 1.32, "barre": 3}],
 "riepilogo": {"in_attesa": 0, "aperti": 1, "chiusi": 0, "vincenti_pct": null, "rendimento_medio_netto_pct": null}}
```
`stato` vale `in attesa`, `aperto` o `chiuso`; `motivo_chiusura` vale `stop`, `regola` o `annullato`.

**`ultimo_log.txt`**: coda dell'output dell'ultima esecuzione, per la diagnosi.

## 13. Riga di comando, demo, test

`python -m guardiano.motore.esegui [--demo] [--cartella-config PERCORSO] [--cartella-dati PERCORSO] [--solo azioni|etf|crypto] [--limite N]`

- `--demo`: serie sintetiche deterministiche (seme per ticker) per tutto l'universo e gli indici; `stato.json → modalita: "demo"`. Serve per i test e per lo sviluppo senza rete.
- Test `pytest` in `guardiano/test/`: valori noti degli indicatori; serie costruite che fanno scattare ogni regola e ogni avviso una sola volta; un'operazione di backtest calcolata a mano, costi compresi; assenza di uso di dati futuri (troncare la serie non cambia i segnali passati); aggiornamento del registro su due esecuzioni successive; un'esecuzione demo completa che rispetta questo contratto.

## 14. Flusso GitHub Actions `guardiano-dati.yml`

- Avvio: `schedule` alle 23:20 UTC ogni giorno (dopo la chiusura USA; GitHub lo esegue solo dal ramo predefinito `main`), `workflow_dispatch`, e `push` su qualunque ramo tranne `dati` sui percorsi `guardiano/motore/**`, `guardiano/config/**`, `guardiano/test/**`, `guardiano/requirements.txt`, `.github/workflows/guardiano-dati.yml`.
- `permissions: contents: write`; `concurrency` con gruppo unico senza annullamento; `timeout-minutes: 30`; Python 3.12 con cache pip.
- Passi: installa le dipendenze; recupera dal ramo `dati`, se esiste, `guardiano/dati/registro_segnali.json`; esegue i test; esegue il motore salvando l'output in `guardiano/dati/ultimo_log.txt`; poi un passo `if: always()` che, se esiste `guardiano/dati/stato.json`, pubblica il contenuto di `guardiano/dati/` sul ramo orfano `dati` come unico commit (push forzato, autore `github-actions[bot]`, messaggio `dati: aggiornamento <data ora>`). Il ramo del codice non riceve mai commit di dati. I push fatti con `GITHUB_TOKEN` non riavviano il flusso.
- GitHub sospende i flussi programmati dopo 60 giorni senza attività sul repository: si riattivano dalla scheda Actions.

## 15. Rapporto degli agenti `rapporto.json` (lo scrive il direttore, lo legge l'interfaccia)

```json
{"data": "2026-11-16", "generato_il": "2026-11-16T02:31:00+01:00", "dati_del": "2026-11-16T00:21:05+01:00",
 "clima": {"sintesi": "due o tre frasi", "mercati": [{"mercato": "IT", "giudizio": "favorevole", "nota": "una frase"}]},
 "proposte": [{"id": "2026-11-16-ENI.MI", "strumento": "ENI.MI", "nome": "Eni", "tipo": "azione", "mercato": "IT", "azione": "COMPRA",
   "orizzonte": "2-6 settimane", "fiducia": "media", "tesi": "due frasi",
   "perche": ["...", "...", "..."],
   "piano": {"prezzo_riferimento": 14.52, "stop": 13.99, "obiettivo": 15.58, "rischio_pct": 3.65, "ingresso": "come entrare, in una frase", "dimensione": "come dimensionare, in una frase"},
   "rischi": ["...", "..."],
   "affidabilita_segnale": "cosa dice la verifica storica di questa regola in questo mercato, in una frase con i numeri",
   "solidita": {"giudizio": "buona", "punti": ["..."]},
   "notizie": [{"titolo": "...", "fonte": "...", "url": "https://...", "data": "2026-11-14"}],
   "vagli": {"analista": "...", "supervisore": "...", "rischio": "..."}}],
 "posizioni": [{"strumento": "ISP.MI", "nome": "Intesa Sanpaolo", "azione": "MANTIENI", "motivo": "una o due frasi", "stop_aggiornato": 4.1}],
 "scartate": [{"strumento": "XYZ", "nome": "...", "motivo": "perché non è passata"}],
 "pac": {"nota": "testo breve", "controlli": ["..."]},
 "avvertenze": "testo fisso sui limiti dello strumento"}
```
`azione` nelle proposte: `COMPRA` oppure `ATTENDI`. Nelle posizioni: `MANTIENI`, `RIDUCI`, `VENDI`. `fiducia`: `bassa`, `media`, `alta`. `proposte` può essere vuoto.

## 16. Interfaccia

Pagina unica pubblicata come artifact privato di Claude, con i file di dati accanto (`dati/*.json`, caricati per percorso relativo; sono la copia del ramo `dati` più `rapporto.json`). Sorgente in `guardiano/interfaccia/index.html`. Sezioni: **Oggi** (clima, proposte del direttore, avvisi sulle posizioni, data dei dati e loro qualità), **Azioni** (per mercato, filtri per stato e settore, scheda con grafico e livelli), **Crypto** (per categoria), **PAC** (profili illustrativi, tabella ETF, simulatore), **Portafoglio** (posizioni inserite a mano, esito, stato e stop di ciascuna, impostazioni di rischio, calcolatore della dimensione), **Registro** (segnali emessi e loro esito, affidabilità storica delle regole), **Guida** (come leggere, limiti, come eseguire su Trade Republic e Revolut X).

Dati dell'utente nel database dell'artifact, leggibili dagli agenti: documento `guardiano/portafoglio` `{"posizioni": [{"id", "strumento", "nome", "tipo", "quantita", "prezzo_carico", "data_acquisto", "piattaforma", "stop", "note"}], "aggiornato_il"}`; `guardiano/impostazioni` `{"profilo": "bilanciato", "capitale_trading_eur": null, "rischio_per_operazione_pct": 1, "max_posizioni": 6}`; `guardiano/storico` `{"operazioni": [...]}`. Se il database non è disponibile, ripiego su `localStorage` con avviso.

Finché i dati sono dimostrativi (`modalita: "demo"`) l'interfaccia mostra un avviso fisso e ben visibile su ogni sezione.

"""Scarico dei prezzi giornalieri e pulizia (sezione 4).

Fonte primaria: yfinance. Ripiego per le crypto: API pubblica di Kraken.
Nessuna eccezione di rete deve fermare l'esecuzione: i ticker falliti si riportano.
"""
from __future__ import annotations

import datetime as dt
import time
from typing import Callable

import numpy as np
import pandas as pd

COLONNE = ["apertura", "massimo", "minimo", "chiusura", "volume"]
MAPPA_YF = {"Open": "apertura", "High": "massimo", "Low": "minimo", "Close": "chiusura", "Volume": "volume"}
URL_KRAKEN = "https://api.kraken.com/0/public/OHLC?pair={pair}&interval=1440"


def pulisci(df: pd.DataFrame | None) -> pd.DataFrame:
    """Indice di date senza fuso e in ordine, colonne standard in float, via le righe senza chiusura."""
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=COLONNE, dtype=float)
    out = df.rename(columns=MAPPA_YF).copy()
    for col in COLONNE:
        if col not in out.columns:
            out[col] = np.nan
    out = out[COLONNE].apply(pd.to_numeric, errors="coerce").astype(float)
    idx = pd.DatetimeIndex(out.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    out.index = idx.normalize()
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out = out[out["chiusura"].notna() & (out["chiusura"] > 0)]
    # aperture, massimi e minimi mancanti: si ripiega sulla chiusura
    for col in ("apertura", "massimo", "minimo"):
        out[col] = out[col].where(out[col].notna() & (out[col] > 0), out["chiusura"])
    out["massimo"] = out[["massimo", "apertura", "chiusura"]].max(axis=1)
    out["minimo"] = out[["minimo", "apertura", "chiusura"]].min(axis=1)
    out["volume"] = out["volume"].fillna(0.0)
    out.index.name = "data"
    return out


def scarta_barra_parziale(df: pd.DataFrame, tipo: str, adesso_utc: dt.datetime) -> pd.DataFrame:
    """Crypto: via l'ultima barra se ha la data UTC di oggi. Azioni, ETF, indici: via l'ultima
    barra se ha la data di oggi e l'esecuzione cade tra le 07:00 e le 21:10 UTC di un giorno feriale."""
    if not len(df):
        return df
    oggi = pd.Timestamp(adesso_utc.date())
    ultima = df.index[-1]
    if tipo == "crypto":
        return df.iloc[:-1] if ultima == oggi else df
    minuti = adesso_utc.hour * 60 + adesso_utc.minute
    if ultima == oggi and adesso_utc.weekday() < 5 and 7 * 60 <= minuti <= 21 * 60 + 10:
        return df.iloc[:-1]
    return df


def qualita(df: pd.DataFrame, tipo: str, oggi: dt.date) -> str:
    if len(df) < 260:
        return "storico_corto"
    giorni = (pd.Timestamp(oggi) - df.index[-1]).days
    limite = 2 if tipo == "crypto" else 5
    if giorni > limite:
        return "dati_vecchi"
    return "ok"


def _estrai(dati: pd.DataFrame, ticker: str) -> pd.DataFrame | None:
    """Estrae un ticker dal risultato di yf.download (colonne a due livelli Ticker/Price)."""
    if dati is None or len(dati) == 0:
        return None
    if isinstance(dati.columns, pd.MultiIndex):
        livello0 = [str(x) for x in dati.columns.get_level_values(0)]
        for chiave in (ticker, ticker.upper()):
            if chiave in livello0:
                parte = dati[chiave]
                return parte.dropna(how="all") if len(parte) else None
        return None
    return dati.dropna(how="all")


def _giro(yf, gruppo: list[str], periodo: str, threads: bool, log, etichetta: str) -> tuple[dict, str | None]:
    """Un tentativo su un gruppo di ticker: restituisce le serie ottenute e l'eventuale errore."""
    try:
        dati = yf.download(gruppo if len(gruppo) > 1 else gruppo[0], period=periodo, interval="1d",
                           auto_adjust=True, group_by="ticker", threads=threads, progress=False)
    except Exception as e:  # rete, limiti di richieste, formato inatteso
        msg = f"{type(e).__name__}: {e}"[:200]
        log(f"  {etichetta}: errore {msg}")
        return {}, msg
    out = {}
    for t in gruppo:
        df = pulisci(_estrai(dati, t))
        if len(df):
            out[t] = df
    return out, None


def scarica_yahoo(tickers: list[str], periodo: str, log: Callable[[str], None],
                  lotto: int = 40, pausa: float = 2.0, attese=(20, 60, 120),
                  tetto_secondi: float = 600.0) -> tuple[dict, dict]:
    """Scarica a lotti; i ticker mancanti si riprovano a lotti più piccoli, fino a tre giri con
    attese crescenti, entro un tetto di tempo complessivo. Restituisce (serie, errori)."""
    import yfinance as yf  # importato qui: i test e la demo non ne hanno bisogno

    inizio = time.time()
    serie: dict[str, pd.DataFrame] = {}
    errori: dict[str, str] = {}
    unici = list(dict.fromkeys(tickers))
    for k in range(0, len(unici), lotto):
        gruppo = unici[k:k + lotto]
        ottenute, err = _giro(yf, gruppo, periodo, True, log, f"lotto {k // lotto + 1}")
        serie.update(ottenute)
        if err:
            for t in gruppo:
                errori.setdefault(t, err)
        if k + lotto < len(unici):
            time.sleep(pausa)
    for n_giro, attesa in enumerate(attese, start=1):
        mancanti = [t for t in unici if t not in serie]
        if not mancanti or time.time() - inizio + attesa > tetto_secondi:
            break
        log(f"  nuovo tentativo {n_giro} tra {attesa} s per {len(mancanti)} ticker: {', '.join(mancanti[:15])}"
            + (" …" if len(mancanti) > 15 else ""))
        time.sleep(attesa)
        piccolo = 10 if len(mancanti) > 10 else 1
        for k in range(0, len(mancanti), piccolo):
            gruppo = mancanti[k:k + piccolo]
            ottenute, err = _giro(yf, gruppo, periodo, len(gruppo) > 1, log, f"tentativo {n_giro}")
            serie.update(ottenute)
            if err:
                for t in gruppo:
                    errori[t] = err
            time.sleep(pausa)
    for t in unici:
        if t in serie:
            errori.pop(t, None)
        else:
            errori.setdefault(t, "nessun dato")
    return serie, errori


def ricostruisci_da_orari(tickers: list[str], dopo: dict, fino_a: dict, log: Callable[[str], None]) -> dict:
    """Ricostruisce le barre giornaliere mancanti dai dati orari degli ultimi 5 giorni.

    Serve quando Yahoo ha già la seduta negli indici ma non ancora nella serie giornaliera
    delle azioni europee. Le date sono quelle di Roma (tutte le Borse europee seguite chiudono
    entro la giornata). Restituisce, per ticker, solo le barre con data > dopo[t] e <= fino_a[t].
    I volumi possono essere incompleti (asta di chiusura)."""
    import yfinance as yf

    out: dict[str, pd.DataFrame] = {}
    if not tickers:
        return out
    try:
        dati = yf.download(tickers if len(tickers) > 1 else tickers[0], period="5d", interval="60m",
                           auto_adjust=True, group_by="ticker", threads=True, progress=False, prepost=False)
    except Exception as e:
        log(f"  dati orari non disponibili ({type(e).__name__}: {e})"[:200])
        return out
    for t in tickers:
        df = _estrai(dati, t)
        if df is None or not len(df):
            continue
        df = df.rename(columns=MAPPA_YF)
        for col in COLONNE:
            if col not in df.columns:
                df[col] = np.nan
        idx = pd.DatetimeIndex(df.index)
        if idx.tz is None:
            idx = idx.tz_localize("UTC")
        df = df[COLONNE].apply(pd.to_numeric, errors="coerce").copy()
        df.index = idx.tz_convert("Europe/Rome")
        df = df[df["chiusura"].notna()]
        if not len(df):
            continue
        giorni = df.groupby(df.index.date).agg(apertura=("apertura", "first"), massimo=("massimo", "max"),
                                               minimo=("minimo", "min"), chiusura=("chiusura", "last"),
                                               volume=("volume", "sum"))
        giorni.index = pd.DatetimeIndex(pd.to_datetime(giorni.index))
        giorni = giorni[(giorni.index > dopo[t]) & (giorni.index <= fino_a[t])]
        if len(giorni):
            out[t] = pulisci(giorni)
    return out


def scarica_kraken(pair: str, timeout: float = 20.0) -> pd.DataFrame:
    """Candele giornaliere da Kraken (fino a 720). Le date sono quelle UTC dell'apertura."""
    import requests

    r = requests.get(URL_KRAKEN.format(pair=pair), timeout=timeout)
    r.raise_for_status()
    js = r.json()
    if js.get("error"):
        raise RuntimeError("; ".join(js["error"]))
    risultato = js.get("result", {})
    chiavi = [k for k in risultato if k != "last"]
    if not chiavi:
        return pulisci(None)
    righe = risultato[chiavi[0]]
    df = pd.DataFrame(righe, columns=["tempo", "apertura", "massimo", "minimo", "chiusura", "vwap", "volume", "conteggio"])
    df.index = pd.to_datetime(df["tempo"].astype(int), unit="s")
    return pulisci(df[COLONNE])

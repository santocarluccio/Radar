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


def scarica_yahoo(tickers: list[str], periodo: str, log: Callable[[str], None],
                  lotto: int = 40, pausa: float = 2.0, attese=(5, 15, 45)) -> tuple[dict, dict]:
    """Scarica a lotti; i ticker falliti si riprovano uno a uno. Restituisce (serie, errori)."""
    import yfinance as yf  # importato qui: i test e la demo non ne hanno bisogno

    serie: dict[str, pd.DataFrame] = {}
    errori: dict[str, str] = {}
    unici = list(dict.fromkeys(tickers))
    for k in range(0, len(unici), lotto):
        gruppo = unici[k:k + lotto]
        try:
            dati = yf.download(gruppo, period=periodo, interval="1d", auto_adjust=True, group_by="ticker",
                               threads=True, progress=False)
        except Exception as e:  # rete, limiti di richieste, formato inatteso
            log(f"  lotto {k // lotto + 1}: errore {type(e).__name__}: {e}")
            dati = None
        for t in gruppo:
            df = pulisci(_estrai(dati, t))
            if len(df):
                serie[t] = df
        if k + lotto < len(unici):
            time.sleep(pausa)
    mancanti = [t for t in unici if t not in serie]
    for t in mancanti:
        ultimo_errore = "nessun dato"
        for attesa in attese:
            time.sleep(attesa)
            try:
                dati = yf.download(t, period=periodo, interval="1d", auto_adjust=True, group_by="ticker",
                                   threads=False, progress=False)
                df = pulisci(_estrai(dati, t))
                if len(df):
                    serie[t] = df
                    break
            except Exception as e:
                ultimo_errore = f"{type(e).__name__}: {e}"[:200]
        if t not in serie:
            errori[t] = ultimo_errore
    return serie, errori


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

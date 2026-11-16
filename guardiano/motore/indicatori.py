"""Indicatori tecnici (sezione 5 della specifica).

Ogni funzione usa solo dati fino alla barra corrente: nessun valore futuro.
Le serie sono DataFrame con colonne apertura, massimo, minimo, chiusura, volume.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Distanze in barre delle variazioni mostrate (g1, g5, m1, m3, m6, a1) per 252 barre l'anno.
DISTANZE_VAR = {"g1": 1, "g5": 5, "m1": 21, "m3": 63, "m6": 126, "a1": 252}


def sma(s: pd.Series, n: int) -> pd.Series:
    """Media semplice su n barre (NaN finché non ci sono n valori)."""
    return s.rolling(n, min_periods=n).mean()


def media_wilder(x: np.ndarray, n: int, inizio: int) -> np.ndarray:
    """Lisciatura di Wilder: il primo valore (alla posizione inizio+n-1) è la media
    semplice di x[inizio .. inizio+n-1], poi m[t] = (m[t-1]·(n-1) + x[t]) / n."""
    out = np.full(len(x), np.nan)
    primo = inizio + n - 1
    if len(x) <= primo:
        return out
    finestra = x[inizio:primo + 1]
    if np.isnan(finestra).any():
        return out
    m = float(finestra.mean())
    out[primo] = m
    for t in range(primo + 1, len(x)):
        v = x[t]
        if np.isnan(v):
            out[t] = m
            continue
        m = (m * (n - 1) + v) / n
        out[t] = m
    return out


def rsi(chiusura: pd.Series, n: int) -> pd.Series:
    """RSI di Wilder. Il primo valore è alla barra n (servono n variazioni)."""
    c = chiusura.to_numpy(dtype=float)
    delta = np.diff(c, prepend=np.nan)
    guadagni = np.where(delta > 0, delta, 0.0)
    perdite = np.where(delta < 0, -delta, 0.0)
    guadagni[0] = np.nan
    perdite[0] = np.nan
    mg = media_wilder(guadagni, n, 1)
    mp = media_wilder(perdite, n, 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = mg / mp
        valori = 100.0 - 100.0 / (1.0 + rs)
    valori = np.where((mp == 0) & (mg > 0), 100.0, valori)
    valori = np.where((mp == 0) & (mg == 0), 50.0, valori)
    valori = np.where(np.isnan(mg) | np.isnan(mp), np.nan, valori)
    return pd.Series(valori, index=chiusura.index)


def true_range(df: pd.DataFrame) -> pd.Series:
    """True range: max(H−L, |H−C[t−1]|, |L−C[t−1]|); alla prima barra H−L."""
    c_prec = df["chiusura"].shift(1)
    tr = pd.concat([
        df["massimo"] - df["minimo"],
        (df["massimo"] - c_prec).abs(),
        (df["minimo"] - c_prec).abs(),
    ], axis=1).max(axis=1, skipna=True)
    return tr


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """ATR di Wilder sui true range dalla seconda barra in poi (primo valore alla barra n)."""
    tr = true_range(df).to_numpy(dtype=float, copy=True)
    tr[0] = np.nan
    return pd.Series(media_wilder(tr, n, 1), index=df.index)


def max_precedente(s: pd.Series, n: int) -> pd.Series:
    """max(s[t−n .. t−1]): la barra corrente è esclusa."""
    return s.shift(1).rolling(n, min_periods=n).max()


def min_precedente(s: pd.Series, n: int) -> pd.Series:
    """min(s[t−n .. t−1]): la barra corrente è esclusa."""
    return s.shift(1).rolling(n, min_periods=n).min()


def scala_barre(k: int, barre_anno: int) -> int:
    """Converte una distanza pensata per 252 barre l'anno (borsa) in barre dello strumento."""
    return max(1, int(round(k * barre_anno / 252)))


def calcola(df: pd.DataFrame, barre_anno: int, indice: pd.Series | None = None,
            finestra_massimo: int = 55, finestra_supporto: int = 20) -> pd.DataFrame:
    """Calcola tutte le colonne di indicatori per una serie.

    `indice`: chiusure dell'indice principale del mercato (per la forza relativa).
    Restituisce un nuovo DataFrame con le colonne originali più gli indicatori.
    """
    out = df.copy()
    c, h, l, v = out["chiusura"], out["massimo"], out["minimo"], out["volume"]
    out["sma20"] = sma(c, 20)
    out["sma50"] = sma(c, 50)
    out["sma200"] = sma(c, 200)
    out["sma200_20fa"] = out["sma200"].shift(20)
    out["rsi14"] = rsi(c, 14)
    out["rsi2"] = rsi(c, 2)
    out["atr14"] = atr(out, 14)
    out["atr_pct"] = out["atr14"] / c * 100.0
    out["max_prec_55"] = max_precedente(h, finestra_massimo)
    out["min_prec_20"] = min_precedente(l, finestra_supporto)
    out["max52"] = h.rolling(barre_anno, min_periods=1).max()
    out["min52"] = l.rolling(barre_anno, min_periods=1).min()
    out["dist_max52_pct"] = (c / out["max52"] - 1.0) * 100.0
    media_vol = v.shift(1).rolling(20, min_periods=20).mean()
    out["volume_media20"] = media_vol
    out["volume_rapporto"] = (v / media_vol).where(media_vol > 0)
    rend_log = np.log(c / c.shift(1))
    out["volatilita_ann_pct"] = rend_log.rolling(20, min_periods=20).std() * np.sqrt(barre_anno) * 100.0
    out["drawdown_pct"] = (c / c.rolling(barre_anno, min_periods=1).max() - 1.0) * 100.0
    out["momentum_6m_pct"] = (c.shift(5) / c.shift(131) - 1.0) * 100.0
    out["momentum_12_1_pct"] = (c.shift(21) / c.shift(252) - 1.0) * 100.0
    if indice is not None and len(indice):
        idx = indice.reindex(out.index.union(indice.index)).ffill().reindex(out.index)
        r_str = c / c.shift(63) - 1.0
        r_idx = idx / idx.shift(63) - 1.0
        out["forza_relativa_3m_pct"] = (r_str - r_idx) * 100.0
    else:
        out["forza_relativa_3m_pct"] = np.nan
    for nome, k in DISTANZE_VAR.items():
        kk = scala_barre(k, barre_anno) if barre_anno != 252 else k
        out[f"var_{nome}"] = (c / c.shift(kk) - 1.0) * 100.0
    tend = np.where((c > out["sma200"]) & (out["sma50"] > out["sma200"]), "rialzista",
                    np.where((c < out["sma200"]) & (out["sma50"] < out["sma200"]), "ribassista", "laterale"))
    tend = np.where(out["sma200"].isna(), "laterale", tend)
    out["tendenza"] = tend
    return out

"""Dati sintetici deterministici per test e sviluppo senza rete.

Ogni ticker ha un seme ricavato dal suo nome: stessa fine e stesso ticker, stessa serie.
Le serie alternano fasi di rialzo e di ribasso, con picchi di volume, così che tutte le
regole e gli avvisi abbiano occasione di scattare.
"""
from __future__ import annotations

import datetime as dt
import hashlib

import numpy as np
import pandas as pd


def seme(ticker: str) -> int:
    return int.from_bytes(hashlib.sha256(ticker.encode("utf-8")).digest()[:8], "little")


def serie(ticker: str, tipo: str, fine: dt.date, anni: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seme(ticker))
    if tipo == "crypto":
        date = pd.date_range(end=pd.Timestamp(fine), periods=int(365 * anni), freq="D")
        vol_base = 0.035
    else:
        date = pd.bdate_range(end=pd.Timestamp(fine), periods=int(252 * anni))
        vol_base = {"indice": 0.010, "etf": 0.009, "vix": 0.06, "cambio": 0.004}.get(tipo, 0.017)
    n = len(date)
    if tipo == "vix":
        x = np.empty(n)
        x[0] = 18.0
        for t in range(1, n):
            x[t] = x[t - 1] + 0.08 * (18.0 - x[t - 1]) + rng.normal(0, 1.2)
        chiusura = np.clip(x, 9.0, 80.0)
    else:
        deriva = np.empty(n)
        t = 0
        while t < n:
            durata = int(rng.integers(60, 260))
            mu = rng.choice([0.0012, 0.0006, -0.0008, 0.0002], p=[0.35, 0.25, 0.25, 0.15])
            if tipo == "cambio":
                mu /= 10
            deriva[t:t + durata] = mu
            t += durata
        volat = vol_base * (1.0 + 0.5 * rng.random())
        rend = deriva + rng.normal(0, volat, n)
        inizio = {"cambio": 1.1, "indice": float(rng.uniform(3000, 40000))}.get(tipo, float(np.exp(rng.uniform(np.log(3), np.log(400)))))
        if tipo == "crypto":
            inizio = float(np.exp(rng.uniform(np.log(0.05), np.log(50000))))
        chiusura = inizio * np.exp(np.cumsum(rend))
    ampiezza = np.abs(rng.normal(0, vol_base * 0.8, n)) + vol_base * 0.3
    apertura = chiusura * (1 + rng.normal(0, vol_base * 0.4, n))
    apertura[1:] = np.where(rng.random(n - 1) < 0.85, chiusura[:-1] * (1 + rng.normal(0, vol_base * 0.3, n - 1)), apertura[1:])
    massimo = np.maximum(apertura, chiusura) * (1 + ampiezza / 2)
    minimo = np.minimum(apertura, chiusura) * (1 - ampiezza / 2)
    volume = rng.lognormal(mean=13.0, sigma=0.35, size=n)
    picchi = rng.random(n) < 0.04
    volume[picchi] *= rng.uniform(1.8, 3.5, picchi.sum())
    if tipo in ("indice", "vix", "cambio"):
        volume[:] = 0.0
    df = pd.DataFrame({"apertura": apertura, "massimo": massimo, "minimo": minimo,
                       "chiusura": chiusura, "volume": volume}, index=date)
    df.index.name = "data"
    return df

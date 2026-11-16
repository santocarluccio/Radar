"""Metriche degli ETF e simulazione del PAC (sezione 11)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _prezzo_a(df: pd.DataFrame, data: pd.Timestamp) -> float | None:
    """Chiusura all'ultima barra non successiva a `data` (None se lo storico inizia dopo)."""
    if df.index[0] > data:
        return None
    return float(df["chiusura"].loc[:data].iloc[-1])


def _annuo(finale: float, iniziale: float | None, anni: float) -> float | None:
    if iniziale is None or iniziale <= 0:
        return None
    return ((finale / iniziale) ** (1.0 / anni) - 1.0) * 100.0


def xirr(flussi: list[tuple[pd.Timestamp, float]]) -> float | None:
    """Tasso interno di rendimento annuo (in %) con date reali, per bisezione."""
    if len(flussi) < 2:
        return None
    t0 = flussi[0][0]

    def vnp(r: float) -> float:
        return sum(v / (1.0 + r) ** ((d - t0).days / 365.25) for d, v in flussi)

    basso, alto = -0.99, 10.0
    fb, fa = vnp(basso), vnp(alto)
    if math.isnan(fb) or math.isnan(fa) or fb * fa > 0:
        return None
    for _ in range(200):
        medio = (basso + alto) / 2
        fm = vnp(medio)
        if abs(fm) < 1e-9:
            break
        if fb * fm < 0:
            alto, fa = medio, fm
        else:
            basso, fb = medio, fm
    return ((basso + alto) / 2) * 100.0


def simula_pac(df: pd.DataFrame, versamento: float, mesi_max: int) -> dict | None:
    """Versamento il primo giorno di borsa di ogni mese, alla chiusura, per gli ultimi
    `mesi_max` mesi (o per lo storico disponibile se almeno 12 mesi)."""
    c = df["chiusura"]
    primi = c.groupby([c.index.year, c.index.month]).head(1)
    if len(primi) < 12:
        return None
    primi = primi.iloc[-mesi_max:]
    quote = float((versamento / primi).sum())
    fine = df.index[-1]
    valore = quote * float(c.iloc[-1])
    flussi = [(d, -versamento) for d in primi.index] + [(fine, valore)]
    return {"mesi": int(len(primi)), "versato": round(versamento * len(primi), 2), "valore": round(valore, 2),
            "rendimento_annuo_pct": xirr(flussi)}


def metriche(df: pd.DataFrame, par: dict) -> dict:
    c = df["chiusura"]
    fine = df.index[-1]
    ultimo = float(c.iloc[-1])
    prec_anno = c.loc[:pd.Timestamp(fine.year - 1, 12, 31)]
    ytd = (ultimo / float(prec_anno.iloc[-1]) - 1.0) * 100.0 if len(prec_anno) else None
    a1p = _prezzo_a(df, fine - pd.DateOffset(years=1))
    rend = {
        "ytd": ytd,
        "a1": (ultimo / a1p - 1.0) * 100.0 if a1p else None,
        "a3_annuo": _annuo(ultimo, _prezzo_a(df, fine - pd.DateOffset(years=3)), 3),
        "a5_annuo": _annuo(ultimo, _prezzo_a(df, fine - pd.DateOffset(years=5)), 5),
        "a10_annuo": _annuo(ultimo, _prezzo_a(df, fine - pd.DateOffset(years=10)), 10),
    }
    recente = c.loc[fine - pd.DateOffset(years=3):]
    lr = np.log(recente / recente.shift(1)).dropna()
    vol = float(lr.std() * math.sqrt(par["barre_anno"]["etf"]) * 100.0) if len(lr) >= 60 else None
    picco = c.cummax()
    max_dd = float((c / picco - 1.0).min() * 100.0)
    dd_att = float((ultimo / float(picco.iloc[-1]) - 1.0) * 100.0)
    anni = (fine - df.index[0]).days / 365.25
    p = par["pac"]
    pac = simula_pac(df, p["versamento_mensile_simulato"], 12 * p["anni_simulazione"])
    return {"rendimenti_pct": rend, "volatilita_ann_pct": vol, "max_drawdown_pct": max_dd,
            "drawdown_attuale_pct": dd_att, "anni_storico": anni, "pac_simulato": pac}


def rendimenti_mensili(df: pd.DataFrame, max_mesi: int = 180) -> dict:
    """Rendimenti mensili in % dalle chiusure di fine mese; il mese dell'ultima barra,
    incompleto, è escluso."""
    c = df["chiusura"]
    fine_mese = c.groupby([c.index.year, c.index.month]).tail(1)
    r = fine_mese.pct_change() * 100.0
    r = r.iloc[1:]
    if len(r):
        ultimo = df.index[-1]
        r = r[~((r.index.year == ultimo.year) & (r.index.month == ultimo.month))]
    r = r.iloc[-max_mesi:]
    return {"mesi": [d.strftime("%Y-%m") for d in r.index], "rendimenti_pct": [round(float(x), 2) for x in r]}

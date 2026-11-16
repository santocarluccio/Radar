"""Clima di mercato per area: IT, EU, US, CRYPTO (sezione 8)."""
from __future__ import annotations

import math

import pandas as pd

NOMI_MERCATI = {"IT": "Italia", "EU": "Europa", "US": "Stati Uniti", "CRYPTO": "Crypto"}


def etichetta_vix(v: float | None) -> str | None:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if v < 15:
        return "calmo"
    if v <= 25:
        return "normale"
    if v <= 35:
        return "teso"
    return "panico"


def _pct(x: float) -> str:
    return f"{x:.0f}%"


def descrizione(stato: str, sopra200: bool | None, ampiezza200: float | None, nome_indice: str) -> str:
    amp = f"{_pct(ampiezza200)} dei titoli sopra la media a 200 giorni" if ampiezza200 is not None else "ampiezza non disponibile"
    if sopra200 is None:
        pos = f"{nome_indice}: dati insufficienti"
    elif sopra200:
        pos = f"{nome_indice} sopra la media a 200 giorni"
    else:
        pos = f"{nome_indice} sotto la media a 200 giorni"
    finale = {"favorevole": "clima favorevole ai nuovi acquisti.",
              "sfavorevole": "clima sfavorevole: nuovi acquisti frenati.",
              "incerto": "clima incerto: prudenza sui nuovi acquisti."}[stato]
    return f"{pos}, {amp}: {finale}"


def calcola_mercato(mercato: str, nome_indice: str, serie_indice: pd.DataFrame | None,
                    ultime_righe: list[pd.Series], par: dict) -> dict:
    """`serie_indice`: indicatori dell'indice principale; `ultime_righe`: ultima barra con
    indicatori di ogni strumento del mercato."""
    sopra200 = sopra50 = None
    var_m1 = var_m3 = None
    if serie_indice is not None and len(serie_indice):
        u = serie_indice.iloc[-1]
        if pd.notna(u["sma200"]):
            sopra200 = bool(u["chiusura"] > u["sma200"])
        if pd.notna(u["sma50"]):
            sopra50 = bool(u["chiusura"] > u["sma50"])
        var_m1 = None if pd.isna(u.get("var_m1")) else float(u["var_m1"])
        var_m3 = None if pd.isna(u.get("var_m3")) else float(u["var_m3"])
    validi200 = [r for r in ultime_righe if pd.notna(r["sma200"])]
    validi50 = [r for r in ultime_righe if pd.notna(r["sma50"])]
    amp200 = (100.0 * sum(1 for r in validi200 if r["chiusura"] > r["sma200"]) / len(validi200)) if validi200 else None
    amp50 = (100.0 * sum(1 for r in validi50 if r["chiusura"] > r["sma50"]) / len(validi50)) if validi50 else None
    cl = par["clima"]
    if sopra200 is True and amp200 is not None and amp200 >= cl["ampiezza_favorevole"]:
        stato = "favorevole"
    elif sopra200 is False and amp200 is not None and amp200 < cl["ampiezza_sfavorevole"]:
        stato = "sfavorevole"
    else:
        stato = "incerto"
    return {
        "mercato": mercato, "nome": NOMI_MERCATI[mercato], "indice": nome_indice, "stato": stato,
        "indice_sopra_sma200": sopra200, "indice_sopra_sma50": sopra50,
        "indice_var_m1_pct": var_m1, "indice_var_m3_pct": var_m3,
        "ampiezza_sopra_sma200_pct": amp200, "ampiezza_sopra_sma50_pct": amp50,
        "descrizione": descrizione(stato, sopra200, amp200, nome_indice),
    }

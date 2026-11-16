"""Scrittura dei file JSON del contratto dati (sezione 12)."""
from __future__ import annotations

import datetime as dt
import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd

# chiavi il cui valore è un prezzo (4 cifre significative, almeno 2 decimali)
CHIAVI_PREZZO = {
    "prezzo", "sma20", "sma50", "sma200", "atr14", "max52", "min52", "prezzo_segnale", "stop", "obiettivo",
    "stop_suggerito", "supporto_20g", "massimo_55g", "prezzo_ingresso", "prezzo_chiusura", "ultimo_prezzo",
    "stop_iniziale", "valore", "versato", "eurusd", "chiusura",
}


def arrotonda_prezzo(x: float) -> float:
    if x == 0:
        return 0.0
    decimali = max(2, 4 - int(math.floor(math.log10(abs(x)))) - 1)
    return round(x, decimali)


def pulito(obj, chiave: str | None = None):
    """Converte in tipi JSON: NaN e infiniti → null, numpy → Python, date → stringhe;
    prezzi a 4 cifre significative, altri decimali a 2."""
    if isinstance(obj, dict):
        return {k: pulito(v, k) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [pulito(v, chiave) for v in obj]
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        x = float(obj)
        if math.isnan(x) or math.isinf(x):
            return None
        if chiave in CHIAVI_PREZZO:
            return arrotonda_prezzo(x)
        return round(x, 2)
    if isinstance(obj, int):
        return obj
    if isinstance(obj, (pd.Timestamp, dt.datetime)):
        return obj.strftime("%Y-%m-%d")
    if isinstance(obj, dt.date):
        return obj.isoformat()
    if obj is None or isinstance(obj, str):
        return obj
    if obj is pd.NaT:
        return None
    return str(obj)


def scrivi(cartella: Path, nome: str, obj, gia_pulito: bool = False) -> int:
    """Scrive in modo atomico; restituisce i byte scritti."""
    cartella.mkdir(parents=True, exist_ok=True)
    testo = json.dumps(obj if gia_pulito else pulito(obj), ensure_ascii=False, separators=(",", ":"))
    tmp = cartella / f".{nome}.tmp"
    tmp.write_text(testo, encoding="utf-8")
    os.replace(tmp, cartella / nome)
    return len(testo.encode("utf-8"))


def serie_grafico(d: pd.DataFrame, barre: int = 260) -> dict:
    coda = d.iloc[-barre:]

    def lista(col):
        return [None if pd.isna(x) else arrotonda_prezzo(float(x)) for x in coda[col]]

    return {"date": [x.strftime("%Y-%m-%d") for x in coda.index], "chiusura": lista("chiusura"),
            "sma50": lista("sma50"), "sma200": lista("sma200")}

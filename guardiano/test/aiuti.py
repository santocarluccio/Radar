"""Costruzione di serie di prova."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

RADICE = Path(__file__).resolve().parents[1]


def parametri() -> dict:
    return json.loads((RADICE / "config" / "parametri.json").read_text(encoding="utf-8"))


def da_chiusure(chiusure, volume=None, ampiezza: float = 0.005, inizio: str = "2020-01-01") -> pd.DataFrame:
    """Serie OHLCV dalle sole chiusure: apertura = chiusura precedente, massimo e minimo
    a ±ampiezza intorno al corpo della candela."""
    c = np.asarray(chiusure, dtype=float)
    o = np.concatenate([[c[0]], c[:-1]])
    h = np.maximum(o, c) * (1 + ampiezza)
    l = np.minimum(o, c) * (1 - ampiezza)
    v = np.ones(len(c)) * 1000.0 if volume is None else np.asarray(volume, dtype=float)
    idx = pd.bdate_range(inizio, periods=len(c))
    return pd.DataFrame({"apertura": o, "massimo": h, "minimo": l, "chiusura": c, "volume": v}, index=idx)


def fronti_salita(s: pd.Series) -> int:
    """Numero di episodi in cui la condizione diventa vera."""
    b = s.astype(bool).to_numpy()
    return int(b[0]) + int(np.sum(b[1:] & ~b[:-1]))

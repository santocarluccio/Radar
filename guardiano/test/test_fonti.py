"""Scarico con un finto yfinance: lotti, nuovi tentativi, pulizia, barra parziale."""
import datetime as dt
import sys
import types

import numpy as np
import pandas as pd

from guardiano.motore import fonti


def _finto_yf(sempre_mancanti: set[str], fallisce_primo_lotto: bool):
    chiamate = []

    def download(tickers, **kw):
        lista = [tickers] if isinstance(tickers, str) else list(tickers)
        chiamate.append(lista)
        if fallisce_primo_lotto and len(chiamate) == 1:
            raise RuntimeError("Too Many Requests")
        idx = pd.date_range("2026-01-01", periods=5, freq="D", tz="UTC")
        parti = {}
        for t in lista:
            if t in sempre_mancanti:
                continue
            parti[t.upper()] = pd.DataFrame({"Open": 1.0, "High": 2.0, "Low": 0.5, "Close": 1.5, "Volume": 10.0},
                                            index=idx.tz_localize(None))
        if not parti:
            return pd.DataFrame()
        return pd.concat(parti.values(), axis=1, keys=parti.keys(), names=["Ticker", "Price"])

    return types.SimpleNamespace(download=download), chiamate


def test_lotti_e_nuovi_tentativi(monkeypatch):
    finto, chiamate = _finto_yf({"NONESISTE"}, fallisce_primo_lotto=True)
    monkeypatch.setitem(sys.modules, "yfinance", finto)
    monkeypatch.setattr(fonti.time, "sleep", lambda s: None)
    tickers = [f"T{k}.MI" for k in range(45)] + ["NONESISTE"]
    serie, errori = fonti.scarica_yahoo(tickers, "5y", lambda m: None)
    assert len(serie) == 45 and set(errori) == {"NONESISTE"}
    assert list(serie["T0.MI"].columns) == fonti.COLONNE
    assert len(chiamate) <= 2 + 3 * 5 + 3  # primo passaggio + al massimo tre giri a lotti piccoli


def test_pulizia_e_barra_parziale():
    idx = pd.to_datetime(["2026-11-12", "2026-11-13", "2026-11-13", "2026-11-16"]).tz_localize("Europe/Rome")
    df = pd.DataFrame({"Open": [1, np.nan, 2, 3], "High": [1, 2, 2, 3], "Low": [1, 1, 1, 3],
                       "Close": [1, 2, 2.5, np.nan], "Volume": [1, 1, 1, 1]}, index=idx)
    p = fonti.pulisci(df)
    assert list(p.index.strftime("%Y-%m-%d")) == ["2026-11-12", "2026-11-13"]
    assert p["chiusura"].iloc[-1] == 2.5  # tra i duplicati vince l'ultimo
    lunedi = pd.DataFrame({"chiusura": [1.0, 2.0]}, index=pd.to_datetime(["2026-11-13", "2026-11-16"]))
    di_giorno = dt.datetime(2026, 11, 16, 12, 0, tzinfo=dt.timezone.utc)
    di_notte = dt.datetime(2026, 11, 16, 23, 20, tzinfo=dt.timezone.utc)
    assert len(fonti.scarta_barra_parziale(lunedi, "azione", di_giorno)) == 1
    assert len(fonti.scarta_barra_parziale(lunedi, "azione", di_notte)) == 2
    assert len(fonti.scarta_barra_parziale(lunedi, "crypto", di_notte)) == 1

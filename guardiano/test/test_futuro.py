"""Troncare la serie non deve cambiare indicatori, segnali e operazioni passate."""
import datetime as dt

import numpy as np
import pandas as pd

from guardiano.motore import backtest as bt
from guardiano.motore import demo
from guardiano.motore import indicatori as ind
from guardiano.motore import segnali as sg
from guardiano.test.aiuti import parametri

PAR = parametri()
FINE = dt.date(2026, 11, 13)


def _pipeline(df, indice):
    d = ind.calcola(df, 252, indice["chiusura"])
    return d, sg.ingressi(d, PAR, "azione"), sg.avvisi(d), sg.condizioni_uscita(d, PAR)


def test_nessun_dato_futuro():
    df = demo.serie("PROVA.MI", "azione", FINE)
    indice = demo.serie("FTSEMIB.MI", "indice", FINE)
    for taglio in (900, 1100, len(df) - 7):
        pieno = _pipeline(df, indice)
        corto = _pipeline(df.iloc[:taglio], indice.loc[:df.index[taglio - 1]])
        a, b = pieno[0].iloc[:taglio], corto[0]
        for col in b.columns:
            if col == "tendenza":
                assert (a[col] == b[col]).all(), col
            else:
                assert np.allclose(a[col].to_numpy(float), b[col].to_numpy(float), equal_nan=True), col
        for r in sg.REGOLE:
            assert (pieno[1][r].iloc[:taglio] == corto[1][r]).all(), r
            assert (pieno[3][r].iloc[:taglio] == corto[3][r]).all(), r
        for nome in sg.AVVISI:
            assert (pieno[2][nome][0].iloc[:taglio] == corto[2][nome][0]).all(), nome


def test_backtest_non_guarda_avanti():
    df = demo.serie("ALTRA.MI", "azione", FINE)
    indice = demo.serie("FTSEMIB.MI", "indice", FINE)
    taglio = len(df) - 150

    def operazioni(d, ing, usc):
        stop = (d["chiusura"] - 2.5 * d["atr14"]).to_numpy(float)
        tot = []
        for r in sg.REGOLE:
            o, _, _ = bt.simula(d.index, *(d[k].to_numpy(float) for k in ("apertura", "massimo", "minimo", "chiusura")),
                                ing[r].to_numpy(), usc[r].to_numpy(), stop, 0.2, 252,
                                10 if r == "ritracciamento" else None)
            tot += [(r, x["data_ingresso"], x["data_uscita"], round(x["netto_pct"], 9)) for x in o]
        return tot

    p = _pipeline(df, indice)
    c = _pipeline(df.iloc[:taglio], indice.loc[:df.index[taglio - 1]])
    ultima = df.index[taglio - 1]
    pieno = [x for x in operazioni(p[0], p[1], p[3]) if x[2] < ultima]
    corto = [x for x in operazioni(c[0], c[1], c[3]) if x[2] < ultima]
    assert pieno == corto and len(pieno) > 0

import numpy as np
import pandas as pd
import pytest

from guardiano.motore import indicatori as ind
from guardiano.test.aiuti import da_chiusure

# Esempio classico di StockCharts per l'RSI a 14 periodi.
CHIUSURE_SC = [44.3389, 44.0902, 44.1497, 43.6124, 44.3278, 44.8264, 45.0955, 45.4245, 45.8433, 46.0826,
               45.8931, 46.0328, 45.6140, 46.2820, 46.2820, 46.0028, 46.0328, 46.4116, 46.2222, 45.6439]


def test_rsi_valori_noti():
    r = ind.rsi(pd.Series(CHIUSURE_SC), 14)
    assert r.iloc[:14].isna().all()
    assert r.iloc[14] == pytest.approx(70.53, abs=0.05)
    assert r.iloc[15] == pytest.approx(66.32, abs=0.05)


def test_rsi_casi_limite():
    su = ind.rsi(pd.Series(np.arange(1, 40, dtype=float)), 14)
    giu = ind.rsi(pd.Series(np.arange(40, 1, -1, dtype=float)), 14)
    piatto = ind.rsi(pd.Series(np.full(30, 5.0)), 14)
    assert (su.dropna() == 100).all()
    assert (giu.dropna() == 0).all()
    assert (piatto.dropna() == 50).all()
    alterno = ind.rsi(pd.Series(100 + np.array([0, 1] * 30, dtype=float)), 14).dropna()
    assert ((alterno > 40) & (alterno < 60)).all()


def test_media_semplice():
    s = ind.sma(pd.Series([1.0, 2, 3, 4, 5]), 3)
    assert s.isna().iloc[:2].all()
    assert list(s.iloc[2:]) == [2.0, 3.0, 4.0]


def test_atr_wilder_a_mano():
    df = pd.DataFrame({
        "apertura": [10, 10, 10, 10, 10.0], "massimo": [11, 12, 11, 13, 12.0],
        "minimo": [9, 10, 9, 10, 11.0], "chiusura": [10, 11, 10, 12, 11.0], "volume": [1.0] * 5})
    # TR dalla seconda barra: max(2,2,0)=2 ; max(2,0,2)=2 ; max(3,3,0)=3 ; max(1,0,1)=1
    a = ind.atr(df, 3)
    assert a.iloc[:3].isna().all()
    assert a.iloc[3] == pytest.approx((2 + 2 + 3) / 3)
    assert a.iloc[4] == pytest.approx(((7 / 3) * 2 + 1) / 3)


def test_massimo_precedente_esclude_la_barra_corrente():
    h = pd.Series([1.0, 2, 3, 10, 4])
    m = ind.max_precedente(h, 3)
    assert m.iloc[3] == 3.0
    assert m.iloc[4] == 10.0
    assert ind.min_precedente(pd.Series([5.0, 4, 3, 1, 6]), 3).iloc[3] == 3.0


def test_forza_relativa_nulla_contro_se_stesso_e_tendenza():
    df = da_chiusure(100 + np.arange(300) * 0.2)
    d = ind.calcola(df, 252, df["chiusura"])
    assert d["forza_relativa_3m_pct"].dropna().abs().max() < 1e-9
    assert d["tendenza"].iloc[-1] == "rialzista"
    assert d["var_g1"].iloc[-1] == pytest.approx((df["chiusura"].iloc[-1] / df["chiusura"].iloc[-2] - 1) * 100)

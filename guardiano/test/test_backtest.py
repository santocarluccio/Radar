import numpy as np
import pandas as pd
import pytest

from guardiano.motore import backtest as bt


def _arr(*x):
    return np.array(x, dtype=float)


def _caso(O, L=None, uscita_a=None, n=8):
    O = np.asarray(O, dtype=float)
    H = O + 0.5
    L = O - 0.5 if L is None else np.asarray(L, dtype=float)
    C = O + 0.2
    date = pd.bdate_range("2024-01-01", periods=len(O))
    ing = np.zeros(len(O), dtype=bool)
    ing[1] = True
    usc = np.zeros(len(O), dtype=bool)
    if uscita_a is not None:
        usc[uscita_a] = True
    return date, O, H, L, C, ing, usc


def test_operazione_calcolata_a_mano_con_costi():
    date, O, H, L, C, ing, usc = _caso([10, 10, 10, 11, 12, 12, 12, 12], uscita_a=3)
    stop = np.full(len(O), 9.0)
    ops, aperte, annullate = bt.simula(date, O, H, L, C, ing, usc, stop, costo_pct=0.2)
    assert (aperte, annullate, len(ops)) == (0, 0, 1)
    o = ops[0]
    # ingresso all'apertura della barra 2 (10), condizione alla chiusura della 3, uscita all'apertura della 4 (12)
    assert o["prezzo_ingresso"] == 10 and o["prezzo_uscita"] == 12
    assert o["lordo_pct"] == pytest.approx(20.0)
    assert o["netto_pct"] == pytest.approx(19.6)
    assert o["motivo"] == "regola" and o["barre"] == 3
    assert o["giorni"] == (date[4] - date[2]).days


def test_stop_in_apertura_e_durante_la_barra():
    date, O, H, L, C, ing, usc = _caso([10, 10, 10, 9.0, 9, 9, 9, 9], L=[9.5, 9.5, 9.6, 8.5, 8.5, 8.5, 8.5, 8.5])
    ops, _, _ = bt.simula(date, O, H, L, C, ing, usc, np.full(8, 9.5), costo_pct=0.0)
    assert ops[0]["motivo"] == "stop" and ops[0]["prezzo_uscita"] == 9.0
    date, O, H, L, C, ing, usc = _caso([10, 10, 10, 10, 10, 10, 10, 10], L=[9.6, 9.6, 9.6, 9.4, 9.6, 9.6, 9.6, 9.6])
    ops, _, _ = bt.simula(date, O, H, L, C, ing, usc, np.full(8, 9.5), costo_pct=0.0)
    assert ops[0]["prezzo_uscita"] == 9.5 and ops[0]["lordo_pct"] == pytest.approx(-5.0)


def test_segnale_annullato_e_operazione_aperta():
    date, O, H, L, C, ing, usc = _caso([10, 10, 9.0, 9, 9, 9, 9, 9])
    ops, aperte, annullate = bt.simula(date, O, H, L, C, ing, usc, np.full(8, 9.5), costo_pct=0.0)
    assert (len(ops), aperte, annullate) == (0, 0, 1)
    date, O, H, L, C, ing, usc = _caso([10] * 8)
    ops, aperte, _ = bt.simula(date, O, H, L, C, ing, usc, np.full(8, 5.0), costo_pct=0.0)
    assert (len(ops), aperte) == (0, 1)


def test_limite_di_barre():
    date, O, H, L, C, ing, usc = _caso([10, 10, 10, 11, 12, 13, 14, 15])
    ops, _, _ = bt.simula(date, O, H, L, C, ing, usc, np.full(8, 5.0), costo_pct=0.0, max_barre=2)
    assert ops[0]["prezzo_uscita"] == 12 and ops[0]["barre"] == 3


def test_giudizio():
    date = pd.bdate_range("2022-01-01", periods=400)
    ops = [{"data_ingresso": date[k * 10], "data_uscita": date[k * 10 + 5], "netto_pct": 1.0, "giorni": 7}
           for k in range(36)]
    st = bt.statistiche(ops, 0, date[0], date[-1], 5.0, 30)
    assert st["giudizio"] == "positiva" and st["vincenti_pct"] == 100 and st["peggior_serie_perdite"] == 0
    assert bt.statistiche(ops[:10], 0, date[0], date[-1], None, 30)["giudizio"] == "dati insufficienti"
    meno = [dict(o, netto_pct=-1.0) for o in ops]
    assert bt.statistiche(meno, 0, date[0], date[-1], None, 30)["giudizio"] == "negativa"

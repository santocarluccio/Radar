"""Serie costruite che fanno scattare ogni regola e ogni avviso una sola volta."""
import numpy as np

from guardiano.motore import indicatori as ind
from guardiano.motore import segnali as sg
from guardiano.test.aiuti import da_chiusure, fronti_salita, parametri

PAR = parametri()


def _calc(df):
    return ind.calcola(df, 252, None)


def serie_rottura(volume_alto=True):
    salita = np.linspace(100, 140, 200)
    piatto = 140 + 0.3 * np.sin(np.arange(80))
    rottura = [145.0]
    dopo = np.full(19, 145.0)
    c = np.concatenate([salita, piatto, rottura, dopo])
    v = np.full(len(c), 1000.0)
    if volume_alto:
        v[280] = 3000.0
    return da_chiusure(c, v)


def test_rottura_una_volta_con_volume():
    d = _calc(serie_rottura())
    s = sg.ingressi(d, PAR, "azione")["rottura"]
    assert int(s.sum()) == 1 and bool(s.iloc[280])


def test_rottura_senza_volume_solo_per_crypto():
    d = _calc(serie_rottura(volume_alto=False))
    assert int(sg.ingressi(d, PAR, "azione")["rottura"].sum()) == 0
    s = sg.ingressi(d, PAR, "crypto")["rottura"]
    assert int(s.sum()) == 1 and bool(s.iloc[280])


def test_ritracciamento_una_volta():
    c = np.concatenate([np.linspace(100, 160, 260), [155.0, 152.0], 152 + 0.23 * np.arange(1, 31)])
    d = _calc(da_chiusure(c))
    s = sg.ingressi(d, PAR, "azione")["ritracciamento"]
    assert int(s.sum()) == 1 and bool(s.iloc[260])


def serie_ripartenza():
    c = np.concatenate([np.linspace(100, 175, 300), np.full(25, 140.0), [160.0], 160 + 0.25 * np.arange(1, 35)])
    return _calc(da_chiusure(c))


def test_ripartenza_una_volta():
    d = serie_ripartenza()
    s = sg.ingressi(d, PAR, "azione")["ripartenza"]
    assert int(s.sum()) == 1 and bool(s.iloc[325])


def test_persa_media_200_una_volta():
    d = serie_ripartenza()
    s, grav = sg.avvisi(d)["persa_media_200"]
    assert int(s.sum()) == 1 and bool(s.iloc[300]) and grav.iloc[300] == "alta"


def test_rottura_supporto_una_volta():
    c = np.concatenate([np.full(40, 100.0), np.full(30, 95.0)])
    d = _calc(da_chiusure(c))
    s, grav = sg.avvisi(d)["rottura_supporto"]
    assert int(s.sum()) == 1 and bool(s.iloc[40]) and grav.iloc[40] == "media"


def test_incrocio_ribassista_una_volta():
    c = np.concatenate([np.linspace(100, 200, 250), np.linspace(199.6, 100, 250)])
    d = _calc(da_chiusure(c))
    s, _ = sg.avvisi(d)["incrocio_ribassista"]
    assert int(s.sum()) == 1


def test_ipercomprato_un_episodio():
    c = np.concatenate([np.full(100, 100.0), 100 + 3.0 * np.arange(1, 13), np.full(30, 136.0)])
    d = _calc(da_chiusure(c))
    s, grav = sg.avvisi(d)["ipercomprato"]
    assert fronti_salita(s) == 1
    assert (grav[s] == "bassa").all()


def test_stato_e_punteggio():
    segn = [{"giorni_fa": 0}]
    assert sg.stato(70, segn, [], "favorevole", PAR) == ("COMPRA", False)
    assert sg.stato(70, segn, [], "sfavorevole", PAR) == ("OSSERVA", True)
    assert sg.stato(70, segn, [{"gravita": "alta", "giorni_fa": 1}], "favorevole", PAR)[0] == "ESCI"
    assert sg.stato(70, [{"giorni_fa": 3}], [], "favorevole", PAR) == ("OSSERVA", False)
    assert sg.stato(30, [], [], "favorevole", PAR) == ("DEBOLE", False)
    assert sg.stato(50, [], [], "favorevole", PAR) == ("NEUTRO", False)

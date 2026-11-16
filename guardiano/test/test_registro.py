"""Aggiornamento del registro su esecuzioni successive."""
import pandas as pd

from guardiano.motore import registro as rg
from guardiano.test.aiuti import parametri

PAR = parametri()


def _dati(righe):
    idx = pd.bdate_range("2026-11-02", periods=len(righe))
    df = pd.DataFrame(righe, columns=["apertura", "massimo", "minimo", "chiusura"], index=idx)
    return df


def _strumento(data_segnale):
    return {"id": "PROVA.MI", "nome": "Prova", "mercato": "IT", "tipo": "azione", "stato": "COMPRA",
            "segnali_attivi": [{"regola": "rottura", "data": data_segnale, "giorni_fa": 0,
                                "prezzo_segnale": 10.0, "stop": 9.0}]}


def test_registro_su_esecuzioni_successive():
    righe = [(10, 10.2, 9.8, 10.0), (10.1, 10.5, 10.0, 10.4), (10.3, 10.4, 8.8, 9.2)]
    d = _dati(righe)
    data_segnale = d.index[0].strftime("%Y-%m-%d")
    nessuna_uscita = {"PROVA.MI": {r: pd.Series(False, index=d.index) for r in ("rottura", "ritracciamento", "ripartenza")}}

    r1 = rg.aggiorna(None, [_strumento(data_segnale)], {"PROVA.MI": d.iloc[:1]}, nessuna_uscita, PAR, "t1")
    assert r1["riepilogo"]["in_attesa"] == 1
    s = r1["segnali"][0]
    assert s["id"] == f"{data_segnale}-PROVA.MI-rottura" and s["stato"] == "in attesa"

    r2 = rg.aggiorna(r1, [_strumento(data_segnale)], {"PROVA.MI": d.iloc[:2]}, nessuna_uscita, PAR, "t2")
    assert len(r2["segnali"]) == 1  # nessun doppione
    s = r2["segnali"][0]
    assert s["stato"] == "aperto" and s["prezzo_ingresso"] == 10.1 and s["barre"] == 1
    assert abs(s["rendimento_netto_pct"] - ((10.4 / 10.1 - 1) * 100 - 0.4)) < 1e-9

    r3 = rg.aggiorna(r2, [], {"PROVA.MI": d}, nessuna_uscita, PAR, "t3")
    s = r3["segnali"][0]
    assert s["stato"] == "chiuso" and s["motivo_chiusura"] == "stop" and s["prezzo_chiusura"] == 9.0
    assert r3["riepilogo"]["chiusi"] == 1 and r3["riepilogo"]["vincenti_pct"] == 0

    r4 = rg.aggiorna(r3, [], {"PROVA.MI": d}, nessuna_uscita, PAR, "t4")
    assert r4["segnali"] == r3["segnali"]  # ripetere non cambia nulla


def test_segnale_annullato_in_apertura():
    d = _dati([(10, 10.2, 9.8, 10.0), (8.9, 9.1, 8.7, 9.0)])
    data_segnale = d.index[0].strftime("%Y-%m-%d")
    usc = {"PROVA.MI": {r: pd.Series(False, index=d.index) for r in ("rottura", "ritracciamento", "ripartenza")}}
    r = rg.aggiorna(None, [_strumento(data_segnale)], {"PROVA.MI": d}, usc, PAR, "t")
    s = r["segnali"][0]
    assert s["stato"] == "chiuso" and s["motivo_chiusura"] == "annullato"
    assert r["riepilogo"]["annullati"] == 1 and r["riepilogo"]["chiusi"] == 0


def test_una_operazione_alla_volta_per_coppia():
    # giorni: 0 segnale A, 1 ingresso, 2 nuovo segnale B (mentre A è aperta), 3 stop di A, 3 segnale C (giorno d'uscita)
    righe = [(10, 10.2, 9.8, 10.0), (10.1, 10.5, 10.0, 10.4), (10.4, 10.9, 10.3, 10.8), (10.0, 10.1, 8.8, 9.1), (9.2, 9.6, 9.0, 9.5)]
    d = _dati(righe)
    giorno = [x.strftime("%Y-%m-%d") for x in d.index]
    usc = {"PROVA.MI": {r: pd.Series(False, index=d.index) for r in ("rottura", "ritracciamento", "ripartenza")}}

    def con(data_segnale):
        st = _strumento(data_segnale)
        return [st]

    r = rg.aggiorna(None, con(giorno[0]), {"PROVA.MI": d.iloc[:2]}, usc, PAR, "t1")
    assert r["segnali"][0]["stato"] == "aperto"
    r = rg.aggiorna(r, con(giorno[2]), {"PROVA.MI": d.iloc[:3]}, usc, PAR, "t2")
    assert len(r["segnali"]) == 1  # B cade mentre A è aperta: non si registra
    r = rg.aggiorna(r, con(giorno[3]), {"PROVA.MI": d.iloc[:4]}, usc, PAR, "t3")
    ids = {s["id"]: s for s in r["segnali"]}
    assert ids[f"{giorno[0]}-PROVA.MI-rottura"]["stato"] == "chiuso"
    assert f"{giorno[3]}-PROVA.MI-rottura" in ids  # C nel giorno dell'uscita: ammesso, come nel backtest

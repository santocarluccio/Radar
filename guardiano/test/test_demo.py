"""Un'esecuzione demo completa rispetta il contratto dati (sezione 12)."""
import json

from guardiano.motore import esegui

CHIAVI_STRUMENTO = {"id", "tipo", "nome", "mercato", "valuta", "data", "prezzo", "var_pct", "indicatori", "tendenza",
                    "punteggio", "componenti_punteggio", "stato", "frenato_dal_clima", "segnali_attivi",
                    "avvisi_uscita", "livelli", "qualita"}
CHIAVI_INDICATORI = {"sma20", "sma50", "sma200", "rsi14", "rsi2", "atr14", "atr_pct", "max52", "min52",
                     "dist_max52_pct", "volume_rapporto", "volatilita_ann_pct", "drawdown_pct", "momentum_6m_pct",
                     "momentum_12_1_pct", "forza_relativa_3m_pct", "percentile_momentum"}
FILE = ["stato.json", "azioni.json", "crypto.json", "etf.json", "etf_mensili.json", "clima.json",
        "affidabilita.json", "registro_segnali.json", "ultimo_log.txt"] + \
       [f"serie_{m}.json" for m in ("IT", "EU", "US", "CRYPTO", "ETF")] + \
       [f"candidati_{m}.json" for m in ("IT", "EU", "US", "CRYPTO")]


def _leggi(cartella, nome):
    return json.loads((cartella / nome).read_text(encoding="utf-8"))


def test_esecuzione_demo_completa(tmp_path):
    args = ["--demo", "--cartella-dati", str(tmp_path), "--limite", "6", "--data-demo", "2026-11-13"]
    assert esegui.main(args) == 0
    for nome in FILE:
        assert (tmp_path / nome).exists(), nome
    stato = _leggi(tmp_path, "stato.json")
    assert stato["modalita"] == "demo" and stato["conteggi"]["azioni"] == 18 and stato["conteggi"]["crypto"] == 6
    assert set(stato["ultima_seduta"]) == {"IT", "EU", "US", "CRYPTO"}
    az = _leggi(tmp_path, "azioni.json")["strumenti"]
    assert az and all(CHIAVI_STRUMENTO <= set(o) for o in az)
    assert all(CHIAVI_INDICATORI == set(o["indicatori"]) for o in az)
    assert all(o["stato"] in {"COMPRA", "OSSERVA", "ESCI", "DEBOLE", "NEUTRO"} for o in az)
    assert all(0 <= o["punteggio"] <= 100 and o["punteggio"] == sum(o["componenti_punteggio"].values()) for o in az)
    cr = _leggi(tmp_path, "crypto.json")["strumenti"]
    assert all(o["mercato"] == "CRYPTO" and "categoria" in o and "su_revolut_x" in o for o in cr)
    etf = _leggi(tmp_path, "etf.json")["strumenti"]
    assert etf and all({"rendimenti_pct", "pac_simulato", "max_drawdown_pct", "anni_storico"} <= set(e) for e in etf)
    clima = _leggi(tmp_path, "clima.json")
    assert {m["mercato"] for m in clima["mercati"]} == {"IT", "EU", "US", "CRYPTO"}
    assert all(m["stato"] in {"favorevole", "incerto", "sfavorevole"} for m in clima["mercati"])
    aff = _leggi(tmp_path, "affidabilita.json")
    assert {r["regola"] for r in aff["regole"]} == {"rottura", "ritracciamento", "ripartenza"}
    assert len(aff["avvertenze"]) == 4
    cand = _leggi(tmp_path, "candidati_IT.json")
    assert set(cand) >= {"mercato", "clima", "acquisto", "osservati", "uscita", "affidabilita"}
    serie = _leggi(tmp_path, "serie_IT.json")
    uno = next(iter(serie.values()))
    assert len(uno["date"]) == len(uno["chiusura"]) == 260
    # seconda esecuzione: il registro si ricarica senza errori e senza doppioni
    assert esegui.main(args) == 0
    reg = _leggi(tmp_path, "registro_segnali.json")
    ids = [s["id"] for s in reg["segnali"]]
    assert len(ids) == len(set(ids))


def test_titoli_in_ritardo():
    import pandas as pd
    giorni = pd.bdate_range("2026-11-10", periods=5)
    serie = {"FTSEMIB.MI": pd.DataFrame({"chiusura": 1.0}, index=giorni),
             "ENI.MI": pd.DataFrame({"chiusura": 1.0}, index=giorni[:-1]),
             "ISP.MI": pd.DataFrame({"chiusura": 1.0}, index=giorni),
             "VWCE.DE": pd.DataFrame({"chiusura": 1.0}, index=giorni[:-1])}
    strumenti = [{"id": "ENI.MI", "tipo": "azione", "meta": {"mercato": "IT"}},
                 {"id": "ISP.MI", "tipo": "azione", "meta": {"mercato": "IT"}},
                 {"id": "VWCE.DE", "tipo": "etf", "meta": {}}]
    # l'ETF si confronta con l'Euro Stoxx 50, qui assente: nessun confronto possibile
    assert [s["id"] for s in esegui.in_ritardo(serie, strumenti)] == ["ENI.MI"]

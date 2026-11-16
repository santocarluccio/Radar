"""Registro dei segnali emessi: misura in avanti con le stesse regole del backtest (sezione 10).

Lo stato è persistente: prezzo d'ingresso, stop e barre già valutate restano congelati, così
le rettifiche dei prezzi storici (dividendi) non riscrivono il passato. Si valutano solo le
barre successive all'ultima già considerata.
"""
from __future__ import annotations

import pandas as pd


def _rend(prezzo: float | None, ingresso: float | None) -> float | None:
    if prezzo is None or not ingresso:
        return None
    return (prezzo / ingresso - 1.0) * 100.0


def nuovo_segnale(strumento: dict, segnale: dict) -> dict:
    return {
        "id": f"{segnale['data']}-{strumento['id']}-{segnale['regola']}",
        "data": segnale["data"], "strumento": strumento["id"], "nome": strumento["nome"],
        "mercato": strumento["mercato"], "tipo": strumento["tipo"], "regola": segnale["regola"],
        "prezzo_segnale": segnale["prezzo_segnale"], "prezzo_ingresso": None,
        "stop_iniziale": segnale["stop"], "stato": "in attesa",
        "data_ingresso": None, "data_chiusura": None, "prezzo_chiusura": None, "motivo_chiusura": None,
        "ultimo_prezzo": segnale["prezzo_segnale"], "rendimento_pct": None, "rendimento_netto_pct": None,
        "barre": 0, "ultima_data_valutata": segnale["data"], "uscita_in_sospeso": False,
    }


def _chiudi(s: dict, data: str, prezzo: float, motivo: str) -> None:
    s["stato"] = "chiuso"
    s["data_chiusura"] = data
    s["prezzo_chiusura"] = prezzo
    s["motivo_chiusura"] = motivo
    s["uscita_in_sospeso"] = False


def avanza(s: dict, d: pd.DataFrame, uscita: pd.Series, costo_pct: float, max_barre: int | None) -> None:
    """Applica le barre di `d` successive a `ultima_data_valutata` a un segnale non chiuso."""
    if s["stato"] == "chiuso":
        return
    ultima = pd.Timestamp(s["ultima_data_valutata"])
    nuove = d.index[d.index > ultima]
    for data in nuove:
        riga = d.loc[data]
        o, l, c = float(riga["apertura"]), float(riga["minimo"]), float(riga["chiusura"])
        giorno = data.strftime("%Y-%m-%d")
        stop = float(s["stop_iniziale"])
        s["ultima_data_valutata"] = giorno
        s["ultimo_prezzo"] = c
        if s["stato"] == "in attesa":
            s["prezzo_ingresso"] = o
            s["data_ingresso"] = giorno
            if o <= stop:
                _chiudi(s, giorno, o, "annullato")
                break
            s["stato"] = "aperto"
            s["barre"] = 1
            if l <= stop:
                _chiudi(s, giorno, stop, "stop")
                break
        else:
            if s["uscita_in_sospeso"]:
                _chiudi(s, giorno, o, "regola")
                break
            if o <= stop:
                _chiudi(s, giorno, o, "stop")
                break
            if l <= stop:
                _chiudi(s, giorno, stop, "stop")
                break
            s["barre"] += 1
        cond = bool(uscita.get(data, False))
        s["uscita_in_sospeso"] = cond or (max_barre is not None and s["barre"] >= max_barre)
    # rendimenti aggiornati
    if s["stato"] == "chiuso" and s["motivo_chiusura"] != "annullato":
        lordo = _rend(s["prezzo_chiusura"], s["prezzo_ingresso"])
    elif s["stato"] == "aperto":
        lordo = _rend(s["ultimo_prezzo"], s["prezzo_ingresso"])
    else:
        lordo = None
    s["rendimento_pct"] = lordo
    s["rendimento_netto_pct"] = None if lordo is None else lordo - 2.0 * costo_pct


def riepilogo(segnali: list[dict]) -> dict:
    chiusi = [s for s in segnali if s["stato"] == "chiuso" and s["motivo_chiusura"] != "annullato"]
    netti = [s["rendimento_netto_pct"] for s in chiusi if s["rendimento_netto_pct"] is not None]
    return {
        "in_attesa": sum(1 for s in segnali if s["stato"] == "in attesa"),
        "aperti": sum(1 for s in segnali if s["stato"] == "aperto"),
        "chiusi": len(chiusi),
        "annullati": sum(1 for s in segnali if s["stato"] == "chiuso" and s["motivo_chiusura"] == "annullato"),
        "vincenti_pct": (100.0 * sum(1 for x in netti if x > 0) / len(netti)) if netti else None,
        "rendimento_medio_netto_pct": (sum(netti) / len(netti)) if netti else None,
    }


def aggiorna(precedente: dict | None, strumenti: list[dict], dati: dict, uscite: dict,
             par: dict, adesso_iso: str) -> dict:
    """`strumenti`: oggetti strumento esportati (con stato e segnali_attivi);
    `dati[id]`: serie con indicatori; `uscite[id][regola]`: condizione d'uscita alla chiusura."""
    segnali = list((precedente or {}).get("segnali", []))
    noti = {s["id"] for s in segnali}
    k = par["validita_segnale_barre"]
    for st in strumenti:
        if st.get("stato") != "COMPRA":
            continue
        for sg in st.get("segnali_attivi", []):
            if sg["giorni_fa"] > k - 1:
                continue
            nuovo = nuovo_segnale(st, sg)
            if nuovo["id"] not in noti:
                segnali.append(nuovo)
                noti.add(nuovo["id"])
    for s in segnali:
        if s["stato"] == "chiuso" or s["strumento"] not in dati:
            continue
        tipo = s.get("tipo", "azione")
        costo = par["costi_per_lato_pct"].get(tipo, par["costi_per_lato_pct"]["azione"])
        max_b = par["regole"]["ritracciamento"]["max_barre"] if s["regola"] == "ritracciamento" else None
        avanza(s, dati[s["strumento"]], uscite[s["strumento"]][s["regola"]], costo, max_b)
    segnali.sort(key=lambda s: (s["data"], s["strumento"], s["regola"]), reverse=True)
    return {"aggiornato_il": adesso_iso, "segnali": segnali, "riepilogo": riepilogo(segnali)}

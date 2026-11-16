"""Regole d'ingresso, avvisi di uscita, punteggio e stato (sezioni 6 e 7).

Convenzione sui conteggi: `giorni_fa` = 0 è l'ultima barra; «nelle ultime k barre»
significa giorni_fa da 0 a k−1.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

NOMI_REGOLE = {
    "rottura": "Rottura dei massimi",
    "ritracciamento": "Ritracciamento in tendenza",
    "ripartenza": "Ripartenza del trend",
}
NOMI_AVVISI = {
    "persa_media_200": "Persa la media a 200 giorni",
    "rottura_supporto": "Rottura del supporto a 20 giorni",
    "incrocio_ribassista": "Incrocio ribassista delle medie",
    "ipercomprato": "Rialzo molto esteso",
}
REGOLE = list(NOMI_REGOLE)
AVVISI = list(NOMI_AVVISI)


def _vero(s: pd.Series) -> pd.Series:
    """Booleano senza NaN (i confronti con NaN valgono falso)."""
    return s.fillna(False).astype(bool)


def ingressi(d: pd.DataFrame, par: dict, tipo: str) -> dict[str, pd.Series]:
    """Serie booleane delle tre regole d'ingresso, valutate alla chiusura di ogni barra."""
    c, sma50, sma200 = d["chiusura"], d["sma50"], d["sma200"]
    r = par["regole"]
    # Rottura dei massimi
    mx = d["max_prec_55"]
    rott = (c > mx) & (c.shift(1) <= mx.shift(1)) & (c > sma200)
    if r["rottura"]["usa_volume"].get(tipo, False):
        rott &= d["volume"] >= r["rottura"]["volume_min_rapporto"] * d["volume_media20"]
    # Ritracciamento in tendenza
    rr = r["ritracciamento"]
    rsi_r = d["rsi2"]
    ritr = (c > sma200) & (sma50 > sma200) & (rsi_r < rr["rsi_ingresso"]) & (rsi_r.shift(1) >= rr["rsi_ingresso"])
    # Ripartenza del trend
    rp = r["ripartenza"]
    sotto = (c < sma200).astype(float).where(sma200.notna())
    conteggio_sotto = sotto.shift(1).rolling(rp["barre_osservate"], min_periods=rp["barre_osservate"]).sum()
    rip = ((c > sma200) & (c.shift(1) <= sma200.shift(1)) & (sma200 >= sma200.shift(20))
           & (conteggio_sotto >= rp["barre_sotto_min"]))
    return {"rottura": _vero(rott), "ritracciamento": _vero(ritr), "ripartenza": _vero(rip)}


def condizioni_uscita(d: pd.DataFrame, par: dict) -> dict[str, pd.Series]:
    """Condizioni d'uscita di regola valutate alla chiusura (lo stop è gestito a parte).
    Per il ritracciamento il limite di barre in posizione è applicato dal simulatore."""
    r = par["regole"]
    c = d["chiusura"]
    return {
        "rottura": _vero(c < d["min_prec_20"]),
        "ritracciamento": _vero(d["rsi2"] > r["ritracciamento"]["rsi_uscita"]),
        "ripartenza": _vero(c < d["sma200"] * (1 - r["ripartenza"]["uscita_sotto_sma200_pct"] / 100.0)),
    }


def avvisi(d: pd.DataFrame) -> dict[str, tuple[pd.Series, pd.Series]]:
    """Per ogni avviso: (serie booleana, serie della gravità)."""
    c, sma20, sma50, sma200 = d["chiusura"], d["sma20"], d["sma50"], d["sma200"]
    mn = d["min_prec_20"]
    alta = pd.Series("alta", index=d.index)
    persa = _vero((c < sma200) & (c.shift(1) >= sma200.shift(1)))
    supp = _vero((c < mn) & (c.shift(1) >= mn.shift(1)))
    grav_supp = pd.Series(np.where(_vero(c < sma200), "alta", "media"), index=d.index)
    incr = _vero((sma50 < sma200) & (sma50.shift(1) >= sma200.shift(1)))
    iperc = _vero((d["rsi14"] > 80) & (c > sma20 + 3 * d["atr14"]))
    return {
        "persa_media_200": (persa, alta),
        "rottura_supporto": (supp, grav_supp),
        "incrocio_ribassista": (incr, alta),
        "ipercomprato": (iperc, pd.Series("bassa", index=d.index)),
    }


def livello_stop(chiusura: float, atr14: float, par: dict) -> float:
    return chiusura - par["stop_atr_multiplo"] * atr14


def _num_it(x: float, dec: int = 1) -> str:
    """Numero in formato italiano (virgola decimale)."""
    return f"{x:.{dec}f}".replace(".", ",")


def descrivi_segnale(regola: str, riga: pd.Series, par: dict) -> str:
    if regola == "rottura":
        testo = f"Chiusura sopra il massimo degli ultimi {par['regole']['rottura']['finestra_massimo']} giorni"
        vr = riga.get("volume_rapporto")
        if vr is not None and not (isinstance(vr, float) and math.isnan(vr)):
            testo += f" con volumi {_num_it(float(vr))} volte la media"
        return testo + "."
    if regola == "ritracciamento":
        return (f"Discesa di breve (RSI a 2 giorni a {_num_it(float(riga['rsi2']))}) dentro una tendenza "
                "rialzista: possibile rimbalzo.")
    return "Il prezzo torna sopra la media a 200 giorni dopo almeno 20 sedute sotto, con la media in salita."


def descrivi_avviso(avviso: str, riga: pd.Series) -> str:
    if avviso == "persa_media_200":
        return "Chiusura sotto la media a 200 giorni: la tendenza di fondo si indebolisce."
    if avviso == "rottura_supporto":
        return "Chiusura sotto il minimo degli ultimi 20 giorni."
    if avviso == "incrocio_ribassista":
        return "La media a 50 giorni scende sotto quella a 200 giorni."
    return (f"RSI a 14 giorni a {_num_it(float(riga['rsi14']))} e prezzo molto sopra la media a 20 giorni: "
            "rialzo esteso, possibile pausa.")


def _r(x, dec=4):
    if x is None:
        return None
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(xf) or math.isinf(xf):
        return None
    return xf


def segnali_recenti(d: pd.DataFrame, ing: dict[str, pd.Series], par: dict, finestra: int = 10) -> list[dict]:
    """Il segnale d'ingresso più recente di ogni regola nelle ultime `finestra` barre."""
    n = len(d)
    out = []
    for regola in REGOLE:
        s = ing[regola].to_numpy()
        pos = np.flatnonzero(s[max(0, n - finestra):]) + max(0, n - finestra)
        if not len(pos):
            continue
        t = int(pos[-1])
        riga = d.iloc[t]
        c = float(riga["chiusura"])
        atr14 = float(riga["atr14"])
        stop = livello_stop(c, atr14, par)
        obiettivo = c + par["obiettivo_multiplo_rischio"] * (c - stop)
        out.append({
            "regola": regola, "nome": NOMI_REGOLE[regola],
            "data": d.index[t].strftime("%Y-%m-%d"), "giorni_fa": n - 1 - t,
            "prezzo_segnale": c, "stop": stop, "obiettivo": obiettivo,
            "rischio_pct": (c - stop) / c * 100.0,
            "descrizione": descrivi_segnale(regola, riga, par),
        })
    out.sort(key=lambda x: x["giorni_fa"])
    return out


def avvisi_recenti(d: pd.DataFrame, av: dict, finestra: int = 5) -> list[dict]:
    """L'occorrenza più recente di ogni avviso nelle ultime `finestra` barre."""
    n = len(d)
    out = []
    for nome in AVVISI:
        serie, grav = av[nome]
        s = serie.to_numpy()
        pos = np.flatnonzero(s[max(0, n - finestra):]) + max(0, n - finestra)
        if not len(pos):
            continue
        t = int(pos[-1])
        out.append({
            "regola": nome, "nome": NOMI_AVVISI[nome], "gravita": str(grav.iloc[t]),
            "data": d.index[t].strftime("%Y-%m-%d"), "giorni_fa": n - 1 - t,
            "descrizione": descrivi_avviso(nome, d.iloc[t]),
        })
    out.sort(key=lambda x: x["giorni_fa"])
    return out


def componenti_punteggio(ultima: pd.Series, pct_mom6: float | None, pct_mom12: float | None,
                         vol_quintile_alto: bool, segnali: list[dict], tipo: str, par: dict) -> dict:
    """Le cinque componenti del punteggio (sezione 7), arrotondate all'intero."""
    c, s50, s200 = ultima["chiusura"], ultima["sma50"], ultima["sma200"]
    tend = 0.0
    if pd.notna(s200) and c > s200:
        tend += 15
    if pd.notna(s200) and pd.notna(s50) and s50 > s200:
        tend += 10
    if pd.notna(ultima.get("sma200_20fa")) and pd.notna(s200) and s200 > ultima["sma200_20fa"]:
        tend += 5
    if pd.notna(s50) and c > s50:
        tend += 10
    mom = 0.15 * (pct_mom6 if pct_mom6 is not None else 0.0) + 0.10 * (pct_mom12 if pct_mom12 is not None else 0.0)
    fr = ultima.get("forza_relativa_3m_pct")
    forza = 0.0 if fr is None or pd.isna(fr) else 10.0 * min(1.0, max(0.0, (float(fr) + 10.0) / 20.0))
    setup = 0.0
    if segnali:
        g = min(s["giorni_fa"] for s in segnali)
        if g <= par["validita_segnale_barre"] - 1:
            setup = 15.0
        elif g <= 9:
            setup = 8.0
    rischio = 10.0
    if vol_quintile_alto:
        rischio -= 4
    dd = ultima.get("drawdown_pct")
    if dd is not None and pd.notna(dd) and dd < -25:
        rischio -= 3
    soglia_atr = 10.0 if tipo == "crypto" else 5.0
    ap = ultima.get("atr_pct")
    if ap is not None and pd.notna(ap) and ap > soglia_atr:
        rischio -= 3
    rischio = max(0.0, rischio)
    comp = {"tendenza": tend, "momentum": mom, "forza_relativa": forza, "setup": setup, "rischio": rischio}
    return {k: int(round(v)) for k, v in comp.items()}


def stato(punteggio: int, segnali: list[dict], avvisi_r: list[dict], clima: str, par: dict) -> tuple[str, bool]:
    """Stato in ordine di precedenza: ESCI, COMPRA, OSSERVA, DEBOLE, NEUTRO.
    Restituisce (stato, frenato_dal_clima)."""
    k = par["validita_segnale_barre"]
    if any(a["gravita"] == "alta" and a["giorni_fa"] <= k - 1 for a in avvisi_r):
        return "ESCI", False
    recente = any(s["giorni_fa"] <= k - 1 for s in segnali)
    s = par["soglie"]
    if recente and punteggio >= s["compra"] and clima != "sfavorevole":
        return "COMPRA", False
    if recente and clima == "sfavorevole":
        return "OSSERVA", True
    if punteggio >= s["osserva"]:
        return "OSSERVA", False
    if punteggio < s["debole"]:
        return "DEBOLE", False
    return "NEUTRO", False

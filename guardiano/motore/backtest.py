"""Verifica storica delle regole (sezione 9).

Il simulatore riceve serie già calcolate e applica sempre le stesse regole:
segnale alla chiusura di t, ingresso all'apertura di t+1, stop fisso iniziale,
uscita di regola all'apertura successiva alla barra in cui scatta la condizione.
"""
from __future__ import annotations

import math
from statistics import median

import numpy as np
import pandas as pd

AVVERTENZE = [
    "L'universo è composto dai titoli di oggi: quelli falliti o usciti dalla Borsa mancano, e questo rende i risultati migliori del vero (distorsione da sopravvivenza).",
    "Lo storico copre circa 5 anni: un solo ciclo di mercato o poco più.",
    "Commissioni, spread e slittamento sono stimati, non misurati.",
    "Il passato non garantisce il futuro: una regola che ha funzionato può smettere di funzionare.",
]


def simula(date: pd.DatetimeIndex, O: np.ndarray, H: np.ndarray, L: np.ndarray, C: np.ndarray,
           ingresso: np.ndarray, uscita: np.ndarray, stop_arr: np.ndarray, costo_pct: float,
           inizio: int = 0, max_barre: int | None = None) -> tuple[list[dict], int, int]:
    """Simula una regola su uno strumento. Restituisce (operazioni chiuse, aperte, annullate).

    Barra d'ingresso: se il minimo tocca lo stop si esce allo stop. Barre successive: se
    l'apertura è sotto lo stop si esce all'apertura; altrimenti se il minimo tocca lo stop
    si esce allo stop; altrimenti, se alla chiusura vale la condizione d'uscita (o sono
    passate `max_barre` barre), si esce all'apertura successiva, o alla chiusura se è
    l'ultima barra. Dopo un'uscita alla barra x si valutano di nuovo i segnali da x in poi.
    """
    n = len(C)
    operazioni: list[dict] = []
    annullate = 0
    i = max(int(inizio), 0)
    in_pos = False
    stop = prezzo_in = 0.0
    bar_in = barre = 0
    in_sospeso = False

    def chiudi(x: int, prezzo: float, motivo: str) -> None:
        lordo = (prezzo / prezzo_in - 1.0) * 100.0
        operazioni.append({
            "data_ingresso": date[bar_in], "data_uscita": date[x],
            "prezzo_ingresso": prezzo_in, "prezzo_uscita": prezzo,
            "lordo_pct": lordo, "netto_pct": lordo - 2.0 * costo_pct,
            "giorni": int((date[x] - date[bar_in]).days), "barre": x - bar_in + 1, "motivo": motivo,
        })

    while i < n:
        if not in_pos:
            if ingresso[i] and i + 1 < n and not math.isnan(stop_arr[i]):
                stop = float(stop_arr[i])
                e = i + 1
                if O[e] <= stop:
                    annullate += 1
                    i = e
                    continue
                prezzo_in, bar_in, barre = float(O[e]), e, 1
                if L[e] <= stop:
                    chiudi(e, stop, "stop")
                    i = e  # dopo l'uscita si valuta il segnale alla chiusura della stessa barra
                    continue
                in_pos = True
                in_sospeso = bool(uscita[e]) or (max_barre is not None and barre >= max_barre)
                if in_sospeso and e == n - 1:
                    chiudi(e, float(C[e]), "regola")
                    in_pos = False
                i = e + 1
                continue
            i += 1
            continue
        # in posizione, barra i
        if in_sospeso:
            chiudi(i, float(O[i]), "regola")
            in_pos = False
            continue  # valuta il segnale alla chiusura di questa barra
        if O[i] <= stop:
            chiudi(i, float(O[i]), "stop")
            in_pos = False
            continue
        if L[i] <= stop:
            chiudi(i, stop, "stop")
            in_pos = False
            continue
        barre += 1
        in_sospeso = bool(uscita[i]) or (max_barre is not None and barre >= max_barre)
        if in_sospeso and i == n - 1:
            chiudi(i, float(C[i]), "regola")
            in_pos = False
        i += 1
    return operazioni, (1 if in_pos else 0), annullate


def _media(x: list[float]) -> float | None:
    return float(np.mean(x)) if x else None


def statistiche(ops: list[dict], aperte: int, dal: pd.Timestamp | None, al: pd.Timestamp | None,
                indice_periodo_pct: float | None, min_operazioni: int) -> dict:
    n = len(ops)
    netti = [o["netto_pct"] for o in ops]
    vinc = [x for x in netti if x > 0]
    perd = [x for x in netti if x <= 0]
    ordinate = sorted(ops, key=lambda o: (o["data_uscita"], o["data_ingresso"]))
    serie = peggiore = 0
    for o in ordinate:
        serie = serie + 1 if o["netto_pct"] <= 0 else 0
        peggiore = max(peggiore, serie)
    somma_perd = abs(sum(perd))
    fp = (sum(vinc) / somma_perd) if somma_perd > 0 else None
    if dal is not None and al is not None:
        meta = dal + (al - dal) / 2
    else:
        meta = None
    prima = [o["netto_pct"] for o in ops if meta is not None and o["data_ingresso"] < meta]
    seconda = [o["netto_pct"] for o in ops if meta is not None and o["data_ingresso"] >= meta]
    media = _media(netti)
    m1, m2 = _media(prima), _media(seconda)
    if n < min_operazioni:
        giudizio = "dati insufficienti"
    elif media is not None and media > 0.5 and (m1 or 0) > 0 and (m2 or 0) > 0:
        giudizio = "positiva"
    elif media is not None and media > 0:
        giudizio = "debole"
    else:
        giudizio = "negativa"
    return {
        "operazioni": n, "aperte": aperte,
        "vincenti_pct": (100.0 * len(vinc) / n) if n else None,
        "guadagno_medio_pct": _media(vinc), "perdita_media_pct": _media(perd),
        "rendimento_medio_netto_pct": media,
        "mediana_giorni": (median(o["giorni"] for o in ops) if ops else None),
        "fattore_profitto": fp, "peggior_serie_perdite": peggiore,
        "prima_meta": {"operazioni": len(prima), "rendimento_medio_netto_pct": m1},
        "seconda_meta": {"operazioni": len(seconda), "rendimento_medio_netto_pct": m2},
        "indice_periodo_pct": indice_periodo_pct, "giudizio": giudizio,
    }


def coorte_forza_relativa(chiusure: pd.DataFrame, dal: pd.Timestamp, quota: float = 0.2,
                          min_strumenti: int = 10) -> dict:
    """A ogni fine mese: rendimento a 21 barre del quintile con il momentum a 6 mesi più alto
    meno la media del mercato. La selezione usa solo dati passati; il rendimento successivo
    serve solo a misurare."""
    if chiusure.shape[1] < min_strumenti:
        return {"mesi": 0, "eccesso_medio_mensile_pct": None, "mesi_positivi_pct": None}
    ch = chiusure.sort_index().ffill(limit=5)
    mom = ch.shift(5) / ch.shift(131) - 1.0
    avanti = ch.shift(-21) / ch - 1.0
    idx = ch.index
    fine_mese = [idx[k] for k in range(len(idx) - 1) if idx[k].month != idx[k + 1].month and idx[k] >= dal]
    eccessi = []
    for d in fine_mese:
        m, f = mom.loc[d], avanti.loc[d]
        validi = m.notna() & f.notna()
        if validi.sum() < min_strumenti:
            continue
        soglia = m[validi].quantile(1.0 - quota)
        alto = validi & (m >= soglia)
        eccessi.append(float(f[alto].mean() - f[validi].mean()))
    if not eccessi:
        return {"mesi": 0, "eccesso_medio_mensile_pct": None, "mesi_positivi_pct": None}
    return {
        "mesi": len(eccessi),
        "eccesso_medio_mensile_pct": 100.0 * float(np.mean(eccessi)),
        "mesi_positivi_pct": 100.0 * sum(1 for e in eccessi if e > 0) / len(eccessi),
    }

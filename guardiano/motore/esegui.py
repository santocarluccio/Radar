"""Ingresso da riga di comando del motore.

python -m guardiano.motore.esegui [--demo] [--cartella-config PERCORSO] [--cartella-dati PERCORSO]
                                  [--solo azioni|etf|crypto] [--limite N]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
import traceback
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from . import VERSIONE
from . import backtest as bt
from . import clima as cl
from . import demo
from . import esporta
from . import fonti
from . import indicatori as ind
from . import pac
from . import registro as rg
from . import segnali as sg

ROMA = ZoneInfo("Europe/Rome")
RADICE = Path(__file__).resolve().parents[1]
MERCATI = ["IT", "EU", "US", "CRYPTO"]
INDICE_PRINCIPALE = {"IT": "FTSEMIB.MI", "EU": "^STOXX50E", "US": "^GSPC"}
ID_BTC = "BTC-EUR"


class Diario:
    """Raccoglie le righe di log e le stampa subito (il flusso le salva)."""

    def __init__(self) -> None:
        self.righe: list[str] = []

    def __call__(self, testo: str) -> None:
        riga = f"{dt.datetime.now(ROMA).strftime('%H:%M:%S')} {testo}"
        self.righe.append(riga)
        print(riga, flush=True)


# ---------------------------------------------------------------- configurazione

def carica_config(cartella: Path) -> tuple[dict, dict, dict, dict]:
    def leggi(nome):
        with open(cartella / nome, encoding="utf-8") as f:
            return json.load(f)
    return (leggi("universo_azioni.json"), leggi("universo_etf.json"),
            leggi("universo_crypto.json"), leggi("parametri.json"))


def elenco_strumenti(az: dict, etf: dict, cr: dict, solo: str | None, limite: int | None) -> list[dict]:
    """Elenco unico degli strumenti da scaricare, con i metadati."""
    out: list[dict] = []
    if solo in (None, "azioni"):
        per_mercato: dict[str, int] = {}
        for t in az["titoli"]:
            m = t["mercato"]
            if limite and per_mercato.get(m, 0) >= limite:
                continue
            per_mercato[m] = per_mercato.get(m, 0) + 1
            out.append({"id": t["ticker_yahoo"], "ticker": t["ticker_yahoo"], "tipo": "azione", "meta": t})
    if solo in (None, "etf"):
        for k, e in enumerate(etf["etf"]):
            if limite and k >= limite:
                break
            out.append({"id": e["ticker_yahoo"], "ticker": e["ticker_yahoo"], "tipo": "etf", "meta": e})
    if solo in (None, "crypto"):
        lista = cr["crypto"]
        if limite:
            lista = [c for c in lista if c["simbolo"] == "BTC"] + [c for c in lista if c["simbolo"] != "BTC"][:max(0, limite - 1)]
        for c in lista:
            out.append({"id": f"{c['simbolo']}-EUR", "ticker": c["yahoo"], "tipo": "crypto", "meta": c})
    for i in az["indici_riferimento"]:
        tipo = "vix" if i["ticker_yahoo"] == "^VIX" else ("cambio" if i["ticker_yahoo"] == "EURUSD=X" else "indice")
        out.append({"id": i["ticker_yahoo"], "ticker": i["ticker_yahoo"], "tipo": tipo, "meta": i})
    return out


# ---------------------------------------------------------------- scarico

def riferimento(s: dict) -> str | None:
    """Indice con cui confrontare la data dell'ultima barra di azioni ed ETF."""
    if s["tipo"] == "etf":
        return "^STOXX50E"
    if s["tipo"] == "azione":
        return INDICE_PRINCIPALE.get(s["meta"].get("mercato"))
    return None


def in_ritardo(serie: dict, strumenti: list[dict]) -> list[dict]:
    """Azioni ed ETF la cui ultima barra è più vecchia di quella del loro indice."""
    out = []
    for s in strumenti:
        r = riferimento(s)
        if r and s["id"] in serie and r in serie and len(serie[s["id"]]) and len(serie[r]):
            if serie[s["id"]].index[-1] < serie[r].index[-1]:
                out.append(s)
    return out


def scarica(strumenti: list[dict], modalita_demo: bool, adesso_utc: dt.datetime, par: dict,
            log: Diario, data_demo: dt.date | None) -> tuple[dict, list[dict], dict]:
    """Restituisce (serie per id, problemi di scarico, fonti usate)."""
    serie: dict[str, pd.DataFrame] = {}
    problemi: list[dict] = []
    fonti_usate = {"kraken": [], "kraken_completamento": [], "orari": []}
    if modalita_demo:
        fine = data_demo or adesso_utc.date()
        for s in strumenti:
            tipo = s["tipo"]
            anni = 8 if tipo == "etf" else par["storico_anni"]
            fine_s = fine if tipo == "crypto" else pd.bdate_range(end=pd.Timestamp(fine), periods=1)[0].date()
            serie[s["id"]] = fonti.pulisci(demo.serie(s["ticker"] or s["id"], tipo, fine_s, anni))
        return serie, problemi, fonti_usate
    anni = par["storico_anni"]
    gruppi = {
        f"{anni}y": [s for s in strumenti if s["tipo"] != "etf" and s["ticker"]],
        "max": [s for s in strumenti if s["tipo"] == "etf"],
    }
    for periodo, lista in gruppi.items():
        if not lista:
            continue
        log(f"Scarico da Yahoo {len(lista)} strumenti (periodo {periodo})")
        ottenute, errori = fonti.scarica_yahoo([s["ticker"] for s in lista], periodo, log)
        log(f"  ricevuti {len(ottenute)} su {len(lista)}; falliti: {', '.join(sorted(errori)) or 'nessuno'}")
        for s in lista:
            if s["ticker"] in ottenute:
                serie[s["id"]] = ottenute[s["ticker"]]
    # azioni ed ETF senza l'ultima seduta del loro indice: secondo tentativo su un periodo breve
    indietro = in_ritardo(serie, strumenti)
    if indietro:
        log(f"  {len(indietro)} titoli senza l'ultima seduta del loro indice: secondo tentativo su un mese")
        ottenute, _ = fonti.scarica_yahoo([s["ticker"] for s in indietro], "1mo", log, attese=())
        recuperati = 0
        for s in indietro:
            nuovo = ottenute.get(s["ticker"])
            if nuovo is None or not len(nuovo):
                continue
            vecchio = serie[s["id"]]
            aggiunte = nuovo[nuovo.index > vecchio.index[-1]]
            if len(aggiunte):
                serie[s["id"]] = pd.concat([vecchio, aggiunte])
                recuperati += 1
        log(f"  recuperati {recuperati} su {len(indietro)}")
        ancora = in_ritardo(serie, strumenti)
        if ancora:
            dopo = {s["ticker"]: serie[s["id"]].index[-1] for s in ancora}
            fino = {s["ticker"]: serie[riferimento(s)].index[-1] for s in ancora}
            ricostruite = fonti.ricostruisci_da_orari([s["ticker"] for s in ancora], dopo, fino, log)
            for s in ancora:
                nuove = ricostruite.get(s["ticker"])
                if nuove is not None and len(nuove):
                    serie[s["id"]] = pd.concat([serie[s["id"]], nuove])
                    fonti_usate["orari"].append(s["id"])
            log(f"  ricostruite dai dati orari le sedute mancanti di {len(fonti_usate['orari'])} titoli su {len(ancora)}")
    # Kraken: ripiego per le crypto senza dati Yahoo sufficienti e completamento delle ultime barre,
    # perché di notte Yahoo può non avere ancora la barra giornaliera del giorno prima
    prima = True
    for s in strumenti:
        coppia = s["meta"].get("kraken_pair_eur") if s["tipo"] == "crypto" else None
        if not coppia:
            continue
        if not prima:
            time.sleep(1.1)  # limite di richieste dell'API pubblica di Kraken
        prima = False
        df = serie.get(s["id"])
        try:
            kr = fonti.scarica_kraken(coppia)
        except Exception as e:
            log(f"  {s['id']}: Kraken non disponibile ({type(e).__name__}: {e})"[:200])
            continue
        if not len(kr):
            continue
        if df is None or len(df) < 250:
            if df is None or len(kr) > len(df):
                serie[s["id"]] = kr
                fonti_usate["kraken"].append(s["id"])
                log(f"  {s['id']}: dati da Kraken ({len(kr)} barre)")
        else:
            # giorni recenti presenti su Kraken ma assenti da Yahoo (anche in mezzo, non solo in coda)
            recenti = kr[kr.index >= df.index[-1] - pd.Timedelta(days=10)]
            mancanti = recenti[~recenti.index.isin(df.index)]
            if len(mancanti):
                serie[s["id"]] = pd.concat([df, mancanti]).sort_index()
                fonti_usate["kraken_completamento"].append(s["id"])
    if fonti_usate["kraken_completamento"]:
        log(f"  ultime barre completate con Kraken per {len(fonti_usate['kraken_completamento'])} crypto")
    for s in strumenti:
        if s["id"] not in serie:
            problemi.append({"strumento": s["id"], "motivo": "nessun dato"})
    return serie, problemi, fonti_usate


# ---------------------------------------------------------------- costruzione degli oggetti

def _f(x):
    """Valore float o None."""
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(v) or np.isinf(v) else v


def percentili(valori: dict[str, float | None]) -> dict[str, float | None]:
    s = pd.Series({k: v for k, v in valori.items() if v is not None}, dtype=float)
    if not len(s):
        return {k: None for k in valori}
    r = s.rank(pct=True) * 100.0
    return {k: (float(r[k]) if k in r.index else None) for k in valori}


def oggetto_strumento(s: dict, d: pd.DataFrame, segnali: list[dict], avvisi: list[dict], comp: dict,
                      punteggio: int, stato: str, frenato: bool, pct_mom: float | None, par: dict,
                      qualita: str) -> dict:
    u = d.iloc[-1]
    m = s["meta"]
    c = float(u["chiusura"])
    obj = {"id": s["id"], "tipo": s["tipo"], "nome": m["nome"]}
    if s["tipo"] == "azione":
        obj.update({"isin": m.get("isin"), "mercato": m["mercato"], "settore": m["settore"], "valuta": m["valuta"]})
    else:
        obj.update({"simbolo": m["simbolo"], "mercato": "CRYPTO", "categoria": m["categoria"], "valuta": "EUR",
                    "coingecko_id": m.get("coingecko_id"),
                    "su_trade_republic": m.get("su_trade_republic"), "su_revolut_x": m.get("su_revolut_x")})
    obj.update({
        "data": d.index[-1], "prezzo": c,
        "var_pct": {k: _f(u[f"var_{k}"]) for k in ind.DISTANZE_VAR},
        "indicatori": {
            "sma20": _f(u["sma20"]), "sma50": _f(u["sma50"]), "sma200": _f(u["sma200"]),
            "rsi14": _f(u["rsi14"]), "rsi2": _f(u["rsi2"]), "atr14": _f(u["atr14"]), "atr_pct": _f(u["atr_pct"]),
            "max52": _f(u["max52"]), "min52": _f(u["min52"]), "dist_max52_pct": _f(u["dist_max52_pct"]),
            "volume_rapporto": _f(u["volume_rapporto"]), "volatilita_ann_pct": _f(u["volatilita_ann_pct"]),
            "drawdown_pct": _f(u["drawdown_pct"]), "momentum_6m_pct": _f(u["momentum_6m_pct"]),
            "momentum_12_1_pct": _f(u["momentum_12_1_pct"]), "forza_relativa_3m_pct": _f(u["forza_relativa_3m_pct"]),
            "percentile_momentum": (int(round(pct_mom)) if pct_mom is not None else None),
        },
        "tendenza": str(u["tendenza"]), "punteggio": punteggio, "componenti_punteggio": comp,
        "stato": stato, "frenato_dal_clima": frenato,
        "segnali_attivi": segnali, "avvisi_uscita": avvisi,
        "livelli": {
            "stop_suggerito": _f(sg.livello_stop(c, float(u["atr14"]), par)) if pd.notna(u["atr14"]) else None,
            "supporto_20g": _f(d["minimo"].iloc[-20:].min()) if len(d) >= 20 else None,
            "massimo_55g": _f(d["massimo"].iloc[-55:].max()) if len(d) >= 55 else None,
        },
        "qualita": qualita,
    })
    return obj


# ---------------------------------------------------------------- esecuzione

def esegui(args, log: Diario, adesso_utc: dt.datetime, generato: str) -> tuple[dict, int]:
    t0 = time.time()
    cartella_config = Path(args.cartella_config) if args.cartella_config else RADICE / "config"
    cartella_dati = Path(args.cartella_dati) if args.cartella_dati else RADICE / "dati"
    az, etf_cfg, cr_cfg, par = carica_config(cartella_config)
    strumenti = elenco_strumenti(az, etf_cfg, cr_cfg, args.solo, args.limite)
    log(f"Guardiano dei Mercati {VERSIONE} — modalità {'demo' if args.demo else 'reale'}, {len(strumenti)} strumenti")
    data_demo = dt.date.fromisoformat(args.data_demo) if args.data_demo else None
    grezze, problemi, fonti_usate = scarica(strumenti, args.demo, adesso_utc, par, log, data_demo)

    oggi = (data_demo or adesso_utc.date()) if args.demo else adesso_utc.date()
    serie: dict[str, pd.DataFrame] = {}
    qualita: dict[str, str] = {}
    per_id = {s["id"]: s for s in strumenti}
    for s in strumenti:
        df = grezze.get(s["id"])
        if df is None:
            continue
        tipo_barra = "crypto" if s["tipo"] == "crypto" else "azione"
        df = df if args.demo else fonti.scarta_barra_parziale(df, tipo_barra, adesso_utc)
        if len(df) < 60:
            problemi.append({"strumento": s["id"], "motivo": f"storico insufficiente ({len(df)} barre)"})
            continue
        serie[s["id"]] = df
        qualita[s["id"]] = fonti.qualita(df, tipo_barra, oggi)

    # azioni ed ETF ancora senza l'ultima seduta del loro indice
    ritardo = [s["id"] for s in in_ritardo(serie, strumenti)]
    for sid in ritardo:
        if qualita.get(sid) == "ok":
            qualita[sid] = "in_ritardo"

    # ---- indicatori
    finestre = dict(finestra_massimo=par["regole"]["rottura"]["finestra_massimo"],
                    finestra_supporto=par["regole"]["rottura"]["finestra_uscita"])
    calcolati: dict[str, pd.DataFrame] = {}
    for s in strumenti:
        if s["tipo"] in ("indice",) and s["id"] in serie:
            calcolati[s["id"]] = ind.calcola(serie[s["id"]], 252, None, **finestre)
    if ID_BTC in serie:
        calcolati[ID_BTC] = ind.calcola(serie[ID_BTC], par["barre_anno"]["crypto"], None, **finestre)
    for s in strumenti:
        sid = s["id"]
        if sid not in serie or sid in calcolati:
            continue
        if s["tipo"] == "azione":
            idx_id = INDICE_PRINCIPALE[s["meta"]["mercato"]]
            idx = serie[idx_id]["chiusura"] if idx_id in serie else None
            calcolati[sid] = ind.calcola(serie[sid], par["barre_anno"]["azione"], idx, **finestre)
        elif s["tipo"] == "crypto":
            idx = serie[ID_BTC]["chiusura"] if ID_BTC in serie else None
            calcolati[sid] = ind.calcola(serie[sid], par["barre_anno"]["crypto"], idx, **finestre)
        elif s["tipo"] == "etf":
            calcolati[sid] = ind.calcola(serie[sid], par["barre_anno"]["etf"], None, **finestre)
    if ID_BTC in calcolati:  # forza relativa del riferimento verso sé stesso
        calcolati[ID_BTC]["forza_relativa_3m_pct"] = 0.0

    def mercato_di(s):
        return "CRYPTO" if s["tipo"] == "crypto" else s["meta"].get("mercato")

    trading = [s for s in strumenti if s["tipo"] in ("azione", "crypto") and s["id"] in calcolati]

    # ---- clima
    mercati_clima = []
    clima_per: dict[str, dict] = {}
    for m in MERCATI:
        membri = [s for s in trading if mercato_di(s) == m]
        if not membri and m != "CRYPTO":
            continue
        if m == "CRYPTO":
            if not membri:
                continue
            id_idx, nome_idx = ID_BTC, "Bitcoin"
        else:
            id_idx = INDICE_PRINCIPALE[m]
            nome_idx = next((i["nome"] for i in az["indici_riferimento"] if i["ticker_yahoo"] == id_idx), id_idx)
        righe = [calcolati[s["id"]].iloc[-1] for s in membri if qualita.get(s["id"]) not in ("dati_vecchi", "in_ritardo")]
        c = cl.calcola_mercato(m, nome_idx, calcolati.get(id_idx), righe, par)
        mercati_clima.append(c)
        clima_per[m] = c
    vix_val = _f(serie["^VIX"]["chiusura"].iloc[-1]) if "^VIX" in serie else None
    eurusd = _f(serie["EURUSD=X"]["chiusura"].iloc[-1]) if "EURUSD=X" in serie else None
    clima_json = {"generato_il": generato, "mercati": mercati_clima,
                  "vix": {"valore": vix_val, "etichetta": cl.etichetta_vix(vix_val)}, "eurusd": eurusd}
    for c in mercati_clima:
        amp = c["ampiezza_sopra_sma200_pct"]
        log(f"Clima {c['mercato']}: {c['stato']} (sopra la media a 200 giorni: {amp:.0f}%)" if amp is not None
            else f"Clima {c['mercato']}: {c['stato']}")

    # ---- segnali, punteggio, stato
    ingressi: dict[str, dict] = {}
    uscite: dict[str, dict] = {}
    recenti: dict[str, tuple[list, list]] = {}
    for s in trading:
        d = calcolati[s["id"]]
        tipo = s["tipo"]
        ingressi[s["id"]] = sg.ingressi(d, par, tipo)
        uscite[s["id"]] = sg.condizioni_uscita(d, par)
        recenti[s["id"]] = (sg.segnali_recenti(d, ingressi[s["id"]], par, 10), sg.avvisi_recenti(d, sg.avvisi(d), 5))
    oggetti: dict[str, dict] = {}
    for m in MERCATI:
        membri = [s for s in trading if mercato_di(s) == m]
        if not membri:
            continue
        ultime = {s["id"]: calcolati[s["id"]].iloc[-1] for s in membri}
        p6 = percentili({k: _f(u["momentum_6m_pct"]) for k, u in ultime.items()})
        p12 = percentili({k: _f(u["momentum_12_1_pct"]) for k, u in ultime.items()})
        vols = pd.Series({k: _f(u["volatilita_ann_pct"]) for k, u in ultime.items()}, dtype=float).dropna()
        soglia_vol = float(vols.quantile(0.8)) if len(vols) >= 5 else None
        stato_clima = clima_per.get(m, {}).get("stato", "incerto")
        for s in membri:
            u = ultime[s["id"]]
            segn, avv = recenti[s["id"]]
            v = _f(u["volatilita_ann_pct"])
            alto = soglia_vol is not None and v is not None and v >= soglia_vol
            comp = sg.componenti_punteggio(u, p6[s["id"]], p12[s["id"]], alto, segn, s["tipo"], par)
            punteggio = int(sum(comp.values()))
            st, fren = sg.stato(punteggio, segn, avv, stato_clima, par)
            if st == "COMPRA" and qualita[s["id"]] in ("dati_vecchi", "in_ritardo"):
                st = "OSSERVA"  # un segnale su dati incompleti o fermi non è un acquisto
            oggetti[s["id"]] = oggetto_strumento(s, calcolati[s["id"]], segn, avv, comp, punteggio, st, fren,
                                                 p6[s["id"]], par, qualita[s["id"]])
    conteggio_stati = pd.Series([o["stato"] for o in oggetti.values()]).value_counts().to_dict() if oggetti else {}
    log(f"Stati: {conteggio_stati}")

    # ---- backtest
    risc = par["backtest"]["riscaldamento_barre"]
    ops: dict[tuple[str, str], list] = {}
    aperte: dict[tuple[str, str], int] = {}
    periodi: dict[str, list] = {}
    for s in trading:
        d = calcolati[s["id"]]
        if len(d) <= risc + 1:
            continue
        m = mercato_di(s)
        periodi.setdefault(m, []).append((d.index[risc], d.index[-1]))
        costo = par["costi_per_lato_pct"][s["tipo"]]
        stop_arr = (d["chiusura"] - par["stop_atr_multiplo"] * d["atr14"]).to_numpy(dtype=float)
        O, H, L, C = (d[k].to_numpy(dtype=float) for k in ("apertura", "massimo", "minimo", "chiusura"))
        for regola in sg.REGOLE:
            max_b = par["regole"]["ritracciamento"]["max_barre"] if regola == "ritracciamento" else None
            o, a, _ = bt.simula(d.index, O, H, L, C, ingressi[s["id"]][regola].to_numpy(),
                                uscite[s["id"]][regola].to_numpy(), stop_arr, costo, risc, max_b)
            for chiave in ((regola, m), (regola, "TUTTI")):
                ops.setdefault(chiave, []).extend(o)
                aperte[chiave] = aperte.get(chiave, 0) + a
    regole_stat = []
    dal_tot = min((p[0] for v in periodi.values() for p in v), default=None)
    al_tot = max((p[1] for v in periodi.values() for p in v), default=None)
    for regola in sg.REGOLE:
        for m in [x for x in MERCATI if x in periodi] + ["TUTTI"]:
            if m == "TUTTI":
                dal, al, var_idx = dal_tot, al_tot, None
            else:
                dal = min(p[0] for p in periodi[m])
                al = max(p[1] for p in periodi[m])
                id_idx = ID_BTC if m == "CRYPTO" else INDICE_PRINCIPALE[m]
                var_idx = None
                if id_idx in serie:
                    ci = serie[id_idx]["chiusura"]
                    a0, a1 = ci.loc[:dal], ci.loc[:al]
                    if len(a0) and len(a1):
                        var_idx = (float(a1.iloc[-1]) / float(a0.iloc[-1]) - 1.0) * 100.0
            st = bt.statistiche(ops.get((regola, m), []), aperte.get((regola, m), 0), dal, al, var_idx,
                                par["backtest"]["min_operazioni"])
            regole_stat.append({"regola": regola, "nome": sg.NOMI_REGOLE[regola], "mercato": m, **st})
    forza = []
    for m in [x for x in MERCATI if x in periodi]:
        membri = [s for s in trading if mercato_di(s) == m]
        ch = pd.DataFrame({s["id"]: calcolati[s["id"]]["chiusura"] for s in membri})
        dal = min(p[0] for p in periodi[m])
        forza.append({"mercato": m, **bt.coorte_forza_relativa(ch, dal)})
    affidabilita = {"generato_il": generato, "periodo": {"dal": dal_tot, "al": al_tot},
                    "avvertenze": bt.AVVERTENZE, "regole": regole_stat, "forza_relativa": forza}
    for r in regole_stat:
        if r["mercato"] == "TUTTI":
            media = r["rendimento_medio_netto_pct"]
            log(f"Backtest {r['regola']}: {r['operazioni']} operazioni, media netta "
                f"{'n.d.' if media is None else f'{media:.2f}%'}, {r['giudizio']}")

    # ---- registro dei segnali
    percorso_reg = cartella_dati / "registro_segnali.json"
    precedente = None
    if percorso_reg.exists():
        try:
            precedente = json.loads(percorso_reg.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            log(f"Registro precedente illeggibile ({e}): si riparte da zero")
    reg = rg.aggiorna(precedente, list(oggetti.values()), {k: calcolati[k] for k in oggetti}, uscite, par, generato)
    log(f"Registro: {reg['riepilogo']}")

    # ---- ETF e PAC
    etf_out, mensili, serie_etf = [], {}, {}
    for s in strumenti:
        if s["tipo"] != "etf" or s["id"] not in calcolati:
            continue
        d = calcolati[s["id"]]
        m = s["meta"]
        met = pac.metriche(serie[s["id"]], par)
        etf_out.append({
            "id": s["id"], "tipo": "etf", "nome": m["nome"], "isin": m.get("isin"), "categoria": m["categoria"],
            "indice_replicato": m.get("indice_replicato"), "ter_pct": m.get("ter_pct"), "politica": m.get("politica"),
            "emittente": m.get("emittente"), "valuta_fondo": m.get("valuta_fondo"),
            "copertura_cambio": m.get("copertura_cambio"), "note": m.get("note", ""),
            "data": d.index[-1], "prezzo": float(d["chiusura"].iloc[-1]), **met,
            "tendenza": str(d["tendenza"].iloc[-1]), "qualita": qualita[s["id"]],
        })
        mensili[s["id"]] = pac.rendimenti_mensili(serie[s["id"]])
        serie_etf[s["id"]] = esporta.serie_grafico(d)

    # ---- file
    def lista_mercato(m, tipo):
        return sorted([o for o in oggetti.values() if o["mercato"] == m and o["tipo"] == tipo],
                      key=lambda o: -o["punteggio"])
    azioni_lista = [o for m in ("IT", "EU", "US") for o in lista_mercato(m, "azione")]
    crypto_lista = lista_mercato("CRYPTO", "crypto")
    cartella_dati.mkdir(parents=True, exist_ok=True)
    scritti = {}
    scritti["azioni.json"] = esporta.scrivi(cartella_dati, "azioni.json", {"generato_il": generato, "strumenti": azioni_lista})
    scritti["crypto.json"] = esporta.scrivi(cartella_dati, "crypto.json", {"generato_il": generato, "strumenti": crypto_lista})
    scritti["etf.json"] = esporta.scrivi(cartella_dati, "etf.json", {"generato_il": generato, "strumenti": etf_out})
    scritti["etf_mensili.json"] = esporta.scrivi(cartella_dati, "etf_mensili.json", mensili)
    scritti["clima.json"] = esporta.scrivi(cartella_dati, "clima.json", clima_json)
    scritti["affidabilita.json"] = esporta.scrivi(cartella_dati, "affidabilita.json", affidabilita)
    scritti["registro_segnali.json"] = esporta.scrivi(cartella_dati, "registro_segnali.json", reg)
    cand = par["candidati"]
    for m in MERCATI:
        membri = [o for o in oggetti.values() if o["mercato"] == m]
        ser = {o["id"]: esporta.serie_grafico(calcolati[o["id"]]) for o in membri}
        if m in INDICE_PRINCIPALE and INDICE_PRINCIPALE[m] in calcolati:
            ser[INDICE_PRINCIPALE[m]] = esporta.serie_grafico(calcolati[INDICE_PRINCIPALE[m]])
        scritti[f"serie_{m}.json"] = esporta.scrivi(cartella_dati, f"serie_{m}.json", ser)
        per_stato = lambda st: sorted([o for o in membri if o["stato"] == st], key=lambda o: -o["punteggio"])
        uscita = sorted([o for o in membri if o["stato"] == "ESCI"], key=lambda o: o["punteggio"])
        candidati = {"mercato": m, "generato_il": generato, "clima": clima_per.get(m),
                     "acquisto": per_stato("COMPRA")[:cand["max_acquisto"]],
                     "osservati": per_stato("OSSERVA")[:cand["max_osservati"]],
                     "uscita": uscita[:cand["max_uscita"]],
                     "affidabilita": [r for r in regole_stat if r["mercato"] == m]}
        scritti[f"candidati_{m}.json"] = esporta.scrivi(cartella_dati, f"candidati_{m}.json", candidati)
    scritti["serie_ETF.json"] = esporta.scrivi(cartella_dati, "serie_ETF.json", serie_etf)

    # ---- stato
    attesi = [s for s in strumenti if s["tipo"] in ("azione", "etf", "crypto")]
    presenti = [s for s in attesi if s["id"] in calcolati]
    ultima_seduta = {}
    for m in MERCATI:
        date = [calcolati[s["id"]].index[-1] for s in trading if mercato_di(s) == m]
        ultima_seduta[m] = max(date).strftime("%Y-%m-%d") if date else None
    avvisi = []
    if args.demo:
        avvisi.append("Dati dimostrativi: prezzi e segnali inventati, non usarli per operare.")
    vecchi = [k for k, q in qualita.items() if q == "dati_vecchi" and per_id[k]["tipo"] != "indice"]
    if vecchi:
        avvisi.append(f"{len(vecchi)} strumenti con dati vecchi: {', '.join(sorted(vecchi)[:12])}")
    corti = [k for k, q in qualita.items() if q == "storico_corto" and per_id[k]["tipo"] != "indice"]
    if corti:
        avvisi.append(f"{len(corti)} strumenti con storico corto (meno di 260 barre): {', '.join(sorted(corti)[:12])}")
    if fonti_usate["orari"]:
        avvisi.append(f"{len(fonti_usate['orari'])} titoli con l'ultima seduta ricostruita dai dati orari di Yahoo "
                      "(prezzi affidabili, volumi forse incompleti)")
    if ritardo:
        avvisi.append(f"{len(ritardo)} titoli senza l'ultima seduta del loro indice (dati in ritardo): {', '.join(sorted(ritardo)[:12])}"
                      + (" …" if len(ritardo) > 12 else ""))
    if fonti_usate["kraken"]:
        avvisi.append(f"Prezzi solo da Kraken (circa 2 anni di storico) per: {', '.join(fonti_usate['kraken'])}")
    for i in ("FTSEMIB.MI", "^STOXX50E", "^GSPC"):
        if any(s["id"] == i for s in strumenti) and i not in calcolati:
            avvisi.append(f"Indice {i} mancante: clima e forza relativa del suo mercato incompleti.")
    try:
        import yfinance as _yf
        ver_yf = _yf.__version__
    except Exception:
        ver_yf = "?"
    stato_json = {
        "generato_il": generato, "modalita": "demo" if args.demo else "reale", "versione_motore": VERSIONE,
        "conteggi": {"azioni": len(azioni_lista), "etf": len(etf_out), "crypto": len(crypto_lista),
                     "esclusi": len(problemi), "universo": len(attesi)},
        "ultima_seduta": ultima_seduta,
        "fonti": ({"azioni": "dati sintetici", "crypto": "dati sintetici"} if args.demo else
                  {"azioni": f"yfinance {ver_yf}", "etf": f"yfinance {ver_yf}", "crypto": "yfinance, Kraken"}),
        "problemi": problemi, "avvisi": avvisi, "durata_secondi": round(time.time() - t0, 1),
        "file": sorted(scritti),
    }
    mancano = len(attesi) - len(presenti)
    codice = 1 if attesi and mancano > len(attesi) / 2 else 0
    if codice:
        stato_json["avvisi"].append(f"Mancano {mancano} strumenti su {len(attesi)}: esecuzione considerata fallita.")
    log(f"Fatto: {len(presenti)} strumenti su {len(attesi)}, {len(problemi)} problemi, {stato_json['durata_secondi']} s")
    return stato_json, codice


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Motore del Guardiano dei Mercati")
    p.add_argument("--demo", action="store_true", help="usa dati sintetici deterministici")
    p.add_argument("--cartella-config", help="cartella con universi e parametri")
    p.add_argument("--cartella-dati", help="cartella di uscita dei JSON")
    p.add_argument("--solo", choices=["azioni", "etf", "crypto"])
    p.add_argument("--limite", type=int, help="al massimo N strumenti per mercato o categoria")
    p.add_argument("--data-demo", help=argparse.SUPPRESS)
    args = p.parse_args(argv)
    log = Diario()
    adesso_utc = dt.datetime.now(dt.timezone.utc)
    generato = adesso_utc.astimezone(ROMA).isoformat(timespec="seconds")
    cartella_dati = Path(args.cartella_dati) if args.cartella_dati else RADICE / "dati"
    try:
        stato_json, codice = esegui(args, log, adesso_utc, generato)
    except Exception as e:
        log(f"ERRORE FATALE: {type(e).__name__}: {e}")
        for riga in traceback.format_exc().splitlines():
            log(riga)
        stato_json = {"generato_il": generato, "modalita": "demo" if args.demo else "reale",
                      "versione_motore": VERSIONE, "errore": f"{type(e).__name__}: {e}",
                      "conteggi": {}, "ultima_seduta": {}, "fonti": {}, "problemi": [],
                      "avvisi": ["Esecuzione fallita: i dati di questo giro non sono disponibili."], "durata_secondi": None}
        codice = 2
    cartella_dati.mkdir(parents=True, exist_ok=True)
    esporta.scrivi(cartella_dati, "stato.json", stato_json)
    if codice == 0:  # sul ramo dati, dopo un giro fallito, il flusso lo sostituisce con la diagnosi
        esporta.scrivi(cartella_dati, "errore_ultimo_giro.json", {"esito": "ok", "generato_il": None})
    (cartella_dati / "ultimo_log.txt").write_text("\n".join(log.righe[-400:]) + "\n", encoding="utf-8")
    return codice


if __name__ == "__main__":
    sys.exit(main())

"""Controlla che rapporto.json rispetti la sezione 15 della specifica.

Uso: python valida_rapporto.py rapporto.json [--dati CARTELLA_DATI]
Con --dati confronta anche strumenti e stop con i file del motore (avvisi, non errori).
Esce con codice 1 se trova errori.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MERCATI = {"IT", "EU", "US", "CRYPTO"}


def valida(r: dict, dati: Path | None = None) -> tuple[list[str], list[str]]:
    err: list[str] = []
    avv: list[str] = []

    def testo(obj, chiave, dove, vuoto_ok=False):
        v = obj.get(chiave) if isinstance(obj, dict) else None
        if not isinstance(v, str) or (not vuoto_ok and not v.strip()):
            err.append(f"{dove}.{chiave}: serve un testo")
        return v

    def numero(obj, chiave, dove, nullo_ok=False):
        v = obj.get(chiave) if isinstance(obj, dict) else None
        if v is None and nullo_ok:
            return None
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            err.append(f"{dove}.{chiave}: serve un numero")
            return None
        return v

    def lista(obj, chiave, dove):
        v = obj.get(chiave) if isinstance(obj, dict) else None
        if not isinstance(v, list):
            err.append(f"{dove}.{chiave}: serve un elenco")
            return []
        return v

    def scelta(obj, chiave, dove, ammessi):
        v = obj.get(chiave) if isinstance(obj, dict) else None
        if v not in ammessi:
            err.append(f"{dove}.{chiave}: «{v}» non ammesso ({', '.join(sorted(ammessi))})")
        return v

    if not isinstance(r, dict):
        return ["il rapporto deve essere un oggetto JSON"], []
    if not DATA.match(str(r.get("data", ""))):
        err.append("data: formato AAAA-MM-GG")
    testo(r, "generato_il", "rapporto")
    testo(r, "dati_del", "rapporto")
    testo(r, "avvertenze", "rapporto")
    cl = r.get("clima")
    if not isinstance(cl, dict):
        err.append("clima: serve un oggetto")
    else:
        testo(cl, "sintesi", "clima")
        for k, m in enumerate(lista(cl, "mercati", "clima")):
            scelta(m, "mercato", f"clima.mercati[{k}]", MERCATI)
            scelta(m, "giudizio", f"clima.mercati[{k}]", {"favorevole", "incerto", "sfavorevole"})
            testo(m, "nota", f"clima.mercati[{k}]")
    proposte = lista(r, "proposte", "rapporto")
    if len(proposte) > 5:
        err.append(f"proposte: al massimo 5 (sono {len(proposte)})")
    for k, p in enumerate(proposte):
        d = f"proposte[{k}]"
        for c in ("id", "strumento", "nome", "orizzonte", "tesi", "affidabilita_segnale"):
            testo(p, c, d)
        scelta(p, "tipo", d, {"azione", "crypto", "etf"})
        scelta(p, "mercato", d, MERCATI)
        scelta(p, "azione", d, {"COMPRA", "ATTENDI"})
        scelta(p, "fiducia", d, {"bassa", "media", "alta"})
        perche = lista(p, "perche", d)
        if not perche or not all(isinstance(x, str) and x.strip() for x in perche):
            err.append(f"{d}.perche: almeno un motivo, solo testi")
        lista(p, "rischi", d)
        pi = p.get("piano")
        if not isinstance(pi, dict):
            err.append(f"{d}.piano: serve un oggetto")
        else:
            prezzo = numero(pi, "prezzo_riferimento", d + ".piano")
            stop = numero(pi, "stop", d + ".piano")
            numero(pi, "obiettivo", d + ".piano")
            numero(pi, "rischio_pct", d + ".piano")
            testo(pi, "ingresso", d + ".piano")
            testo(pi, "dimensione", d + ".piano")
            if prezzo is not None and stop is not None and stop >= prezzo:
                err.append(f"{d}.piano: lo stop deve stare sotto il prezzo di riferimento")
        so = p.get("solidita")
        if not isinstance(so, dict):
            err.append(f"{d}.solidita: serve un oggetto")
        else:
            testo(so, "giudizio", d + ".solidita")
            lista(so, "punti", d + ".solidita")
        for j, n in enumerate(lista(p, "notizie", d)):
            for c in ("titolo", "fonte"):
                testo(n, c, f"{d}.notizie[{j}]")
            if not str(n.get("url", "")).startswith(("https://", "http://")):
                err.append(f"{d}.notizie[{j}].url: serve un link http(s)")
            if not DATA.match(str(n.get("data", ""))):
                err.append(f"{d}.notizie[{j}].data: formato AAAA-MM-GG")
        v = p.get("vagli")
        if not isinstance(v, dict):
            err.append(f"{d}.vagli: serve un oggetto")
        else:
            for c in ("analista", "supervisore", "rischio"):
                testo(v, c, d + ".vagli")
    for k, p in enumerate(lista(r, "posizioni", "rapporto")):
        d = f"posizioni[{k}]"
        testo(p, "strumento", d)
        testo(p, "nome", d)
        scelta(p, "azione", d, {"MANTIENI", "RIDUCI", "VENDI"})
        testo(p, "motivo", d)
        numero(p, "stop_aggiornato", d, nullo_ok=True)
    for k, s in enumerate(lista(r, "scartate", "rapporto")):
        for c in ("strumento", "nome", "motivo"):
            testo(s, c, f"scartate[{k}]")
    pac = r.get("pac")
    if not isinstance(pac, dict):
        err.append("pac: serve un oggetto")
    else:
        testo(pac, "nota", "pac", vuoto_ok=True)
        lista(pac, "controlli", "pac")

    if dati is not None and not r.get("esempio"):
        motore = {}
        for nome in ("azioni.json", "crypto.json", "etf.json"):
            f = dati / nome
            if f.exists():
                for o in json.loads(f.read_text(encoding="utf-8")).get("strumenti", []):
                    motore[o["id"]] = o
        stato = dati / "stato.json"
        if stato.exists() and json.loads(stato.read_text(encoding="utf-8")).get("modalita") == "demo" and proposte:
            err.append("con dati dimostrativi non si fanno proposte")
        for k, p in enumerate(proposte):
            o = motore.get(p.get("strumento"))
            if o is None:
                err.append(f"proposte[{k}]: strumento {p.get('strumento')} assente dai dati del motore")
                continue
            stop_motore = [s.get("stop") for s in o.get("segnali_attivi", [])] + [(o.get("livelli") or {}).get("stop_suggerito")]
            stop = (p.get("piano") or {}).get("stop")
            if isinstance(stop, (int, float)) and not any(isinstance(x, (int, float)) and abs(x - stop) <= 0.005 * abs(x) for x in stop_motore):
                avv.append(f"proposte[{k}]: lo stop {stop} non coincide con quelli del motore {stop_motore}")
    return err, avv


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    r = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    dati = Path(argv[argv.index("--dati") + 1]) if "--dati" in argv else None
    err, avv = valida(r, dati)
    for a in avv:
        print("AVVISO:", a)
    for e in err:
        print("ERRORE:", e)
    print("rapporto valido" if not err else f"{len(err)} errori")
    return 1 if err else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

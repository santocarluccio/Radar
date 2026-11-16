"""Il validatore del rapporto accetta l'esempio e respinge un rapporto rotto."""
import copy
import importlib.util
import json
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("valida_rapporto", RADICE / "agenti" / "valida_rapporto.py")
valida_rapporto = importlib.util.module_from_spec(spec)
spec.loader.exec_module(valida_rapporto)


def test_esempio_valido_e_rapporto_rotto():
    esempio = json.loads((RADICE / "agenti" / "esempio_rapporto.json").read_text(encoding="utf-8"))
    err, _ = valida_rapporto.valida(esempio)
    assert err == []
    rotto = copy.deepcopy(esempio)
    rotto["proposte"][0]["azione"] = "VENDI"
    rotto["proposte"][0]["piano"]["stop"] = 20.0
    rotto["proposte"][0]["notizie"][0]["url"] = "javascript:alert(1)"
    del rotto["clima"]
    err, _ = valida_rapporto.valida(rotto)
    assert len(err) == 4

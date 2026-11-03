import json

import pytest

from src.pipeline import final_threshold, load_threshold, save_reference_value

SAVED = {"fraction": 0.09, "value": 0.857, "reference_value": 1.23}


def test_valor_fijo_usa_el_valor_guardado():
    assert final_threshold("valor fijo", SAVED) == (None, 0.857)
    assert final_threshold("valor fijo", SAVED, reference=True) == (None, 1.23)


def test_fraccion_fija_usa_la_fraccion_guardada():
    assert final_threshold("fracción fija", SAVED) == (0.09, None)


def test_falta_el_valor_o_regla_desconocida():
    with pytest.raises(ValueError):
        final_threshold("valor fijo", {"fraction": 0.09, "value": None})
    with pytest.raises(ValueError):
        final_threshold("valor fijo", {"fraction": 0.09, "value": 0.8}, reference=True)
    with pytest.raises(ValueError):
        final_threshold("otsu", SAVED)


def test_guardar_y_leer_el_valor_de_la_referencia(tmp_path):
    path = tmp_path / "pesos.json"
    path.write_text(json.dumps({"features": [], "intercept": 0, "coefficients": [],
                                "fraction": 0.09, "value": 0.857, "note": ""}), encoding="utf-8")
    assert load_threshold(path)["reference_value"] is None
    save_reference_value(1.5, path)
    saved = load_threshold(path)
    assert saved == {"fraction": 0.09, "value": 0.857, "reference_value": 1.5}
    assert json.loads(path.read_text(encoding="utf-8"))["value"] == 0.857   # lo demás no cambia
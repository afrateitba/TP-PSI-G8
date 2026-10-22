from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from PIL import Image

from src.config import GROUPS, IMAGE_IDS, N_PER_GROUP, RAW_DIR, SPLIT_CSV
from src.data import (assign_persons, dev_ids, disc_side, group_of, load_fov,
                      load_image, load_split, load_vessels, quant_mean)

HAS_DATA = (RAW_DIR / "images").exists() and SPLIT_CSV.exists()


def test_image_ids():
    assert len(IMAGE_IDS) == len(GROUPS) * N_PER_GROUP == 45
    assert IMAGE_IDS[0] == "01_h" and IMAGE_IDS[-1] == "15_g"
    assert group_of("03_dr") == "dr"
    with pytest.raises(ValueError):
        group_of("03_x")


def test_assign_persons_gap_and_transitivity():
    t0 = datetime(2007, 1, 22, 10, 0)
    times = pd.Series({
        "a": t0,
        "b": t0 + timedelta(minutes=1),            # misma persona que a
        "c": t0 + timedelta(minutes=60),           # otra persona
        "d": t0 + timedelta(minutes=68),           # con c
        "e": t0 + timedelta(minutes=76),           # con d, y por cadena con c
        "f": t0 + timedelta(days=3),
    })
    persons = assign_persons(times.sample(frac=1, random_state=0), max_gap_min=10)
    persons = persons.loc[times.index]
    assert persons["a"] == persons["b"]
    assert persons["c"] == persons["d"] == persons["e"]
    assert len(set(persons)) == 3


def test_assign_persons_numbering_follows_index_order():
    t0 = datetime(2007, 1, 1)
    times = pd.Series({"x": t0 + timedelta(days=5), "y": t0})
    assert assign_persons(times).to_dict() == {"x": "P01", "y": "P02"}


def test_quant_mean_grows_with_compression(tmp_path):
    rng = np.random.default_rng(2026)
    img = Image.fromarray(rng.integers(0, 256, (64, 64, 3), dtype=np.uint8))
    img.save(tmp_path / "hi.jpg", quality=95)
    img.save(tmp_path / "lo.jpg", quality=50)
    assert quant_mean(tmp_path / "lo.jpg") > quant_mean(tmp_path / "hi.jpg")


def test_disc_side_finds_bright_spot():
    rgb = np.zeros((400, 600, 3), dtype=np.uint8)
    fov = np.ones((400, 600), dtype=bool)
    rgb[180:220, 60:100] = 255
    assert disc_side(rgb, fov) == "izquierda"
    assert disc_side(rgb[:, ::-1], fov) == "derecha"


@pytest.mark.skipif(not HAS_DATA, reason="faltan las imágenes en data/raw")
def test_real_masks_match_images():
    # Solo imágenes de desarrollo; 13_h es una de las máscaras con píxeles grises.
    for image_id in ["01_h", "13_h", "05_dr", "03_g"]:
        assert image_id in dev_ids()
        rgb = load_image(image_id)
        vessels, fov = load_vessels(image_id), load_fov(image_id)
        assert rgb.shape == (2336, 3504, 3) and rgb.dtype == np.uint8
        assert vessels.shape == fov.shape == rgb.shape[:2]
        assert 0.05 < vessels[fov].mean() < 0.15


@pytest.mark.skipif(not SPLIT_CSV.exists(), reason="todavía no hay split.csv")
def test_real_persons():
    # Se revisa lo guardado en split.csv, sin volver a leer las imágenes de prueba.
    t = load_split()
    assert len(t) == 45
    assert t.groupby("person")["group"].nunique().max() == 1
    sizes = t.groupby("person").size()
    assert sizes.max() == 2 and t["person"].nunique() == 28
    # Las dos imágenes de cada persona son un ojo derecho y uno izquierdo.
    pairs = t[t["person"].isin(sizes[sizes == 2].index)]
    assert (pairs.groupby("person")["disc_side"].nunique() == 2).all()
    assert set(t["quant_mean"]) == {2.94, 11.06}

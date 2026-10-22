"""Candado del conjunto de prueba (plan de evaluación, sección 1)."""
from pathlib import Path

import pytest

import src.data as data
from src.config import RAW_DIR, ROOT, SPLIT_CSV

HAS_SPLIT = SPLIT_CSV.exists()
HAS_DATA = (RAW_DIR / "images").exists() and HAS_SPLIT

# Entradas que saltean el candado y los únicos archivos donde pueden aparecer
# (este archivo no se revisa, porque las nombra).
ACCESS_POINTS = {
    "load_test_case(": {"src/data.py", "notebooks/99_prueba.ipynb"},
    "image_table(": {"src/data.py", "scripts/make_split.py"},
    "_read_rgb(": {"src/data.py"},
    "_binary(": {"src/data.py"},
}


@pytest.mark.skipif(not HAS_SPLIT, reason="todavía no hay split.csv")
def test_ids_cover_split():
    dev, held = data.dev_ids(), data.heldout_ids()
    assert len(dev) == 30 and len(held) == 15
    assert not set(dev) & set(held)
    assert len(data.dev_ids("dr")) == 10
    assert all(i.endswith("_dr") for i in data.dev_ids("dr"))


@pytest.mark.skipif(not HAS_SPLIT, reason="todavía no hay split.csv")
def test_loaders_refuse_heldout_images():
    held = data.heldout_ids()[0]
    for loader in (data.load_image, data.load_vessels, data.load_fov):
        with pytest.raises(data.LockedImageError):
            loader(held)


@pytest.mark.skipif(not HAS_SPLIT, reason="todavía no hay split.csv")
def test_load_test_case_refuses_dev_images():
    with pytest.raises(ValueError):
        data.load_test_case(data.dev_ids()[0])


@pytest.mark.skipif(not HAS_DATA, reason="faltan las imágenes en data/raw")
def test_dev_images_load():
    image_id = data.dev_ids()[0]
    assert data.load_fov(image_id).any()


def test_access_points_only_where_allowed():
    """Las entradas que saltean el candado no aparecen fuera de su lugar."""
    files = [p for d in ("src", "scripts", "notebooks", "tests")
             for p in (ROOT / d).rglob("*")
             if p.suffix in {".py", ".ipynb"} and p.resolve() != Path(__file__).resolve()]
    for pattern, allowed in ACCESS_POINTS.items():
        used = {p.relative_to(ROOT).as_posix() for p in files
                if pattern in p.read_text(encoding="utf-8")}
        assert used <= allowed, f"{pattern} aparece en {sorted(used - allowed)}"

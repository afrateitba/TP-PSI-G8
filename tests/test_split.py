import pandas as pd
import pytest

from src.config import SPLIT_CSV
from src.split import compressed_quota, group_candidates, make_split


def _fake_table():
    """Dos grupos chicos. Las personas con dos imágenes son pares de ojos.

    Grupo h: 6 imágenes, 3 más comprimidas -> con 2 en prueba, cuota {1}.
    Grupo dr: 5 imágenes, 1 más comprimida -> con 2 en prueba, cuota {0, 1}.
    """
    rows = [  # image, group, person, more_compressed
        ("01_h", "h", "P1", False), ("02_h", "h", "P1", False),
        ("03_h", "h", "P2", True), ("04_h", "h", "P2", True),
        ("05_h", "h", "P3", False),
        ("06_h", "h", "P4", True),
        ("01_dr", "dr", "P5", True), ("02_dr", "dr", "P5", False),
        ("03_dr", "dr", "P6", False),
        ("04_dr", "dr", "P7", False),
        ("05_dr", "dr", "P8", False),
    ]
    return pd.DataFrame(rows, columns=["image", "group", "person", "more_compressed"])


def test_compressed_quota_is_floor_and_ceiling():
    assert compressed_quota(10, 15, 5) == {3, 4}   # 3,33
    assert compressed_quota(3, 15, 5) == {1}       # exacto, sin error de redondeo
    assert compressed_quota(7, 15, 5) == {2, 3}


def test_group_candidates_exact():
    t = _fake_table()
    # h: 2 imágenes con exactamente 1 más comprimida -> P3 (no) + P4 (sí).
    assert group_candidates(t, "h", 2) == [("P3", "P4")]
    # dr: 2 imágenes, 0 o 1 más comprimidas -> el par P5 o dos sueltas.
    assert set(group_candidates(t, "dr", 2)) == {
        ("P5",), ("P6", "P7"), ("P6", "P8"), ("P7", "P8")}


def test_make_split_keeps_persons_and_quotas():
    t = _fake_table()
    s = make_split(t, n_test=2, seed=1)
    assert (s.groupby("person")["set"].nunique() == 1).all()
    assert (s[s["set"] == "test"].groupby("group").size() == 2).all()
    assert s.equals(make_split(t, n_test=2, seed=1))


def test_make_split_rejects_person_in_two_groups():
    t = _fake_table()
    t.loc[t["image"] == "05_dr", "person"] = "P1"
    with pytest.raises(ValueError):
        make_split(t, n_test=2)


@pytest.mark.skipif(not SPLIT_CSV.exists(), reason="todavía no hay split.csv")
def test_saved_split():
    s = pd.read_csv(SPLIT_CSV)
    assert len(s) == 45
    assert (s.groupby("person")["set"].nunique() == 1).all()
    assert (s[s["set"] == "test"].groupby("group").size() == 5).all()
    for g, d in s.groupby("group"):
        n_more_test = int(d.loc[d["set"] == "test", "more_compressed"].sum())
        assert n_more_test in compressed_quota(int(d["more_compressed"].sum()), len(d), 5)

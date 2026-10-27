import numpy as np
import pytest

from src.metrics import auc, auc_thin, thin_masks

LIMITS = (3.47, 9.0)


def two_vessels():
    """Un vaso fino (3 px) y uno grueso (11 px) sobre fondo, en una imagen de 100 × 100."""
    thin = np.zeros((100, 100), bool)
    thick = np.zeros_like(thin)
    thin[10:90, 29:32] = True
    thick[10:90, 60:71] = True
    return thin | thick, thin, thick


def test_score_only_on_thin_gives_one():
    truth, thin, thick = two_vessels()
    score = thin.astype(np.float32)
    assert auc_thin(score, truth, limits=LIMITS) == pytest.approx(1.0)
    assert auc(score, truth) < 1.0           # con todos los vasos, el grueso sin marcar resta


def test_thick_vessels_do_not_count():
    # marcar solo el grueso no ayuda ni perjudica a los finos: queda como el azar
    truth, thin, thick = two_vessels()
    assert auc_thin(thick.astype(np.float32), truth, limits=LIMITS) == pytest.approx(0.5)


def test_respects_region():
    truth, thin, thick = two_vessels()
    region = np.ones_like(truth)
    region[:, :50] = False                    # deja afuera el vaso fino
    with pytest.raises(ValueError):           # sin vasos finos en la región no hay área
        auc_thin(thin.astype(np.float32), truth, region, LIMITS)
        

def test_precomputed_masks_give_same_result():
    truth, thin, thick = two_vessels()
    score = np.random.default_rng(2026).random(truth.shape).astype(np.float32) + thin
    masks = thin_masks(truth, limits=LIMITS)
    assert auc_thin(score, truth, masks=masks) == pytest.approx(auc_thin(score, truth, limits=LIMITS))

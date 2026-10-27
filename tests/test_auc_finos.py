import numpy as np
import pytest

from src.metrics import auc, auc_finos

LIMITES = (3.47, 9.0)


def dos_vasos():
    """Un vaso fino (3 px) y uno grueso (11 px) sobre fondo, en una imagen de 100 × 100."""
    truth = np.zeros((100, 100), bool)
    fino = np.zeros_like(truth)
    grueso = np.zeros_like(truth)
    fino[10:90, 29:32] = True
    grueso[10:90, 60:71] = True
    truth = fino | grueso
    return truth, fino, grueso


def test_puntaje_solo_en_los_finos_da_uno():
    truth, fino, grueso = dos_vasos()
    score = fino.astype(np.float32)
    assert auc_finos(score, truth, limits=LIMITES) == pytest.approx(1.0)
    assert auc(score, truth) < 1.0           # con todos los vasos, el grueso sin marcar resta


def test_los_gruesos_no_cuentan():
    # marcar solo el grueso no ayuda ni perjudica a los finos: queda como el azar
    truth, fino, grueso = dos_vasos()
    score = grueso.astype(np.float32)
    assert auc_finos(score, truth, limits=LIMITES) == pytest.approx(0.5)


def test_respeta_la_region():
    truth, fino, grueso = dos_vasos()
    region = np.ones_like(truth)
    region[:, :50] = False                    # deja afuera el vaso fino
    with pytest.raises(ValueError):           # sin vasos finos en la región no hay área
        auc_finos(fino.astype(np.float32), truth, region, LIMITES)
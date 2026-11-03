"""Segmenta los vasos de una foto de fondo de ojo con el algoritmo final.

Uso:  python scripts/segmentar.py foto.jpg mascara.png
      python scripts/segmentar.py foto.jpg mascara.png --superpuesta vista.png
      python scripts/segmentar.py foto.jpg mascara.png --referencia   # solo el detector de líneas

La máscara se guarda en blanco (vaso) y negro (fondo), del mismo tamaño que la
foto. No necesita la máscara del campo de visión: la detecta sola. Los pesos
de la combinación y los umbrales se leen de models/pesos_combinacion.json, y
la regla del umbral (valor fijo, etapa 8) de config.SEGMENT_THRESHOLD_RULE.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline import WEIGHTS_PATH, segment_final  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("foto", type=Path)
    parser.add_argument("salida", type=Path)
    parser.add_argument("--superpuesta", type=Path, help="guarda también la foto con los vasos en verde")
    parser.add_argument("--referencia", action="store_true", help="usa solo el detector de líneas")
    parser.add_argument("--pesos", type=Path, default=WEIGHTS_PATH)
    args = parser.parse_args()

    if not args.pesos.exists():
        sys.exit(f"Faltan los pesos y umbrales en {args.pesos}.")
    rgb = np.asarray(Image.open(args.foto).convert("RGB"))
    mask = segment_final(rgb, reference=args.referencia, path=args.pesos)
    Image.fromarray(mask.astype(np.uint8) * 255).save(args.salida)
    print(f"{args.salida}: {mask.sum():,} píxeles de vaso ({mask.mean():.1%} de la foto)")
    if args.superpuesta:
        view = rgb.copy()
        view[mask] = (0.4 * view[mask] + 0.6 * np.array([0, 255, 0])).astype(np.uint8)
        Image.fromarray(view).save(args.superpuesta)
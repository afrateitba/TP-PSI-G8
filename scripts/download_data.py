"""Descarga la High-Resolution Fundus Image Database a data/raw/ (~76 MB).

Uso:  python scripts/download_data.py
"""
import sys
import zipfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import HRF_URL, HRF_ZIP_BYTES, RAW_DIR  # noqa: E402

if __name__ == "__main__":
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = RAW_DIR / "all.zip"
    if not zip_path.exists() or zip_path.stat().st_size != HRF_ZIP_BYTES:
        print(f"Descargando {HRF_URL}")
        with requests.get(HRF_URL, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(zip_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
    if zip_path.stat().st_size != HRF_ZIP_BYTES:
        sys.exit(f"Tamaño inesperado: {zip_path.stat().st_size} bytes "
                 f"(se esperaban {HRF_ZIP_BYTES}).")
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(RAW_DIR)
    print("Descarga completa.")

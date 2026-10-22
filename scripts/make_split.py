"""Genera data/split.csv una única vez.

Uso:  python scripts/make_split.py           # falla si split.csv ya existe
      python scripts/make_split.py --force   # solo con acuerdo de los tres
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import GROUPS, SEED, SPLIT_CSV  # noqa: E402
from src.data import image_table  # noqa: E402
from src.split import group_candidates, make_split  # noqa: E402

if __name__ == "__main__":
    if SPLIT_CSV.exists() and "--force" not in sys.argv:
        sys.exit(f"{SPLIT_CSV} ya existe. La partición no se regenera (usar --force).")

    table = image_table()
    split = make_split(table)
    if (split.groupby("person")["set"].nunique() > 1).any():
        sys.exit("Error: hay personas en desarrollo y en prueba.")
    split.to_csv(SPLIT_CSV, index=False)

    print(f"Guardado {SPLIT_CSV}")
    for g in GROUPS:
        print(f"Particiones válidas del grupo {g}: {len(group_candidates(table, g))}")
    print(f"Se eligió una por grupo con semilla {SEED}.\n")
    print("Imágenes:")
    print(split.groupby(["group", "set"]).size().unstack(fill_value=0), "\n")
    print("Personas:")
    print(split.groupby(["group", "set"])["person"].nunique().unstack(fill_value=0), "\n")
    print("Imágenes más comprimidas:")
    print(split.groupby(["group", "set"])["more_compressed"].sum().unstack(fill_value=0), "\n")
    print("Prueba:", ", ".join(split.loc[split["set"] == "test", "image"]))

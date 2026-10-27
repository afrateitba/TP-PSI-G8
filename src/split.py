"""Partición en desarrollo y prueba por persona.  Esquema v1, etapa 0.

Una partición es válida si cumple, en cada grupo (sano, retinopatía
diabética, glaucoma), las tres condiciones:
1. Personas enteras: las imágenes de una persona (assign_persons) van al
   mismo conjunto, para que prueba sea gente que el método no vio.
2. Cupo exacto: prueba lleva TEST_PER_GROUP imágenes del grupo.
3. Compresión pareja: la cantidad de imágenes más comprimidas en prueba es
   el piso o el techo de TEST_PER_GROUP x (fracción más comprimida del grupo).
Como ninguna persona tiene imágenes de dos grupos, cada grupo se sortea por
separado: se enumeran todas sus combinaciones válidas y se elige una al azar
con SEED, así que todas tienen la misma probabilidad. Las condiciones usan
solo el grupo, la persona y la compresión, nunca las máscaras ni resultados.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd

from .config import GROUPS, SEED, TEST_PER_GROUP


def compressed_quota(n_more: int, n_group: int, n_test: int = TEST_PER_GROUP) -> set[int]:
    """Cantidades permitidas de imágenes más comprimidas en prueba (piso y techo)."""
    num = n_test * n_more
    return {num // n_group, -(-num // n_group)}


def group_candidates(table: pd.DataFrame, group: str,
                     n_test: int = TEST_PER_GROUP) -> list[tuple[str, ...]]:
    """Todas las combinaciones de personas del grupo que cumplen las condiciones.

    `table` necesita las columnas group, person y more_compressed. Devuelve
    tuplas de personas ordenadas.
    """
    t = table[table["group"] == group]
    per_person = t.groupby("person").agg(n=("person", "size"),
                                         n_more=("more_compressed", "sum"))
    allowed = compressed_quota(int(t["more_compressed"].sum()), len(t), n_test)
    persons = sorted(per_person.index)
    n, n_more = per_person["n"].to_dict(), per_person["n_more"].to_dict()
    valid = []
    for k in range(1, n_test + 1):
        for combo in combinations(persons, k):
            if (sum(n[p] for p in combo) == n_test
                    and sum(n_more[p] for p in combo) in allowed):
                valid.append(combo)
    return valid


def make_split(table: pd.DataFrame, n_test: int = TEST_PER_GROUP,
               seed: int = SEED) -> pd.DataFrame:
    """Agrega la columna 'set' ('dev' o 'test') con una partición válida al azar."""
    if (table.groupby("person")["group"].nunique() > 1).any():
        raise ValueError("Hay personas con imágenes de dos grupos")
    rng = np.random.default_rng(seed)
    test = []
    for group in [g for g in GROUPS if g in set(table["group"])]:
        cands = group_candidates(table, group, n_test)
        if not cands:
            raise ValueError(f"Ninguna partición válida para el grupo {group}")
        test.extend(cands[rng.integers(len(cands))])
    out = table.copy()
    out["set"] = np.where(out["person"].isin(test), "test", "dev")
    return out


def person_folds(table: pd.DataFrame, k: int = 5, seed: int = SEED) -> pd.Series:
    """Grupos de validación cruzada por persona, repartiendo los grupos clínicos.

    `table` necesita las columnas person y group. Dentro de cada grupo clínico
    las personas se mezclan con `seed` y se reparten en ronda entre los `k`
    grupos, siguiendo la ronda de un grupo clínico al siguiente para que los
    tamaños queden parejos. Devuelve el número de grupo (0 a k-1) de cada
    persona, indexado por persona. Las dos imágenes de una persona siempre
    quedan juntas.
    """
    rng = np.random.default_rng(seed)
    persons = table.drop_duplicates("person").set_index("person")["group"]
    fold, turn = {}, 0
    for group in [g for g in GROUPS if g in set(persons)]:
        members = sorted(persons[persons == group].index)
        for p in rng.permutation(members):
            fold[p] = turn % k
            turn += 1
    return pd.Series(fold, name="fold").sort_index()

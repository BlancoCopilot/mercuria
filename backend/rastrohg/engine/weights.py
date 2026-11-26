"""Peso efectivo de un dato: confianza de la fuente × decaimiento por antigüedad.

Un dato de sedimento de 1995 no dice lo mismo sobre hoy que uno de 2026: la minería
cambió. peso = confianza × 0,5^(años / vida_media). La vida media es por matriz
(params.yaml): el agua refleja la actividad actual; el sedimento integra décadas.
"""
from __future__ import annotations

from datetime import date


def age_factor(sampled_on: date | None, half_life_years: float, today: date | None = None) -> float:
    if sampled_on is None or not half_life_years:
        return 1.0
    years = max(0.0, ((today or date.today()) - sampled_on).days / 365.25)
    return 0.5 ** (years / half_life_years)


SEASON_CODE = {"humeda": 0.5, "seca": -0.5}

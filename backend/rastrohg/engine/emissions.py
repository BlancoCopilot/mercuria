"""Módulo 2a: mercurio liberado por sitio minero.

Hg (kg/año) = área activa × rendimiento de oro × razón Hg:Au × factor de actividad.
Se propaga la incertidumbre por Monte Carlo: el resultado siempre es un rango
(p05–p95), nunca un número solo.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class SiteInput:
    site_id: int
    area_ha: float
    activo: bool = True
    mezcla_tecnicas: dict[str, float] | None = None  # None => mezcla por defecto
    confianza: float = 1.0                           # 1 satélite, 0.2 denuncia


@dataclass
class EmissionResult:
    site_id: int
    hg_total_p05: float
    hg_total_p50: float
    hg_total_p95: float
    hg_agua_p05: float
    hg_agua_p50: float
    hg_agua_p95: float
    hg_agua_media: float
    detalle: dict = field(default_factory=dict)


def _rng_for(site_id: int) -> np.random.Generator:
    # Semilla fija por sitio: recalcular no cambia el resultado si no cambian los datos.
    return np.random.default_rng(1_000_003 * int(site_id) + 17)


def estimate_site(site: SiteInput, cfg: dict) -> EmissionResult:
    e = cfg["emisiones"]
    n = int(e["muestras_monte_carlo"])
    rng = _rng_for(site.site_id)

    rend = e["rendimiento_au_g_ha_anio"]
    yield_g = rng.lognormal(np.log(rend["mediana"]), np.log(rend["gsd"]), n)

    mezcla = site.mezcla_tecnicas or e["mezcla_tecnicas_default"]
    total_w = sum(mezcla.values())
    ratio = np.zeros(n)
    for tecnica, w in mezcla.items():
        t = e["razon_hg_au"][tecnica]
        ratio += (w / total_w) * rng.triangular(t["min"], t["moda"], t["max"], n)

    actividad = 1.0 if site.activo else float(e["factor_inactivo"])
    au_kg = site.area_ha * yield_g / 1000.0
    hg_total = au_kg * ratio * actividad

    fa = e["fraccion_a_agua"]
    frac_agua = rng.beta(fa["a"], fa["b"], n)
    hg_agua = hg_total * frac_agua

    q = lambda x, p: float(np.percentile(x, p))  # noqa: E731
    return EmissionResult(
        site_id=site.site_id,
        hg_total_p05=q(hg_total, 5), hg_total_p50=q(hg_total, 50), hg_total_p95=q(hg_total, 95),
        hg_agua_p05=q(hg_agua, 5), hg_agua_p50=q(hg_agua, 50), hg_agua_p95=q(hg_agua, 95),
        hg_agua_media=float(hg_agua.mean()),
        detalle={
            "area_ha": site.area_ha,
            "activo": site.activo,
            "mezcla_tecnicas": mezcla,
            "au_kg_anio_p50": q(au_kg, 50),
            "n_muestras": n,
        },
    )

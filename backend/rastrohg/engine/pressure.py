"""Módulo 2b (parte 1): presión minera río arriba de cada tramo.

P(tramo) = Σ_sitios confianza × Hg_agua(sitio) × exp(−distancia río abajo / L)

Usamos el Hg liberado al agua (área × factores) en vez del área sola: es
proporcional al área pero además incorpora técnica, actividad y confianza del dato.
Un sitio solo afecta a su cadena río abajo, así que una mina nueva cambia la presión
únicamente de esos tramos.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .network import RiverNetwork


@dataclass
class SiteLoad:
    site_id: int
    reach_id: int
    hg_agua_kg: float      # media de Monte Carlo (la presión es un valor esperado)
    confianza: float


def compute_pressure(net: RiverNetwork, sites: list[SiteLoad], L_km: float,
                     cutoff_factor: float = 6.0) -> dict[int, float]:
    """Presión por tramo (kg/año equivalentes). Tramos sin minería río arriba => 0."""
    pressure = {rid: 0.0 for rid in net.ids}
    max_km = L_km * cutoff_factor  # exp(-6) ≈ 0.25 %: se corta ahí
    for s in sites:
        if s.reach_id not in net.reaches or s.hg_agua_kg <= 0:
            continue
        load = s.confianza * s.hg_agua_kg
        for rid, d in net.downstream(s.reach_id, max_km):
            pressure[rid] += load * math.exp(-d / L_km)
    return pressure


def mass_balance_concentration(load_kg_yr: float, discharge_cms: float, q_min: float = 0.05) -> float:
    """Concentración si toda la carga se diluyera en el caudal medio (µg/L).

    1 kg/año = 31,7 µg/s; 1 m³/s = 1000 L/s => 0,0317 µg/L por (kg/año)/(m³/s).
    """
    return 0.0317 * load_kg_yr / max(discharge_cms, q_min)

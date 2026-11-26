"""Consejo de consumo de pescado para la ficha "Mi comunidad".

Comidas por semana sin superar la ingesta semanal tolerable de metilmercurio:
    comidas = ISTmeHg [µg/kg/sem] × peso [kg] / (C [µg/g] × fracción_metil × porción [g])
La concentración por especie = pez de referencia (carnívoro) × factor trófico.
Se calcula para adulto y para niño; el consejo usa el caso del niño (más protector).
"""
from __future__ import annotations

import math

from .kriging import Z95


def fish_advice(pez_log_mu: float, pez_log_sd: float, especies: list[dict], cfg: dict) -> list[dict]:
    cp = cfg["consejo_pescado"]
    factores = cfg["matrices"]["pez"]["factores_troficos"]
    out = []
    for e in especies:
        f = e.get("factor", factores[e["grupo"]])    # factor propio si hay estudio local de la especie
        c50 = math.exp(pez_log_mu) * f
        c95 = math.exp(pez_log_mu + Z95 * pez_log_sd) * f
        comidas = {}
        for quien in ("adulto", "nino"):
            ug_por_comida = c50 * cp["fraccion_metil"] * cp["porcion_g"][quien]
            comidas[quien] = cp["ingesta_semanal_tolerable_ug_kg"] * cp["peso_kg"][quien] / max(ug_por_comida, 1e-9)
        n = comidas["nino"]
        consejo = "comer" if n >= 3 else ("limitar" if n >= 1 else "evitar")
        out.append({
            "codigo": e["codigo"], "nombre": e["nombre"], "grupo": e["grupo"],
            "mg_kg_p50": round(c50, 3), "mg_kg_p95": round(c95, 3),
            "comidas_semana_adulto": round(comidas["adulto"], 1),
            "comidas_semana_nino": round(comidas["nino"], 1),
            "consejo": consejo,
            **({"nota": e["nota"]} if e.get("nota") else {}),
        })
    orden = {"comer": 0, "limitar": 1, "evitar": 2}
    return sorted(out, key=lambda x: (orden[x["consejo"]], x["mg_kg_p50"]))

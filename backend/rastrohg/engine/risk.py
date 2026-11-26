"""Módulo 5: riesgo por celda H3 = media geométrica(peligro × exposición × vulnerabilidad).

* Peligro (0–1): concentración estimada en escala logarítmica, anclada en dos puntos
  de cada matriz: C ≤ fondo natural → 0, C = valor de referencia → 0,5,
  C = 10 × referencia → 1. Anclar el cero en el fondo evita que un río sin minería
  salga con peligro "medio" solo porque el pescado amazónico siempre tiene algo de Hg.
  Se toma el máximo entre matrices (cada una con su peso).
* Exposición (0–1): gente, tomas de agua y zonas de pesca en la celda (saturante).
* Vulnerabilidad (0–1): niños, mujeres en edad fértil, consumo de pescado.
* Incertidumbre: Monte Carlo sobre la concentración (lognormal del kriging).
  "confianza" = probabilidad de que la celda esté realmente en la clase mostrada.
  Si es baja, la celda se pinta pálida: "no sabemos bien".
* Semilla fija por celda: recalcular sin datos nuevos da exactamente lo mismo.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field

import numpy as np

CLASES = ("bajo", "medio", "alto")


@dataclass
class HazardSource:
    matrix: str
    reach_id: int
    log_mu: float
    log_sd: float
    decay: float = 1.0       # < 1 si el tramo está en una celda vecina


@dataclass
class CellInput:
    h3: str
    exposure: float
    vulnerability: float
    sources: list[HazardSource] = field(default_factory=list)


@dataclass
class CellRisk:
    h3: str
    hazard: float
    exposure: float
    vulnerability: float
    risk: float
    risk_class: str
    confidence: float
    p_alto: float
    palida: bool
    drivers: dict


def hazard_index(log_c: np.ndarray | float, ref: float, fondo: float) -> np.ndarray | float:
    x = np.asarray(log_c, dtype=float)
    lr, lf = math.log(ref), math.log(fondo)
    bajo = 0.5 * (x - lf) / (lr - lf)                 # entre fondo y referencia
    alto = 0.5 + 0.5 * (x - lr) / math.log(10)        # por encima de la referencia
    return np.clip(np.where(x <= lr, bajo, alto), 0.0, 1.0)


def exposure_index(poblacion: float, n_tomas: int, n_pesca: int, cfg: dict) -> float:
    e = cfg["riesgo"]["exposicion"]
    s = poblacion / e["poblacion_ref"] + e["peso_toma_agua"] * n_tomas + e["peso_zona_pesca"] * n_pesca
    return float(1.0 - math.exp(-s))


def vulnerability_index(poblacion: float, ninos_u5: float, mujeres_15_49: float,
                        comidas_pescado_semana: float | None, cfg: dict) -> float:
    v = cfg["riesgo"]["vulnerabilidad"]
    comidas = v["comidas_pescado_default"] if comidas_pescado_semana is None else comidas_pescado_semana
    if poblacion > 0:
        f_ninos = min(1.0, (ninos_u5 / poblacion) / v["ref_ninos"])
        f_mujeres = min(1.0, (mujeres_15_49 / poblacion) / v["ref_mujeres_fertiles"])
    else:
        f_ninos = f_mujeres = 0.5   # sin censo: valor intermedio, no cero
    f_pescado = min(1.0, comidas / v["ref_comidas_pescado_semana"])
    base = (f_ninos + f_mujeres + f_pescado) / 3.0
    return float(v["piso"] + (1.0 - v["piso"]) * base)


def classify(r: np.ndarray | float, cfg: dict) -> np.ndarray:
    u = cfg["riesgo"]["umbrales"]
    return np.where(np.asarray(r) >= u["alto"], 2, np.where(np.asarray(r) >= u["medio"], 1, 0))


def _seed(h3: str) -> int:
    return int.from_bytes(hashlib.sha256(h3.encode()).digest()[:8], "little")


def compute_cell(ci: CellInput, cfg: dict) -> CellRisk:
    rc = cfg["riesgo"]
    n = int(rc["muestras_mc"])
    rng = np.random.default_rng(_seed(ci.h3))
    H_samples = np.zeros(n)
    H_point = 0.0
    drivers: dict = {}
    for s in ci.sources:
        w = rc["pesos_peligro"][s.matrix]
        ref = cfg["matrices"][s.matrix]["referencia"]
        fondo = cfg["matrices"][s.matrix]["fondo"]
        shift = math.log(max(s.decay, 1e-9))
        h_pt = w * float(hazard_index(s.log_mu + shift, ref, fondo))
        z = rng.standard_normal(n)
        H_samples = np.maximum(H_samples, w * hazard_index(s.log_mu + s.log_sd * z + shift, ref, fondo))
        if h_pt >= H_point:
            H_point = h_pt
        drivers[s.matrix] = {"reach_id": s.reach_id, "peligro": round(h_pt, 3),
                             "mediana": math.exp(s.log_mu), "unidad": cfg["matrices"][s.matrix]["unidad"]}

    EV = ci.exposure * ci.vulnerability
    risk_point = (H_point * EV) ** (1 / 3)
    R_samples = np.cbrt(H_samples * EV)
    cls_point = int(classify(risk_point, cfg))
    cls_samples = classify(R_samples, cfg)
    confidence = float(np.mean(cls_samples == cls_point))
    return CellRisk(
        h3=ci.h3,
        hazard=round(H_point, 4),
        exposure=round(ci.exposure, 4),
        vulnerability=round(ci.vulnerability, 4),
        risk=round(float(risk_point), 4),
        risk_class=CLASES[cls_point],
        confidence=round(confidence, 3),
        p_alto=round(float(np.mean(cls_samples == 2)), 3),
        palida=confidence < rc["confianza_palida"],
        drivers=drivers,
    )


def best_source_per_matrix(sources: list[HazardSource]) -> list[HazardSource]:
    """De todos los tramos que tocan la celda (y vecinas), el más peligroso por matriz."""
    best: dict[str, HazardSource] = {}
    for s in sources:
        score = s.log_mu + math.log(max(s.decay, 1e-9))
        cur = best.get(s.matrix)
        if cur is None or score > cur.log_mu + math.log(max(cur.decay, 1e-9)):
            best[s.matrix] = s
    return list(best.values())


def changed(old: dict | None, new: CellRisk, cfg: dict) -> bool:
    if old is None:
        return True
    tol = cfg["riesgo"]["tolerancia"]
    return (old["risk_class"] != new.risk_class
            or abs(old["risk"] - new.risk) > tol["riesgo"]
            or abs(old["confidence"] - new.confidence) > tol["confianza"])

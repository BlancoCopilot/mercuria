"""Módulo 3: dónde tomar la próxima muestra de laboratorio.

Criterio: elegir el tramo cuya medición (hipotética, de laboratorio) más reduce la
varianza del mapa, ponderada por cuánta gente está expuesta a cada tramo.
En un modelo gaussiano la reducción de varianza no depende del valor que se vaya a
medir, solo de dónde se mide, así que se puede calcular antes de salir al campo:

    reducción(c) = Σ_t w_t · Cov_post(c, t)² / (Var_post(c) + ruido_lab)

Se eligen k puntos de forma voraz: tras elegir uno se agrega como observación
virtual, así el segundo no repite la información del primero.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .kriging import NetworkKriging, Observation


@dataclass
class Suggestion:
    rank: int
    reach_id: int
    reduccion_varianza: float     # fracción de la varianza ponderada total que se elimina
    var_antes: float              # varianza (log) en el punto antes de muestrear


def _posterior_cov_row(kr: NetworkKriging, V: np.ndarray, c: int, T: np.ndarray) -> np.ndarray:
    idx = kr.net.index
    ci = idx[c]
    prior = kr.X[T] @ kr.model.beta_cov @ kr.X[ci]
    pos = {t: k for k, t in enumerate(T)}
    for rj, cov in kr.net_cov_row(c).items():
        k = pos.get(idx[rj])
        if k is not None:
            prior[k] += cov
    if V.shape[0]:   # V usa la covariable de los datos (congelada) — coherente con fit()
        prior = prior - V[:, ci] @ V[:, T]
    return prior


def suggest_points(kr: NetworkKriging, candidates: list[int], target_weights: dict[int, float],
                   k: int = 3) -> list[Suggestion]:
    net = kr.net
    candidates = [c for c in candidates if c in net.reaches]
    T = np.array(sorted(net.index[r] for r, w in target_weights.items() if w > 0 and r in net.reaches))
    if len(T) == 0 or not candidates:
        return []
    w = np.array([target_weights[net.ids[t]] for t in T])
    original = list(getattr(kr, "obs", []))
    obs = list(original)
    kr.fit(obs)
    total0 = float((w * np.square(kr.predict().log_sd[T])).sum())

    picks: list[Suggestion] = []
    chosen: set[int] = set()
    for rank in range(1, k + 1):
        V = kr.whitened_cross()
        sd = kr.predict().log_sd
        best_c, best_s = None, -1.0
        for c in candidates:
            if c in chosen:
                continue
            row = _posterior_cov_row(kr, V, c, T)
            var_c = float(sd[net.index[c]] ** 2)
            s = float((w * np.square(row)).sum() / (var_c + kr.model.obs_noise(1.0)))
            if s > best_s:
                best_c, best_s = c, s
        if best_c is None:
            break
        picks.append(Suggestion(rank, best_c, best_s / total0 if total0 > 0 else 0.0,
                                float(sd[net.index[best_c]] ** 2)))
        chosen.add(best_c)
        obs.append(Observation(best_c, 1.0, 1.0))   # valor irrelevante para la varianza
        kr.fit(obs)
    kr.fit(original)   # deja el modelo como estaba (sin observaciones virtuales)
    return picks

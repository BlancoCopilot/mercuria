"""Módulo 2b (parte 2): concentración por tramo con kriging de regresión en red fluvial.

Modelo (escala log, uno por matriz: agua, sedimento, pez — nunca se mezclan):

    ln C(tramo) = β0 + β1·u(tramo) + η(tramo) + ε

* u: covariable de presión minera (0 si no hay minería río arriba).
* β ~ Normal(prior): con 0 datos el mapa sale del prior físico (fondo + balance de
  masa) con mucha incertidumbre; con datos, β se calibra solo (regresión bayesiana).
* η: residuo espacial con covarianza "tail-up" en la red: solo hay correlación entre
  tramos conectados por el flujo, decae con la distancia a lo largo del río y se
  pondera por la razón de áreas de cuenca. Dos tributarios vecinos pero separados
  NO se influyen, cosa que el kriging euclidiano (pykrige) sí haría.
* ε: error de medición por dato = ruido_lab / peso (laboratorio 1, kit 0,5...).
* Bajo el límite de detección (LD): el dato solo dice "C < LD". Si el LD está por
  encima de lo que el modelo ya espera (p84 a priori), no aporta nada y se ignora. Si
  no, se usa la media de la distribución a priori truncada en LD, con su varianza
  (aproximación tobit de un paso). Antes se usaba LD/2, que con un LD alto (1 µg/L)
  hacía ver contaminado un río limpio.
* Estación (solo si la matriz tiene `efecto_estacion`): columna s = +0,5 húmeda,
  −0,5 seca, 0 desconocida. El mapa se predice en s = 0 (promedio geométrico entre
  temporadas); un dato sin estación conocida lleva ruido extra (β_est/2)².
* Calibración congelada: la covariable u de cada medición se fija al calibrar (cuando
  llegan mediciones). Si luego solo aparece una mina, las mediciones no se
  "reinterpretan": cambian exactamente los tramos río abajo de la mina, nada más.
  pykrige no permite un error distinto por punto; por eso el kriging está escrito
  aquí con numpy (~100 líneas, auditable).

La predicción y su varianza salen de un solo sistema gaussiano: siempre hay
incertidumbre (p05–p95).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.linalg import cho_factor, cho_solve, solve_triangular
from scipy.stats import norm

from .network import RiverNetwork
from .pressure import mass_balance_concentration

Z95 = 1.6449


@dataclass
class Observation:
    reach_id: int
    value: float             # unidad canónica de la matriz (>0)
    weight: float = 1.0      # confianza de la fuente
    below_dl: bool = False   # bajo límite de detección: value = LD, se usa LD/2
    u: float | None = None   # covariable congelada en la última calibración (None = la actual)
    s: float | None = None   # estación: +0.5 húmeda, -0.5 seca, None desconocida


@dataclass
class MatrixModel:
    name: str
    sigma2: float
    range_km: float
    noise_lab: float
    beta_mean: np.ndarray
    beta_cov: np.ndarray
    nugget: float = 0.0      # variabilidad temporal/de método entre muestras del mismo tramo (log)

    @property
    def seasonal(self) -> bool:
        return len(self.beta_mean) == 3

    @classmethod
    def from_cfg(cls, name: str, cfg: dict) -> "MatrixModel":
        m = cfg["matrices"][name]
        bp = m["beta_prior"]
        mean, sd = list(bp["media"]), list(bp["sd"])
        if "efecto_estacion" in m:   # factor húmeda/seca, en log
            mean.append(math.log(m["efecto_estacion"]["factor"]))
            sd.append(m["efecto_estacion"]["sd_log"])
        return cls(
            name=name,
            sigma2=float(m["sigma2"]),
            range_km=float(m["rango_km"]),
            noise_lab=float(m["ruido_lab"]),
            beta_mean=np.array(mean, dtype=float),
            beta_cov=np.diag(np.square(np.array(sd, dtype=float))),
            nugget=float(m.get("nugget", 0.0)),
        )

    def obs_noise(self, weight: float) -> float:
        """Varianza de un dato: (laboratorio + variabilidad temporal) / peso."""
        return (self.noise_lab + self.nugget) / weight


def covariate(matrix_cfg: dict, pressure_kg: float, discharge_cms: float) -> float:
    if matrix_cfg["covariable"] == "balance_masa":
        c_mb = mass_balance_concentration(pressure_kg, discharge_cms)
        return math.log1p(matrix_cfg["k_columna_agua"] * c_mb / matrix_cfg["fondo"])
    return math.log1p(pressure_kg / matrix_cfg["presion_ref_kg"])


def design_matrix(net: RiverNetwork, pressure: dict[int, float], matrix_cfg: dict) -> np.ndarray:
    """X en el orden de net.ids: [1, u] (+ columna de estación = 0 si la matriz es estacional)."""
    X = np.ones((len(net.ids), 3 if "efecto_estacion" in matrix_cfg else 2))
    if X.shape[1] == 3:
        X[:, 2] = 0.0
    for i, rid in enumerate(net.ids):
        X[i, 1] = covariate(matrix_cfg, pressure.get(rid, 0.0), net.reaches[rid].dis_av_cms)
    return X


@dataclass
class Prediction:
    reach_ids: list[int]
    log_mu: np.ndarray
    log_sd: np.ndarray
    n_cercanos: np.ndarray   # datos conectados por el flujo dentro del rango

    def quantiles(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        return (np.exp(self.log_mu - Z95 * self.log_sd),
                np.exp(self.log_mu),
                np.exp(self.log_mu + Z95 * self.log_sd))


class NetworkKriging:
    def __init__(self, net: RiverNetwork, model: MatrixModel, X: np.ndarray):
        self.net = net
        self.model = model
        self.X = X
        self.cutoff_km = 4.0 * model.range_km
        self._fitted = False

    # ---- covarianza en red -------------------------------------------------
    def net_cov_row(self, rid: int) -> dict[int, float]:
        """Covarianza tail-up de rid con todos los tramos conectados (dispersa)."""
        m = self.model
        a_i = max(self.net.reaches[rid].upland_skm, 1e-6)
        row = {}
        for rj, d in self.net.flow_connected(rid, self.cutoff_km).items():
            a_j = max(self.net.reaches[rj].upland_skm, 1e-6)
            w = math.sqrt(min(a_i, a_j) / max(a_i, a_j))
            row[rj] = m.sigma2 * w * math.exp(-d / m.range_km)
        return row

    def _cols(self, reach_ids: list[int], Xd: np.ndarray) -> np.ndarray:
        """Covarianza total (β + red) entre todos los tramos (N) y reach_ids (n)."""
        idx = self.net.index
        K = self.X @ self.model.beta_cov @ Xd.T
        for j, r in enumerate(reach_ids):
            for rj, c in self.net_cov_row(r).items():
                K[idx[rj], j] += c
        return K

    # ---- ajuste -------------------------------------------------------------
    def _data_rows(self, obs: list[Observation]) -> np.ndarray:
        Xd = self.X[[self.net.index[o.reach_id] for o in obs]].copy()
        for j, o in enumerate(obs):
            if o.u is not None:
                Xd[j, 1] = o.u
            if self.model.seasonal:
                Xd[j, 2] = o.s or 0.0
        return Xd

    def fit(self, obs: list[Observation]) -> "NetworkKriging":
        m = self.model
        obs = [o for o in obs if o.reach_id in self.net.reaches and o.value > 0 and o.weight > 0]
        Xd = self._data_rows(obs) if obs else np.zeros((0, len(m.beta_mean)))
        y, noise, keep = [], [], []
        self.n_censurados_ignorados = 0
        for j, o in enumerate(obs):
            nz = m.obs_noise(o.weight)
            if m.seasonal and o.s is None:
                nz += (m.beta_mean[2] / 2) ** 2          # no sabemos en qué temporada se midió
            if o.below_dl:
                x = Xd[j]
                mu_p = float(x @ m.beta_mean)
                sd_p = math.sqrt(float(x @ m.beta_cov @ x) + m.sigma2 + nz)
                a = (math.log(o.value) - mu_p) / sd_p
                if a > 1.0:                                # LD por encima del p84: no informa
                    self.n_censurados_ignorados += 1
                    continue
                lam = norm.pdf(a) / max(norm.cdf(a), 1e-12)
                y.append(mu_p - sd_p * lam)
                noise.append(max(sd_p ** 2 * (1 - a * lam - lam ** 2), nz))
            else:
                y.append(math.log(o.value))
                noise.append(nz)
            keep.append(j)
        obs = [obs[j] for j in keep]
        Xd = Xd[keep] if keep else np.zeros((0, len(m.beta_mean)))
        self.obs = obs
        self.d_reaches = [o.reach_id for o in obs]
        n = len(obs)
        self.Xd = Xd
        if n == 0:
            self._fitted = True
            self.Kstar = np.zeros((len(self.net.ids), 0))
            return self
        self.Kstar = self._cols(self.d_reaches, Xd)      # N × n
        A = Xd @ m.beta_cov @ Xd.T + np.diag(noise) + 1e-9 * np.eye(n)
        for j, r in enumerate(self.d_reaches):
            row = self.net_cov_row(r)
            for k, r2 in enumerate(self.d_reaches):
                A[j, k] += row.get(r2, 0.0)
        self.chol = cho_factor(A, lower=True)
        self.resid = np.array(y) - Xd @ m.beta_mean
        self.alpha = cho_solve(self.chol, self.resid)
        self._fitted = True
        return self

    def log_marginal_likelihood(self) -> float:
        n = len(self.obs)
        if n == 0:
            return 0.0
        L = self.chol[0]
        return float(-0.5 * self.resid @ self.alpha - np.log(np.diag(L)).sum() - 0.5 * n * math.log(2 * math.pi))

    # ---- predicción ---------------------------------------------------------
    def prior_var(self) -> np.ndarray:
        return np.einsum("ij,jk,ik->i", self.X, self.model.beta_cov, self.X) + self.model.sigma2

    def predict(self) -> Prediction:
        assert self._fitted, "llamar fit() primero"
        mu = self.X @ self.model.beta_mean
        var = self.prior_var()
        n = len(self.d_reaches)
        n_cerca = np.zeros(len(self.net.ids), dtype=int)
        if n:
            mu = mu + self.Kstar @ self.alpha
            V = solve_triangular(self.chol[0], self.Kstar.T, lower=True)   # n × N
            var = var - np.square(V).sum(axis=0)
            idx = self.net.index
            for r in self.d_reaches:
                for rj, d in self.net.flow_connected(r, self.model.range_km).items():
                    n_cerca[idx[rj]] += 1
        var = np.maximum(var, 1e-6)
        return Prediction(list(self.net.ids), mu, np.sqrt(var), n_cerca)

    def whitened_cross(self) -> np.ndarray:
        """V = L⁻¹ K(d, ·): sirve para la covarianza a posteriori en el muestreo."""
        if not self.d_reaches:
            return np.zeros((0, len(self.net.ids)))
        return solve_triangular(self.chol[0], self.Kstar.T, lower=True)


def fit_hyperparameters(net: RiverNetwork, base: MatrixModel, X: np.ndarray,
                        obs: list[Observation], cfg: dict) -> MatrixModel:
    """Búsqueda en grilla por verosimilitud marginal; solo si hay suficientes datos."""
    aj = cfg["ajuste"]
    # cuentan solo los datos que el modelo realmente usa (no los censurados no informativos)
    usados = len(NetworkKriging(net, base, X).fit(obs).obs) if len(obs) >= aj["min_datos_para_ajustar"] else 0
    if usados < aj["min_datos_para_ajustar"]:
        return base
    best, best_ll = base, -np.inf
    for rng_km in aj["rangos_km"]:
        for s2 in aj["sigma2"]:
            for nug in aj.get("nugget", [base.nugget]):
                cand = MatrixModel(base.name, s2, rng_km, base.noise_lab, base.beta_mean, base.beta_cov, nug)
                ll = NetworkKriging(net, cand, X).fit(obs).log_marginal_likelihood()
                if ll > best_ll:
                    best, best_ll = cand, ll
    return best

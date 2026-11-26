"""Pipeline de recálculo: base de datos -> motor -> nueva versión del mapa.

Flujo (un solo trabajo, en serie):
  1. Refresca exposición/vulnerabilidad por celda (censo, OSM, encuestas de pescado).
  2. Emisiones por sitio (Monte Carlo, semilla fija).
  3. Por matriz: presión río abajo -> kriging en red -> estimación por tramo.
  4. Riesgo por celda H3.
  5. Compara con lo vigente y guarda SOLO lo que cambió (tolerancias en params.yaml).
     Una mina nueva solo cambia la presión de su cadena río abajo, así que en la
     práctica solo cambian esos tramos y sus celdas. Calcular todo en memoria cuesta
     segundos en una cuenca piloto; lo caro (escrituras, versiones, alertas, descargas
     del teléfono) se limita a lo que cambió.
  6. Si algo cambió: nueva versión, alertas por cambio de nivel y cola de push.
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

import h3
import numpy as np
from sqlalchemy import Connection, text

from ..db import execute, one, rows, tx
from ..engine import emissions, kriging, risk
from ..engine.network import Reach, RiverNetwork
from ..engine.params import MATRICES, params, params_hash
from ..engine.pressure import SiteLoad, compute_pressure

log = logging.getLogger(__name__)

DEFAULT_POP_BY_KIND = {"city": 20000, "town": 2000, "village": 300, "hamlet": 60, "isolated_dwelling": 8}


# ---------------------------------------------------------------------------
# Carga desde la base
# ---------------------------------------------------------------------------
def load_network(conn: Connection) -> RiverNetwork:
    rs = rows(conn, "SELECT hyriv_id, next_down, length_km, upland_skm, dis_av_cms FROM river_reach")
    return RiverNetwork([Reach(int(r["hyriv_id"]), int(r["next_down"]), float(r["length_km"]),
                               float(r["upland_skm"]), float(r["dis_av_cms"])) for r in rs])


def refresh_cell_inputs(conn: Connection, cfg: dict) -> None:
    kinds = " ".join(f"WHEN '{k}' THEN {v}" for k, v in DEFAULT_POP_BY_KIND.items())
    data = rows(conn, f"""
        WITH s AS (
            SELECT h3,
                   sum(coalesce(poblacion, CASE kind {kinds} ELSE 50 END)) AS pob,
                   sum(coalesce(ninos_u5, 0))      AS ninos,
                   sum(coalesce(mujeres_15_49, 0)) AS mujeres,
                   bool_and(ninos_u5 IS NOT NULL)  AS con_censo
            FROM settlement GROUP BY h3),
        e AS (
            SELECT h3, count(*) FILTER (WHERE kind = 'toma_agua')  AS tomas,
                       count(*) FILTER (WHERE kind = 'zona_pesca') AS pesca
            FROM exposure_feature GROUP BY h3),
        f AS (SELECT h3, avg(comidas_semana) AS comidas FROM fish_survey GROUP BY h3)
        SELECT c.h3, coalesce(s.pob, 0) AS pob, coalesce(s.ninos, 0) AS ninos,
               coalesce(s.mujeres, 0) AS mujeres, coalesce(s.con_censo, false) AS con_censo,
               coalesce(e.tomas, 0) AS tomas, coalesce(e.pesca, 0) AS pesca, f.comidas
        FROM h3_cell c LEFT JOIN s USING (h3) LEFT JOIN e USING (h3) LEFT JOIN f USING (h3)""")
    updates = []
    for d in data:
        pob = float(d["pob"])
        E = risk.exposure_index(pob, d["tomas"], d["pesca"], cfg)
        # sin datos de censo: vulnerabilidad intermedia (no se asume cero)
        V = risk.vulnerability_index(pob if d["con_censo"] else 0, d["ninos"], d["mujeres"],
                                     None if d["comidas"] is None else float(d["comidas"]), cfg)
        updates.append({"h3": d["h3"], "pob": int(pob), "ninos": int(d["ninos"]), "mujeres": int(d["mujeres"]),
                        "comidas": d["comidas"], "tomas": d["tomas"], "pesca": d["pesca"], "e": E, "v": V})
    if updates:
        conn.execute(text("""
            UPDATE h3_cell SET poblacion=:pob, ninos_u5=:ninos, mujeres_15_49=:mujeres,
                   comidas_pescado_semana=:comidas, n_tomas_agua=:tomas, n_zonas_pesca=:pesca,
                   exposure=:e, vulnerability=:v
            WHERE h3=:h3"""), updates)


def update_emissions(conn: Connection, cfg: dict, ph: str) -> list[SiteLoad]:
    years = cfg["emisiones"]["anios_actividad"]
    limite = date.today() - timedelta(days=365 * years)
    sites = rows(conn, """
        SELECT id, area_ha, last_detected, confianza, mezcla_tecnicas, reach_id, status
        FROM mining_site WHERE status <> 'descartado' AND reach_id IS NOT NULL""")
    loads, upserts, status_changes = [], [], []
    for s in sites:
        activo = s["last_detected"] is None or s["last_detected"] >= limite
        if (s["status"] == "activo") != activo:
            status_changes.append({"id": s["id"], "st": "activo" if activo else "inactivo"})
        res = emissions.estimate_site(emissions.SiteInput(
            s["id"], float(s["area_ha"]), activo, s["mezcla_tecnicas"], float(s["confianza"])), cfg)
        upserts.append({"id": s["id"], **{k: getattr(res, k) for k in (
            "hg_total_p05", "hg_total_p50", "hg_total_p95", "hg_agua_p05", "hg_agua_p50",
            "hg_agua_p95", "hg_agua_media")}, "detalle": _json(res.detalle), "ph": ph})
        loads.append(SiteLoad(s["id"], int(s["reach_id"]), res.hg_agua_media, float(s["confianza"])))
    if status_changes:
        conn.execute(text("UPDATE mining_site SET status=:st, updated_at=now() WHERE id=:id"), status_changes)
    if upserts:
        conn.execute(text("""
            INSERT INTO site_emission (site_id, hg_total_p05, hg_total_p50, hg_total_p95,
                hg_agua_p05, hg_agua_p50, hg_agua_p95, hg_agua_media, detalle, params_hash, computed_at)
            VALUES (:id, :hg_total_p05, :hg_total_p50, :hg_total_p95, :hg_agua_p05, :hg_agua_p50,
                :hg_agua_p95, :hg_agua_media, CAST(:detalle AS jsonb), :ph, now())
            ON CONFLICT (site_id) DO UPDATE SET hg_total_p05=EXCLUDED.hg_total_p05,
                hg_total_p50=EXCLUDED.hg_total_p50, hg_total_p95=EXCLUDED.hg_total_p95,
                hg_agua_p05=EXCLUDED.hg_agua_p05, hg_agua_p50=EXCLUDED.hg_agua_p50,
                hg_agua_p95=EXCLUDED.hg_agua_p95, hg_agua_media=EXCLUDED.hg_agua_media,
                detalle=EXCLUDED.detalle, params_hash=EXCLUDED.params_hash, computed_at=now()"""), upserts)
    return loads


def load_observations(conn: Connection, matrix: str, cfg: dict) -> list[kriging.Observation]:
    from ..engine.weights import SEASON_CODE, age_factor

    mcfg = cfg["matrices"][matrix]
    rs = rows(conn, """
        SELECT id, reach_id, value, weight, below_dl, fish_group, hg_species, covariate_u, season,
               coalesce(sampled_on, created_at::date) AS fecha
        FROM measurement
        WHERE matrix = :m AND status = 'valido' AND reach_id IS NOT NULL
          AND (matrix = 'pez' OR hg_species = 'total')""", m=matrix)
    obs = []
    for r in rs:
        v = float(r["value"])
        if matrix == "pez":
            # todo se normaliza a "pez carnívoro de referencia, Hg total"
            v /= mcfg["factores_troficos"].get(r["fish_group"] or "carnivoro", 1.0)
            if r["hg_species"] == "metil":
                v /= cfg["consejo_pescado"]["fraccion_metil"]
        w = float(r["weight"]) * age_factor(r["fecha"], mcfg.get("vida_media_anios", 0))
        o = kriging.Observation(int(r["reach_id"]), v, w, bool(r["below_dl"]), r["covariate_u"],
                                SEASON_CODE.get(r["season"]))
        o.id = r["id"]  # type: ignore[attr-defined]
        obs.append(o)
    return obs


# Disparadores que recalibran el modelo (β e hiperparámetros). Los demás (satélite,
# denuncia, encuesta, OSM) predicen con la calibración vigente => una mina nueva solo
# cambia su cadena río abajo.
RECALIBRA = {"medicion", "medicion_revisada", "manual", "cli", "cron", "inicial_sintetico"}


def calibrate(conn: Connection, obs: list[kriging.Observation], X: np.ndarray, net: RiverNetwork) -> None:
    ups = []
    for o in obs:
        o.u = float(X[net.index[o.reach_id], 1])
        ups.append({"id": o.id, "u": o.u})  # type: ignore[attr-defined]
    if ups:
        conn.execute(text("UPDATE measurement SET covariate_u=:u, calibrated_at=now() WHERE id=:id"), ups)


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------
@dataclass
class MatrixState:
    pressure: dict[int, float]
    kr: kriging.NetworkKriging
    pred: kriging.Prediction
    n_obs: int


def build_models(conn: Connection, cfg: dict, net: RiverNetwork, loads: list[SiteLoad],
                 recalibrar: bool = False) -> dict[str, MatrixState]:
    out = {}
    for m in MATRICES:
        mcfg = cfg["matrices"][m]
        P = compute_pressure(net, loads, mcfg["decaimiento_L_km"])
        X = kriging.design_matrix(net, P, mcfg)
        obs = load_observations(conn, m, cfg)
        if recalibrar or any(o.u is None for o in obs):
            calibrate(conn, obs, X, net)
        model = kriging.fit_hyperparameters(net, kriging.MatrixModel.from_cfg(m, cfg), X, obs, cfg)
        kr = kriging.NetworkKriging(net, model, X).fit(obs)
        out[m] = MatrixState(P, kr, kr.predict(), len(obs))
    return out


def _write_pressure(conn: Connection, matrix: str, P: dict[int, float]) -> int:
    old = {r["reach_id"]: r["pressure"] for r in rows(
        conn, "SELECT reach_id, pressure FROM reach_pressure WHERE matrix=:m", m=matrix)}
    ups = [{"r": rid, "m": matrix, "p": p} for rid, p in P.items()
           if abs(old.get(rid, -1.0) - p) > 1e-9 * (1 + abs(p))]
    if ups:
        conn.execute(text("""INSERT INTO reach_pressure (reach_id, matrix, pressure) VALUES (:r, :m, :p)
                             ON CONFLICT (reach_id, matrix) DO UPDATE SET pressure = EXCLUDED.pressure"""), ups)
    return len(ups)


def compute_cells(conn: Connection, cfg: dict, states: dict[str, MatrixState]) -> list[risk.CellRisk]:
    rc = cfg["riesgo"]
    cell_reaches: dict[str, list[int]] = defaultdict(list)
    for r in rows(conn, "SELECT reach_id, h3 FROM reach_cell"):
        cell_reaches[r["h3"]].append(int(r["reach_id"]))
    est = {}
    for m, st in states.items():
        idx = st.kr.net.index
        est[m] = {rid: (float(st.pred.log_mu[i]), float(st.pred.log_sd[i])) for rid, i in idx.items()}
    out = []
    for c in rows(conn, "SELECT h3, exposure, vulnerability FROM h3_cell"):
        sources = []
        for k in range(rc["anillos_peligro"] + 1):
            decay = rc["decaimiento_anillo"] ** k
            for nb in ([c["h3"]] if k == 0 else h3.grid_ring(c["h3"], k)):
                for rid in cell_reaches.get(nb, ()):
                    for m in MATRICES:
                        if rid in est[m]:
                            mu, sd = est[m][rid]
                            sources.append(risk.HazardSource(m, rid, mu, sd, decay))
        ci = risk.CellInput(c["h3"], float(c["exposure"]), float(c["vulnerability"]),
                            risk.best_source_per_matrix(sources))
        out.append(risk.compute_cell(ci, cfg))
    return out


# ---------------------------------------------------------------------------
# Recálculo completo con escritura delta
# ---------------------------------------------------------------------------
def run_recompute(triggers: list[dict]) -> dict:
    cfg = params()
    ph = params_hash()
    tol = cfg["riesgo"]["tolerancia"]["log_mu"]
    with tx() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(4242)"))   # un recálculo a la vez, aunque haya 2 workers
        net = load_network(conn)
        if not len(net):
            return {"estado": "sin_red", "detalle": "cargue HydroRIVERS primero"}
        refresh_cell_inputs(conn, cfg)
        loads = update_emissions(conn, cfg, ph)
        recalibrar = any(t.get("tipo") in RECALIBRA for t in triggers)
        states = build_models(conn, cfg, net, loads, recalibrar)

        n_pressure = sum(_write_pressure(conn, m, st.pressure) for m, st in states.items())

        old_est = {(r["reach_id"], r["matrix"]): (r["log_mu"], r["log_sd"])
                   for r in rows(conn, "SELECT reach_id, matrix, log_mu, log_sd FROM reach_estimate")}
        est_changes = []
        for m, st in states.items():
            p05, p50, p95 = st.pred.quantiles()
            for rid, i in st.kr.net.index.items():
                mu, sd = float(st.pred.log_mu[i]), float(st.pred.log_sd[i])
                old = old_est.get((rid, m))
                if old is None or abs(old[0] - mu) > tol or abs(old[1] - sd) > tol:
                    est_changes.append({"r": rid, "m": m, "mu": mu, "sd": sd, "p05": float(p05[i]),
                                        "p50": float(p50[i]), "p95": float(p95[i]),
                                        "n": int(st.pred.n_cercanos[i])})

        cells = compute_cells(conn, cfg, states)
        old_cells = {r["h3"]: r for r in rows(conn, "SELECT h3, risk, risk_class, confidence FROM cell_risk_current")}
        cell_changes = [c for c in cells if risk.changed(old_cells.get(c.h3), c, cfg)]

        # Hay versión nueva si cambió cualquier dato del mapa (presión, estimaciones o celdas),
        # aunque ninguna celda cambie de nivel: p. ej. una denuncia pequeña río abajo de una
        # mina grande mueve la presión <1 %, pero el sitio sí aparece en el mapa.
        if not est_changes and not cell_changes and not n_pressure:
            return {"estado": "sin_cambios", "triggers": triggers}

        model_info = {m: {"n_datos": st.n_obs, "n_usados": len(st.kr.obs),
                          "censurados_ignorados": st.kr.n_censurados_ignorados,
                          "sigma2": st.kr.model.sigma2, "rango_km": st.kr.model.range_km,
                          "nugget": st.kr.model.nugget,
                          "recalibrado": recalibrar} for m, st in states.items()}
        vid = one(conn, """INSERT INTO map_version (triggers, reaches_changed, cells_changed, params_hash, model_info)
                           VALUES (CAST(:t AS jsonb), :rc, :cc, :ph, CAST(:mi AS jsonb)) RETURNING id""",
                  t=_json(triggers), rc=len({(e["r"]) for e in est_changes}), cc=len(cell_changes),
                  ph=ph, mi=_json(model_info))["id"]

        if est_changes:
            conn.execute(text("""
                INSERT INTO reach_estimate (reach_id, matrix, log_mu, log_sd, p05, p50, p95, n_cercanos, version_id)
                VALUES (:r, :m, :mu, :sd, :p05, :p50, :p95, :n, :v)
                ON CONFLICT (reach_id, matrix) DO UPDATE SET log_mu=EXCLUDED.log_mu, log_sd=EXCLUDED.log_sd,
                    p05=EXCLUDED.p05, p50=EXCLUDED.p50, p95=EXCLUDED.p95, n_cercanos=EXCLUDED.n_cercanos,
                    version_id=EXCLUDED.version_id"""), [{**e, "v": vid} for e in est_changes])

        alerts = []
        if cell_changes:
            conn.execute(text("""
                INSERT INTO cell_risk (h3, version_id, hazard, exposure, vulnerability, risk, risk_class,
                                       confidence, p_alto, palida, drivers)
                VALUES (:h3, :v, :hazard, :exposure, :vulnerability, :risk, :risk_class, :confidence,
                        :p_alto, :palida, CAST(:drivers AS jsonb))"""),
                [{**c.__dict__, "v": vid, "drivers": _json(c.drivers)} for c in cell_changes])
            for c in cell_changes:
                old = old_cells.get(c.h3)
                if old is not None and old["risk_class"] != c.risk_class:   # versión inicial: sin alertas
                    alerts.append({"v": vid, "h3": c.h3, "o": old["risk_class"], "n": c.risk_class})
        if alerts:
            conn.execute(text("INSERT INTO alert (version_id, h3, old_class, new_class) VALUES (:v, :h3, :o, :n)"), alerts)
            execute(conn, """
                INSERT INTO push_outbox (device_id, alert_id, title, body, data)
                SELECT ds.device_id, a.id, 'Aviso RastroHg: mercurio en tu zona',
                       'El nivel de riesgo cambió de ' || coalesce(a.old_class, '-') || ' a ' || upper(a.new_class)
                       || '. Abre RastroHg para ver qué hacer.',
                       jsonb_build_object('h3', a.h3, 'version', a.version_id, 'nivel', a.new_class)
                FROM alert a
                JOIN device_subscription ds ON ds.h3 = a.h3
                JOIN device d ON d.id = ds.device_id
                WHERE a.version_id = :v AND d.push_token IS NOT NULL AND NOT d.banned""", v=vid)

    summary = {"estado": "nueva_version", "version": vid, "tramos_cambiados": len({e["r"] for e in est_changes}),
               "presion_cambiada": n_pressure,
               "celdas_cambiadas": len(cell_changes), "alertas": len(alerts), "triggers": triggers,
               "modelos": model_info}
    log.info("recompute %s", summary)
    return summary


# ---------------------------------------------------------------------------
# Sugerencia de muestreo (módulo 3)
# ---------------------------------------------------------------------------
def run_sampling(matrix: str = "agua", k: int | None = None) -> dict:
    from ..engine.sampling import suggest_points

    cfg = params()
    k = k or cfg["muestreo"]["k_default"]
    with tx() as conn:
        net = load_network(conn)
        vid = one(conn, "SELECT max(id) AS v FROM map_version")["v"]
        if not len(net):
            return {"estado": "sin_red"}
        loads = [SiteLoad(r["site_id"], int(r["reach_id"]), float(r["hg_agua_media"]), float(r["confianza"]))
                 for r in rows(conn, """SELECT e.site_id, s.reach_id, e.hg_agua_media, s.confianza
                                        FROM site_emission e JOIN mining_site s ON s.id = e.site_id
                                        WHERE s.status <> 'descartado' AND s.reach_id IS NOT NULL""")]
        mcfg = cfg["matrices"][matrix]
        P = compute_pressure(net, loads, mcfg["decaimiento_L_km"])
        X = kriging.design_matrix(net, P, mcfg)
        obs = load_observations(conn, matrix, cfg)
        model = kriging.fit_hyperparameters(net, kriging.MatrixModel.from_cfg(matrix, cfg), X, obs, cfg)
        kr = kriging.NetworkKriging(net, model, X).fit(obs)

        candidates = [int(r["hyriv_id"]) for r in rows(conn, """
            SELECT DISTINCT r.hyriv_id FROM river_reach r JOIN settlement s
              ON ST_DWithin(r.geom::geography, s.geom::geography, :d)""",
            d=cfg["muestreo"]["candidatos_max_km_a_poblado"] * 1000)]
        # peso = 1 + población de las celdas que tocan el tramo (y sus vecinas)
        pop = {r["h3"]: r["poblacion"] for r in rows(conn, "SELECT h3, poblacion FROM h3_cell")}
        weights: dict[int, float] = defaultdict(lambda: 1.0)
        for r in rows(conn, "SELECT reach_id, h3 FROM reach_cell"):
            ring = h3.grid_disk(r["h3"], 1)
            weights[int(r["reach_id"])] += sum(pop.get(c, 0) for c in ring)
        for rid in net.ids:
            weights[rid]  # todos los tramos cuentan al menos 1
        picks = suggest_points(kr, candidates, dict(weights), k=k)

        execute(conn, "DELETE FROM sampling_suggestion WHERE version_id = :v AND matrix = :m", v=vid, m=matrix)
        out = []
        for p in picks:
            row = one(conn, """
                INSERT INTO sampling_suggestion (version_id, matrix, rank, reach_id, geom, reduccion_varianza,
                                                 var_antes, nearest_settlement)
                SELECT :v, :m, :rank, r.hyriv_id, ST_LineInterpolatePoint(r.geom, 0.5), :red, :var,
                       (SELECT s.name FROM settlement s ORDER BY s.geom <-> r.geom LIMIT 1)
                FROM river_reach r WHERE r.hyriv_id = :rid
                RETURNING id, rank, reach_id, reduccion_varianza, nearest_settlement,
                          ST_Y(geom) AS lat, ST_X(geom) AS lon""",
                v=vid, m=matrix, rank=p.rank, rid=p.reach_id, red=p.reduccion_varianza, var=p.var_antes)
            out.append(row)
    return {"version": vid, "matrix": matrix, "sugerencias": out,
            "candidatos": len(candidates), "datos_existentes": len(obs)}


def _json(x) -> str:
    import json

    def default(o):
        if isinstance(o, (np.floating, np.integer)):
            return o.item()
        if isinstance(o, float) and math.isnan(o):
            return None
        return str(o)
    return json.dumps(x, default=default)

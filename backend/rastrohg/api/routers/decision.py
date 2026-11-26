"""Módulo 3 (sugerencia de muestreo) y módulo 10 (panel de decisión)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from ...db import one, rows
from ...worker.queue import enqueue
from ..deps import DbDep, require
from ..schemas import Matrix

router = APIRouter(prefix="/v1", tags=["decisión"])
Authority = Annotated[dict, Depends(require("autoridad"))]


@router.get("/sampling/suggestions")
def get_suggestions(db: DbDep, _: Authority, matrix: Matrix = "agua"):
    v = one(db.conn, "SELECT max(version_id) AS v FROM sampling_suggestion WHERE matrix=:m", m=matrix)["v"]
    sug = rows(db.conn, """
        SELECT s.rank, s.reach_id, round((s.reduccion_varianza * 100)::numeric, 1) AS reduccion_pct,
               s.nearest_settlement AS comunidad_cercana, ST_Y(s.geom) AS lat, ST_X(s.geom) AS lon,
               e.p05, e.p50, e.p95, e.n_cercanos
        FROM sampling_suggestion s LEFT JOIN reach_estimate e ON e.reach_id = s.reach_id AND e.matrix = s.matrix
        WHERE s.version_id = :v AND s.matrix = :m ORDER BY s.rank""", v=v, m=matrix)
    return {"version": v, "matrix": matrix, "sugerencias": sug,
            "explicacion": "Puntos donde una muestra de laboratorio reduce más la incertidumbre del mapa, "
                           "ponderada por la población que vive junto a cada tramo."}


@router.post("/sampling/suggestions", status_code=202)
def recompute_suggestions(_: Authority, matrix: Matrix = "agua", k: int = 3):
    return {"job_id": enqueue("rastrohg.worker.jobs.suggest_sampling", matrix, k)}


@router.get("/dashboard/summary")
def summary(db: DbDep, _: Authority):
    return one(db.conn, """
        SELECT (SELECT max(id) FROM map_version) AS version_mapa,
               (SELECT count(*) FROM mining_site WHERE status='activo') AS sitios_activos,
               (SELECT count(*) FROM mining_site WHERE status='activo' AND legal_status='sin_concesion') AS sin_concesion,
               (SELECT count(*) FROM mining_site WHERE status='activo' AND legal_status='en_area_protegida') AS en_area_protegida,
               (SELECT round(sum(hg_total_p50)::numeric, 1) FROM site_emission e JOIN mining_site s ON s.id=e.site_id
                 WHERE s.status <> 'descartado') AS hg_kg_anio_p50,
               (SELECT count(*) FROM cell_risk_current WHERE risk_class='alto') AS celdas_alto,
               (SELECT coalesce(sum(c.poblacion),0) FROM cell_risk_current r JOIN h3_cell c USING (h3)
                 WHERE r.risk_class='alto') AS personas_riesgo_alto,
               (SELECT count(*) FROM cell_risk_current WHERE palida) AS celdas_inciertas,
               (SELECT count(*) FROM measurement WHERE status='valido') AS mediciones,
               (SELECT count(*) FROM measurement WHERE is_synthetic) AS mediciones_sinteticas""")


@router.get("/dashboard/priorities")
def priorities(db: DbDep, _: Authority, limit: int = 10):
    """Zonas para campañas de salud (riesgo × gente) y para recuperación (sedimento + minería)."""
    salud = rows(db.conn, """
        SELECT r.h3, r.risk_class, r.risk, r.confidence, c.poblacion,
               round((r.risk * ln(1 + c.poblacion))::numeric, 3) AS prioridad,
               (SELECT string_agg(name, ', ') FROM settlement s WHERE s.h3 = r.h3) AS comunidades,
               (SELECT count(*) FROM health_case hc JOIN settlement s ON s.id = hc.settlement_id WHERE s.h3 = r.h3) AS casos,
               CASE WHEN r.palida THEN 'muestrear primero: incertidumbre alta' ELSE 'campaña de salud' END AS accion
        FROM cell_risk_current r JOIN h3_cell c USING (h3)
        WHERE c.poblacion > 0 AND r.risk_class <> 'bajo'
        ORDER BY prioridad DESC LIMIT :n""", n=limit)
    recuperacion = rows(db.conn, """
        SELECT e.reach_id, round(e.p50::numeric, 3) AS sedimento_mg_kg_p50, round(e.p95::numeric, 3) AS p95,
               round(p.pressure::numeric, 2) AS presion_kg_anio,
               (SELECT count(*) FROM mining_site s WHERE s.reach_id = e.reach_id AND s.status <> 'descartado') AS sitios
        FROM reach_estimate e JOIN reach_pressure p ON p.reach_id = e.reach_id AND p.matrix = e.matrix
        WHERE e.matrix = 'sedimento' AND p.pressure > 0
        ORDER BY e.p50 * ln(1 + p.pressure) DESC LIMIT :n""", n=limit)
    return {"campanas_salud": salud, "recuperacion_ecosistema": recuperacion}


@router.get("/dashboard/indicators")
def indicators(db: DbDep, _: Authority, months: int = 12):
    return rows(db.conn, """
        WITH m AS (SELECT generate_series(date_trunc('month', now()) - make_interval(months => :n - 1),
                                          date_trunc('month', now()), interval '1 month') AS mes)
        SELECT to_char(m.mes, 'YYYY-MM') AS mes,
          (SELECT count(*) FROM mining_site s WHERE date_trunc('month', s.first_detected) = m.mes) AS minas_nuevas,
          (SELECT count(*) FROM (
              SELECT DISTINCT ON (h3) risk_class FROM cell_risk cr JOIN map_version v ON v.id = cr.version_id
              WHERE v.created_at < m.mes + interval '1 month' ORDER BY h3, version_id DESC) x
           WHERE x.risk_class = 'alto') AS celdas_riesgo_alto,
          (SELECT coalesce(sum(people), 0) FROM outreach_event o WHERE date_trunc('month', o.created_at) = m.mes) AS personas_alcanzadas,
          (SELECT count(*) FROM referral r WHERE date_trunc('month', r.referred_at) = m.mes) AS casos_derivados,
          (SELECT count(*) FROM measurement me WHERE date_trunc('month', me.created_at) = m.mes) AS mediciones
        FROM m ORDER BY m.mes""", n=months)

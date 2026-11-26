"""Mapa público (sin login). Nada aquí identifica a una persona:
* riesgo por celda H3 (el teléfono dibuja las celdas con h3-js a partir del id),
* ríos con su estimación e incertidumbre, una capa por matriz,
* sitios mineros: los de satélite con polígono; los que vienen de una denuncia solo
  como celda (un polígono exacto revelaría dónde estaba quien denunció),
* denuncias: solo conteos por celda.
"""
from __future__ import annotations

import json

import h3
from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import Connection

from ...db import one, rows
from ...ingest.base import cell_of
from ..deps import DbDep
from ..schemas import Matrix

router = APIRouter(prefix="/v1/map", tags=["mapa público"])


def cells_since(conn: Connection, since: int) -> tuple[int, list[dict]]:
    version = one(conn, "SELECT max(id) AS v FROM map_version")["v"]
    cells = rows(conn, """
        SELECT DISTINCT ON (h3) h3, risk_class AS clase, round(risk::numeric, 3) AS riesgo,
               round(confidence::numeric, 2) AS confianza, palida, version_id AS version
        FROM cell_risk WHERE version_id > :s ORDER BY h3, version_id DESC""", s=since)
    return version, cells


@router.get("/version")
def version(db: DbDep):
    return one(db.conn, """SELECT id AS version, created_at, triggers, reaches_changed, cells_changed, params_hash
                           FROM map_version ORDER BY id DESC LIMIT 1""")


@router.get("/cells")
def cells(db: DbDep, response: Response, since: int = Query(0, description="versión que ya tiene el teléfono")):
    """Diferencial: solo las celdas que cambiaron después de `since` (0 = todas)."""
    v, cs = cells_since(db.conn, since)
    response.headers["X-Map-Version"] = str(v)
    return {"version": v, "desde": since, "celdas": cs}


@router.get("/cells/{cell}")
def cell_detail(cell: str, db: DbDep):
    if not h3.is_valid_cell(cell):
        raise HTTPException(400, "Celda H3 inválida")
    c = one(db.conn, "SELECT * FROM cell_risk_current WHERE h3 = :h", h=cell)
    if not c:
        raise HTTPException(404, "Sin estimación para esta celda")
    base = one(db.conn, """SELECT poblacion, n_tomas_agua, n_zonas_pesca, comidas_pescado_semana
                           FROM h3_cell WHERE h3=:h""", h=cell)
    comunidades = rows(db.conn, "SELECT id, name FROM settlement WHERE h3 = :h ORDER BY poblacion DESC NULLS LAST", h=cell)
    historial = rows(db.conn, """SELECT version_id, risk_class, risk, confidence FROM cell_risk
                                 WHERE h3=:h ORDER BY version_id""", h=cell)
    return {**c, "insumos": base, "comunidades": comunidades, "historial": historial}


@router.get("/rivers")
def rivers(db: DbDep, matrix: Matrix = "agua", since: int = 0, simplify_m: float = 50):
    """GeoJSON de tramos con mediana y rango p05–p95 (unidad canónica de la matriz)."""
    feats = rows(db.conn, """
        SELECT r.hyriv_id, r.ord_stra, e.p05, e.p50, e.p95, e.n_cercanos, e.version_id,
               coalesce(p.pressure, 0) AS presion_kg,
               ST_AsGeoJSON(ST_Simplify(r.geom, :tol), 6) AS g
        FROM reach_estimate e JOIN river_reach r ON r.hyriv_id = e.reach_id
        LEFT JOIN reach_pressure p ON p.reach_id = e.reach_id AND p.matrix = e.matrix
        WHERE e.matrix = :m AND e.version_id > :s""", m=matrix, s=since, tol=simplify_m / 111_000)
    unidad = {"agua": "ug/L", "sedimento": "mg/kg", "pez": "mg/kg (pez carnívoro de referencia)"}[matrix]
    return {"type": "FeatureCollection", "matrix": matrix, "unidad": unidad,
            "features": [{"type": "Feature", "geometry": json.loads(f.pop("g")), "properties": f} for f in feats]}


@router.get("/sites")
def sites(db: DbDep, legal_status: str | None = None):
    feats = rows(db.conn, """
        SELECT s.id, s.legal_status, s.origin, s.status, round(s.area_ha::numeric, 2) AS area_ha,
               s.first_detected, s.last_detected, s.confianza, s.is_synthetic AS sintetico,
               e.hg_total_p05, e.hg_total_p50, e.hg_total_p95,
               (SELECT p.name || ' (' || split_part(p.category, ': ', 2) || ')' FROM protected_area p
                 WHERE p.id = s.protected_area_id) AS area_protegida,
               CASE WHEN s.origin = 'denuncia' THEN NULL ELSE ST_AsGeoJSON(s.geom, 6) END AS g,
               ST_Y(ST_Centroid(s.geom)) AS lat, ST_X(ST_Centroid(s.geom)) AS lon
        FROM mining_site s LEFT JOIN site_emission e ON e.site_id = s.id
        WHERE s.status <> 'descartado' AND (CAST(:ls AS text) IS NULL OR s.legal_status = :ls)
        ORDER BY s.id""", ls=legal_status)
    out = []
    for f in feats:
        lat, lon = f.pop("lat"), f.pop("lon")
        g = f.pop("g")
        if g is None:   # denuncia: solo la celda
            c = cell_of(lat, lon)
            ring = [[lng, la] for la, lng in h3.cell_to_boundary(c)]
            geom = {"type": "Polygon", "coordinates": [ring + [ring[0]]]}
            f["h3"] = c
        else:
            geom = json.loads(g)
        out.append({"type": "Feature", "geometry": geom, "properties": f})
    return {"type": "FeatureCollection", "features": out}


@router.get("/reports")
def reports(db: DbDep):
    return rows(db.conn, """SELECT h3, kind, count(*) AS n, count(*) FILTER (WHERE status='validada') AS validadas
                            FROM report WHERE status <> 'rechazada' GROUP BY h3, kind ORDER BY h3""")

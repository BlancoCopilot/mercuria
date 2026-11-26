"""Datos abiertos: descarga libre, sin cuenta, en cualquier momento.

Licencia por defecto CC BY 4.0 (cada fila dice la suya). No incluye datos de personas
(solo agregados de salud con k ≥ 5), datos sintéticos, ni estudios embargados.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import date

from fastapi import APIRouter, Query
from fastapi.responses import Response

from ...db import rows
from ..deps import DbDep
from ..schemas import Matrix

router = APIRouter(prefix="/v1/open", tags=["datos abiertos"])


def _csv(data: list[dict], name: str, cols: list[str] | None = None) -> Response:
    buf = io.StringIO()
    cols = cols or (list(data[0]) if data else ["sin_datos"])
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in data:
        w.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in r.items()})
    fn = f"mercuria_{name}_{date.today():%Y%m%d}.csv"
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{fn}"', "Cache-Control": "public, max-age=300"})


def _geojson(feats: list[dict], name: str) -> Response:
    fn = f"mercuria_{name}_{date.today():%Y%m%d}.geojson"
    return Response(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False, default=str),
                    media_type="application/geo+json",
                    headers={"Content-Disposition": f'attachment; filename="{fn}"', "Cache-Control": "public, max-age=300"})


MEDICIONES_SQL = """
    SELECT m.id, m.matrix AS matriz, m.subtype AS subtipo,
           CASE m.hg_species WHEN 'metil' THEN 'metilmercurio' ELSE 'hg_total' END AS analito,
           m.value AS valor, m.unit AS unidad, m.value_original AS valor_original, m.unit_original AS unidad_original,
           m.basis AS base_original, m.below_dl AS bajo_limite_deteccion, m.sampled_on AS fecha_muestreo,
           m.season AS estacion, round(ST_Y(m.geom)::numeric, 6) AS lat, round(ST_X(m.geom)::numeric, 6) AS lon,
           m.precision_m AS precision_ubicacion_m, m.reach_id AS tramo_hydrorivers, m.method AS metodo,
           m.fish_species AS especie_pez, m.fish_group AS grupo_trofico, m.source_type AS tipo_fuente,
           m.weight AS peso_en_modelo, m.reference AS referencia, s.doi, s.id AS estudio_id,
           COALESCE(s.license, 'ver referencia') AS licencia, m.created_at AS cargado
    FROM measurement m LEFT JOIN study s ON s.id = m.study_id
    WHERE m.status = 'valido' AND NOT m.is_synthetic
      AND (CAST(:m AS text) IS NULL OR m.matrix = :m)
      AND (CAST(:sid AS int) IS NULL OR m.study_id = :sid)
    ORDER BY m.matrix, m.sampled_on NULLS LAST"""


@router.get("/catalog")
def catalog(db: DbDep):
    """Resumen de lo que se puede descargar (para la página de datos abiertos)."""
    c = rows(db.conn, """
        SELECT (SELECT count(*) FROM measurement WHERE status='valido' AND NOT is_synthetic) AS mediciones,
               (SELECT count(*) FROM study WHERE status='publicado') AS estudios,
               (SELECT count(*) FROM study_record r JOIN study s ON s.id=r.study_id
                 WHERE s.status='publicado' AND r.status='aprobado' AND NOT r.modeled) AS otros_registros,
               (SELECT count(*) FROM cell_risk_current) AS zonas,
               (SELECT count(*) FROM mining_site WHERE status <> 'descartado' AND NOT is_synthetic) AS sitios,
               (SELECT count(*) FROM river_reach WHERE NOT is_synthetic) AS tramos,
               (SELECT max(id) FROM map_version) AS version_mapa,
               (SELECT max(created_at) FROM map_version) AS actualizado""")[0]
    por_matriz = rows(db.conn, """SELECT matrix AS matriz, count(*) AS n FROM measurement
                                  WHERE status='valido' AND NOT is_synthetic GROUP BY 1 ORDER BY 1""")
    return {**c, "por_matriz": por_matriz}


@router.get("/studies")
def studies(db: DbDep):
    return rows(db.conn, """
        SELECT s.id, s.title AS titulo, s.authors AS autores, s.year AS anio, s.doi, s.url, s.institution AS institucion,
               s.license AS licencia, s.summary AS resumen, s.published_at AS publicado,
               s.pdf_open_access AS pdf_abierto, count(m.id) AS mediciones_en_mapa
        FROM study s LEFT JOIN measurement m ON m.study_id = s.id AND m.status = 'valido'
        WHERE s.status = 'publicado' GROUP BY s.id ORDER BY s.published_at DESC""")


@router.get("/studies.csv")
def studies_csv(db: DbDep):
    return _csv(studies(db), "estudios")


@router.get("/mediciones.csv")
def mediciones_csv(db: DbDep, matriz: Matrix | None = None, estudio: int | None = None):
    return _csv(rows(db.conn, MEDICIONES_SQL, m=matriz, sid=estudio), f"mediciones{'_' + matriz if matriz else ''}")


@router.get("/mediciones.geojson")
def mediciones_geojson(db: DbDep, matriz: Matrix | None = None, estudio: int | None = None):
    feats = []
    for r in rows(db.conn, MEDICIONES_SQL, m=matriz, sid=estudio):
        lat, lon = float(r.pop("lat")), float(r.pop("lon"))
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": r})
    return _geojson(feats, f"mediciones{'_' + matriz if matriz else ''}")


@router.get("/otros_registros.csv")
def otros(db: DbDep):
    """Datos aprobados que no entran al modelo (cabello, suelo, sedimento en suspensión, sin ubicación…)."""
    data = rows(db.conn, """
        SELECT r.id, s.id AS estudio_id, s.title AS estudio, s.doi, s.license AS licencia,
               r.fields->>'matriz' AS matriz, r.fields->>'subtipo' AS subtipo, r.fields->>'analito' AS analito,
               r.fields->>'valor' AS valor, r.fields->>'unidad' AS unidad, r.fields->>'estadistico' AS estadistico,
               r.fields->>'n' AS n, r.fields->>'lugar' AS lugar, r.fields->>'fecha' AS fecha,
               round(r.lat::numeric, 5) AS lat, round(r.lon::numeric, 5) AS lon, r.precision_m AS precision_m,
               array_to_string(r.problems, ' | ') AS observaciones, r.fields->>'pagina' AS pagina
        FROM study_record r JOIN study s ON s.id = r.study_id
        WHERE s.status = 'publicado' AND r.status = 'aprobado' AND NOT r.modeled
          AND r.fields->>'matriz' NOT IN ('cabello', 'sangre', 'orina')""")   # datos humanos: solo agregados
    return _csv(data, "otros_registros")


@router.get("/zonas_riesgo.csv")
def zonas(db: DbDep):
    data = rows(db.conn, """
        SELECT r.h3, r.risk_class AS nivel, round(r.risk::numeric, 3) AS riesgo, round(r.confidence::numeric, 3) AS confianza,
               r.palida AS incierta, round(r.hazard::numeric, 3) AS peligro, round(r.exposure::numeric, 3) AS exposicion,
               round(r.vulnerability::numeric, 3) AS vulnerabilidad, c.poblacion,
               round(ST_Y(ST_Centroid(c.geom))::numeric, 5) AS lat_centro, round(ST_X(ST_Centroid(c.geom))::numeric, 5) AS lon_centro,
               r.version_id AS version_mapa
        FROM cell_risk_current r JOIN h3_cell c USING (h3) ORDER BY r.risk DESC""")
    return _csv(data, "zonas_riesgo")


@router.get("/rios.csv")
def rios(db: DbDep, matriz: Matrix = Query("agua")):
    unidad = {"agua": "ug/L", "sedimento": "mg/kg", "pez": "mg/kg"}[matriz]
    data = rows(db.conn, """
        SELECT e.reach_id AS tramo_hydrorivers, e.matrix AS matriz, :u AS unidad,
               round(e.p05::numeric, 5) AS p05, round(e.p50::numeric, 5) AS mediana, round(e.p95::numeric, 5) AS p95,
               e.n_cercanos AS mediciones_conectadas, round(p.pressure::numeric, 3) AS presion_minera_kg_anio,
               e.version_id AS version_mapa
        FROM reach_estimate e LEFT JOIN reach_pressure p ON p.reach_id = e.reach_id AND p.matrix = e.matrix
        JOIN river_reach r ON r.hyriv_id = e.reach_id
        WHERE e.matrix = :m AND NOT r.is_synthetic ORDER BY e.p50 DESC""", m=matriz, u=unidad)
    return _csv(data, f"rios_{matriz}")


@router.get("/sitios_mineros.geojson")
def sitios(db: DbDep):
    feats = []
    for r in rows(db.conn, """
        SELECT s.id, s.legal_status AS estado_legal, s.status AS estado, round(s.area_ha::numeric, 2) AS area_ha,
               s.first_detected AS primera_deteccion, s.last_detected AS ultima_deteccion,
               round(e.hg_total_p05::numeric, 2) AS hg_kg_anio_p05, round(e.hg_total_p50::numeric, 2) AS hg_kg_anio_p50,
               round(e.hg_total_p95::numeric, 2) AS hg_kg_anio_p95, ST_AsGeoJSON(s.geom, 6) AS g
        FROM mining_site s LEFT JOIN site_emission e ON e.site_id = s.id
        WHERE s.status <> 'descartado' AND NOT s.is_synthetic AND s.origin <> 'denuncia'"""):
        g = json.loads(r.pop("g"))
        feats.append({"type": "Feature", "geometry": g, "properties": r})
    return _geojson(feats, "sitios_mineros")

"""Módulo 1: detector de sitios mineros.

Polígonos de minería (Amazon Mining Watch, MapBiomas clase 30, denuncias) ->
detecciones -> sitios. Una detección a menos de 100 m de un sitio existente lo
amplía; si no, crea un sitio nuevo. Después cada sitio se:
  * clasifica frente a concesiones (AJAM/RAISG/GeoTienda) y áreas protegidas,
  * conecta al tramo de río al que drena (el más cercano).

Decisión de lenguaje: no etiquetamos "ilegal" (es una determinación legal que hace
una autoridad); decimos "sin concesión registrada" o "en área protegida".
"""
from __future__ import annotations

import hashlib
from datetime import date
from typing import Iterable

from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from sqlalchemy import Connection, text

from ..db import one, rows, tx
from ..engine.params import params
from ..settings import get_settings
from .vector import read_vector

MERGE_M = 100


def _multi(g: BaseGeometry) -> MultiPolygon | None:
    g = g.buffer(0) if not g.is_valid else g
    if isinstance(g, Polygon):
        return MultiPolygon([g])
    if isinstance(g, MultiPolygon):
        return g
    polys = [p for p in getattr(g, "geoms", []) if isinstance(p, Polygon)]
    return MultiPolygon(polys) if polys else None


def ingest_features(conn: Connection, feats: Iterable[tuple[BaseGeometry, date, str | None]],
                    source: str, is_synthetic: bool = False) -> dict:
    """feats: (geometría, fecha de detección, id en la fuente). Devuelve sitios nuevos/cambiados."""
    new_sites, touched = [], set()
    n_new_det = 0
    for geom, detected_on, ref in feats:
        mp = _multi(geom)
        if mp is None:
            continue
        ref = ref or hashlib.sha1(mp.wkb).hexdigest()[:16]
        det = one(conn, """
            INSERT INTO mining_detection (source, source_ref, detected_on, area_ha, geom, is_synthetic)
            VALUES (:s, :r, :d, ST_Area(ST_GeomFromText(:g, 4326)::geography) / 1e4,
                    ST_GeomFromText(:g, 4326), :syn)
            ON CONFLICT (source, source_ref) DO NOTHING RETURNING id""",
            s=source, r=str(ref), d=detected_on, g=mp.wkt, syn=is_synthetic)
        if det is None:
            continue   # ya conocida
        n_new_det += 1
        site = one(conn, """
            SELECT id FROM mining_site
            WHERE status <> 'descartado'
              AND ST_DWithin(geom::geography, ST_GeomFromText(:g, 4326)::geography, :m)
            ORDER BY ST_Distance(geom::geography, ST_GeomFromText(:g, 4326)::geography) LIMIT 1""",
            g=mp.wkt, m=MERGE_M)
        if site:
            sid = site["id"]
            conn.execute(text("""
                UPDATE mining_site SET
                    geom = ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Union(geom, ST_GeomFromText(:g, 4326))), 3)),
                    first_detected = LEAST(first_detected, :d),
                    last_detected  = GREATEST(last_detected, :d),
                    origin    = CASE WHEN origin = 'denuncia' THEN 'satelite' ELSE origin END,
                    confianza = GREATEST(confianza, 1.0),   -- el satélite confirma una denuncia
                    status = 'activo', updated_at = now()
                WHERE id = :id"""), {"g": mp.wkt, "d": detected_on, "id": sid})
        else:
            sid = one(conn, """
                INSERT INTO mining_site (first_detected, last_detected, area_ha, origin, confianza, geom, is_synthetic)
                VALUES (:d, :d, 0, 'satelite', :c, ST_GeomFromText(:g, 4326), :syn) RETURNING id""",
                d=detected_on, c=params()["confianza_fuente"]["satelite"], g=mp.wkt, syn=is_synthetic)["id"]
            new_sites.append(sid)
        conn.execute(text("UPDATE mining_detection SET site_id=:s WHERE id=:d"), {"s": sid, "d": det["id"]})
        touched.add(sid)
    if touched:
        finalize_sites(conn, list(touched))
    return {"detecciones_nuevas": n_new_det, "sitios_nuevos": new_sites, "sitios_cambiados": sorted(touched)}


def finalize_sites(conn: Connection, site_ids: list[int]) -> None:
    """Área, tramo de río y estado legal de los sitios indicados."""
    conn.execute(text("""
        UPDATE mining_site s SET area_ha = ST_Area(s.geom::geography) / 1e4,
            (reach_id, snap_distance_m) = (
                SELECT r.hyriv_id, ST_Distance(r.geom::geography, s.geom::geography)
                FROM river_reach r ORDER BY r.geom <-> s.geom LIMIT 1)
        WHERE s.id = ANY(:ids)"""), {"ids": site_ids})
    conn.execute(text("""
        UPDATE mining_site s SET
            concession_id = (SELECT c.id FROM concession c
                             WHERE ST_Intersects(c.geom, s.geom) AND (c.valid_to IS NULL OR c.valid_to >= current_date)
                             ORDER BY ST_Area(ST_Intersection(c.geom, s.geom)) DESC LIMIT 1),
            protected_area_id = (SELECT p.id FROM protected_area p WHERE ST_Intersects(p.geom, s.geom) LIMIT 1)
        WHERE s.id = ANY(:ids)"""), {"ids": site_ids})
    conn.execute(text("""
        UPDATE mining_site s SET legal_status = CASE
            WHEN s.protected_area_id IS NOT NULL THEN 'en_area_protegida'
            WHEN s.concession_id IS NOT NULL THEN 'con_concesion'
            WHEN NOT EXISTS (SELECT 1 FROM concession) THEN 'indeterminado'   -- sin capa, no afirmamos nada
            ELSE 'sin_concesion' END
        WHERE s.id = ANY(:ids)"""), {"ids": site_ids})


def site_from_report(conn: Connection, report_id: str) -> int:
    """Denuncia de minería -> sitio provisional (confianza 0,2), círculo del área declarada."""
    cfg = params()
    r = one(conn, "SELECT id, area_ha, created_client_at, is_synthetic FROM report WHERE id=:id", id=report_id)
    area = r["area_ha"] or cfg["emisiones"]["area_denuncia_sin_poligono_ha"]
    sid = one(conn, """
        INSERT INTO mining_site (first_detected, last_detected, area_ha, origin, confianza, geom, is_synthetic)
        SELECT CAST(:d AS date), CAST(:d AS date), :a, 'denuncia', :c,
               ST_Multi(ST_Buffer(geom::geography, sqrt(:a * 1e4 / pi()))::geometry), :syn
        FROM report WHERE id = :id RETURNING id""",
        d=r["created_client_at"].date(), a=area, c=cfg["confianza_fuente"]["denuncia"],
        syn=r["is_synthetic"], id=report_id)["id"]
    conn.execute(text("UPDATE report SET site_id=:s WHERE id=:id"), {"s": sid, "id": report_id})
    finalize_sites(conn, [sid])
    return sid


def ingest_remote(source: str) -> dict:
    """Tarea programada: descarga la capa configurada (AMW_URL / MAPBIOMAS_URL) y la ingiere."""
    s = get_settings()
    url = {"amw": s.amw_url, "mapbiomas": s.mapbiomas_url}[source]
    if not url:
        return {"detecciones_nuevas": 0, "sitios_nuevos": [], "sitios_cambiados": [],
                "aviso": f"{source.upper()}_URL no configurada"}
    gdf = read_vector(url)
    if source == "mapbiomas":
        for col in ("class", "classification", "clase", "DN"):
            if col in gdf.columns:
                gdf = gdf[gdf[col].astype(str) == "30"]
                break
    feats = list(_features(gdf))
    with tx() as conn:
        return ingest_features(conn, feats, source)


def _parse_period(v) -> date | None:
    """Año (2023), fecha ISO o trimestre de Amazon Mining Watch ("Q326" = 3er trimestre de 2026)."""
    sv = str(v).strip()
    if sv.isdigit() and len(sv) == 4:
        return date(int(sv), 7, 1)
    if len(sv) == 4 and sv[0] in "Qq" and sv[1:].isdigit():
        q, yy = int(sv[1]), int(sv[2:])
        if 1 <= q <= 4:
            return date(2000 + yy, 3 * q - 1, 15)   # mitad del trimestre
    try:
        return date.fromisoformat(sv[:10])
    except ValueError:
        return None


def _features(gdf) -> Iterable[tuple[BaseGeometry, date, str | None]]:
    # AMW publica "onset" (año o trimestre en que se confirmó la minería por primera vez).
    date_cols = [c for c in ("detected_on", "onset", "onset_year", "date", "fecha", "year", "anio", "YEAR")
                 if c in gdf.columns]
    id_cols = [c for c in ("id", "ID", "fid", "source_ref") if c in gdf.columns]
    for _, row in gdf.iterrows():
        d = None
        for c in date_cols:
            d = _parse_period(row[c])
            if d:
                break
        ref = str(row[id_cols[0]]) if id_cols else None
        yield row.geometry, d or date.today(), ref

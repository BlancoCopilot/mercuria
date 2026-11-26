"""Cargadores de la base fija: censo, concesiones, áreas protegidas."""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from ..db import tx
from .detections import finalize_sites
from .vector import read_vector


def load_census_csv(path: str) -> dict:
    """CSV de comunidades (Censo 2024 / INE). Columnas:
    codigo, nombre, lat, lon, poblacion, ninos_u5, mujeres_15_49[, municipio]
    Si el código ya existe se actualiza; si hay un poblado OSM a < 1 km con el mismo
    nombre, se le agregan los datos del censo en vez de duplicarlo.
    """
    df = pd.read_csv(path)
    recs = df.rename(columns={"codigo": "code", "nombre": "name"}).to_dict("records")
    n_merge = 0
    with tx() as conn:
        for r in recs:
            params = {"code": str(r["code"]), "name": r["name"], "lat": r["lat"], "lon": r["lon"],
                      "pob": int(r["poblacion"]), "ninos": int(r["ninos_u5"]), "muj": int(r["mujeres_15_49"]),
                      "mun": r.get("municipio")}
            res = conn.execute(text("""
                UPDATE settlement SET census_code=:code, poblacion=:pob, ninos_u5=:ninos, mujeres_15_49=:muj,
                       municipio=COALESCE(:mun, municipio), poblacion_fuente='censo2024'
                WHERE id = (SELECT id FROM settlement
                            WHERE census_code = :code
                               OR (census_code IS NULL AND lower(name) = lower(:name)
                                   AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon,:lat),4326)::geography, 1000))
                            LIMIT 1)"""), params)
            if res.rowcount:
                n_merge += 1
                continue
            conn.execute(text("""
                INSERT INTO settlement (name, census_code, poblacion, ninos_u5, mujeres_15_49, municipio, geom, source,
                                        poblacion_fuente)
                VALUES (:name, :code, :pob, :ninos, :muj, :mun, ST_SetSRID(ST_MakePoint(:lon,:lat),4326), 'censo2024',
                        'censo2024')"""),
                params)
        from .base import build_cells
        build_cells(conn)
    return {"filas": len(recs), "fusionadas": n_merge}


def _load_polygons(path: str, table: str, mapping: dict[str, str], source: str) -> int:
    gdf = read_vector(path)
    recs = []
    for _, r in gdf.iterrows():
        rec = {dst: (None if pd.isna(r.get(src)) else r.get(src)) for dst, src in mapping.items()}
        rec["wkt"] = r.geometry.wkt
        rec["source"] = source
        recs.append(rec)
    cols = list(mapping)
    with tx() as conn:
        conn.execute(text(f"""
            INSERT INTO {table} ({", ".join(cols)}, geom, source)
            VALUES ({", ".join(":" + c for c in cols)},
                    ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_GeomFromText(:wkt, 4326)), 3)), :source)"""), recs)
        # reclasificar todos los sitios con la capa nueva
        ids = [r[0] for r in conn.execute(text("SELECT id FROM mining_site"))]
        if ids:
            finalize_sites(conn, ids)
    return len(recs)


def load_concessions(path: str, code_col="codigo", holder_col="titular", status_col="estado",
                     mineral_col="mineral", source="AJAM") -> dict:
    n = _load_polygons(path, "concession",
                       {"code": code_col, "holder": holder_col, "status": status_col, "mineral": mineral_col}, source)
    return {"concesiones": n}


def load_protected_areas(path: str, name_col="nombre", category_col="categoria", source="SERNAP") -> dict:
    n = _load_polygons(path, "protected_area", {"name": name_col, "category": category_col}, source)
    return {"areas_protegidas": n}

"""Carga de HydroRIVERS v1.0 (https://www.hydrosheds.org/products/hydrorivers).

Descargar HydroRIVERS_v10_sa_shp.zip (Sudamérica) y pasar la ruta. Se recorta a la
cuenca piloto: o por bbox, o (mejor) tomando todo lo que drena a un tramo de salida.
"""
from __future__ import annotations

from collections import defaultdict, deque

from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge
from sqlalchemy import text

from ..db import tx
from .vector import read_vector


def load_hydrorivers(path: str, outlet_id: int | None = None, min_upland_skm: float = 0.0) -> dict:
    gdf = read_vector(path, clip=True)
    gdf = gdf[gdf["UPLAND_SKM"] >= min_upland_skm]
    if outlet_id is not None:
        ups = defaultdict(list)
        for rid, nd in zip(gdf["HYRIV_ID"], gdf["NEXT_DOWN"]):
            ups[int(nd)].append(int(rid))
        keep, q = {outlet_id}, deque([outlet_id])
        while q:
            for u in ups.get(q.popleft(), ()):
                if u not in keep:
                    keep.add(u)
                    q.append(u)
        gdf = gdf[gdf["HYRIV_ID"].astype(int).isin(keep)]
    recs = []
    for _, r in gdf.iterrows():
        g = r.geometry
        if isinstance(g, MultiLineString):
            g = linemerge(g)
            if not isinstance(g, LineString):
                g = max(g.geoms, key=lambda x: x.length)
        recs.append({
            "id": int(r["HYRIV_ID"]), "nd": int(r["NEXT_DOWN"]), "main": int(r.get("MAIN_RIV", 0) or 0),
            "len": float(r["LENGTH_KM"]), "ddn": float(r.get("DIST_DN_KM", 0) or 0),
            "up": float(r["UPLAND_SKM"]), "q": float(r["DIS_AV_CMS"]), "ord": int(r.get("ORD_STRA", 0) or 0),
            "wkt": g.wkt,
        })
    with tx() as conn:
        conn.execute(text("""
            INSERT INTO river_reach (hyriv_id, next_down, main_riv, length_km, dist_dn_km, upland_skm,
                                     dis_av_cms, ord_stra, geom)
            VALUES (:id, :nd, :main, :len, :ddn, :up, :q, :ord, ST_GeomFromText(:wkt, 4326))
            ON CONFLICT (hyriv_id) DO UPDATE SET next_down=EXCLUDED.next_down, length_km=EXCLUDED.length_km,
                upland_skm=EXCLUDED.upland_skm, dis_av_cms=EXCLUDED.dis_av_cms, geom=EXCLUDED.geom"""), recs)
    return {"tramos": len(recs)}

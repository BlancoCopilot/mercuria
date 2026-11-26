"""Construcción de la grilla H3 y utilidades espaciales compartidas."""
from __future__ import annotations

import h3
from shapely import wkb
from shapely.geometry import LineString
from sqlalchemy import Connection, text

from ..db import one, rows
from ..engine.params import params

SNAP_MAX_M = 2000


def h3_res() -> int:
    return int(params()["riesgo"]["h3_res"])


def cell_of(lat: float, lon: float) -> str:
    return h3.latlng_to_cell(lat, lon, h3_res())


def build_cells(conn: Connection, step_deg: float = 0.0025) -> dict:
    """Celdas = las que toca algún río (+ anillo 1) y las que tienen poblados.

    Muestrea cada tramo cada ~250 m para saber qué celdas atraviesa (reach_cell).
    """
    res = h3_res()
    reach_cells: list[dict] = []
    cells: set[str] = set()
    for r in rows(conn, "SELECT hyriv_id, ST_AsBinary(geom) AS g FROM river_reach"):
        line: LineString = wkb.loads(bytes(r["g"]))
        n = max(2, int(line.length / step_deg) + 1)
        touched = {h3.latlng_to_cell(p.y, p.x, res)
                   for p in (line.interpolate(i / (n - 1), normalized=True) for i in range(n))}
        for c in touched:
            reach_cells.append({"r": r["hyriv_id"], "h3": c})
            cells.update(h3.grid_disk(c, 1))
    for table in ("settlement", "exposure_feature"):
        pts = rows(conn, f"""SELECT id, ST_Y(ST_PointOnSurface(geom)) AS lat,
                                    ST_X(ST_PointOnSurface(geom)) AS lon FROM {table}""")
        ups = [{"h": h3.latlng_to_cell(s["lat"], s["lon"], res), "id": s["id"]} for s in pts]
        if ups:
            conn.execute(text(f"UPDATE {table} SET h3=:h WHERE id=:id"), ups)
            cells.update(u["h"] for u in ups)
    existing = {r["h3"] for r in rows(conn, "SELECT h3 FROM h3_cell")}
    new = [{"h3": c, "res": res, "wkt": _cell_wkt(c)} for c in cells - existing]
    if new:
        conn.execute(text("INSERT INTO h3_cell (h3, res, geom) VALUES (:h3, :res, ST_GeomFromText(:wkt, 4326))"), new)
    conn.execute(text("DELETE FROM reach_cell"))
    if reach_cells:
        conn.execute(text("INSERT INTO reach_cell (reach_id, h3) VALUES (:r, :h3) ON CONFLICT DO NOTHING"), reach_cells)
    return {"celdas": len(cells), "celdas_nuevas": len(new), "tramo_celda": len(reach_cells)}


def _cell_wkt(c: str) -> str:
    ring = [(lng, lat) for lat, lng in h3.cell_to_boundary(c)]
    ring.append(ring[0])
    return "POLYGON((" + ",".join(f"{x} {y}" for x, y in ring) + "))"


MAIN_CHANNEL_M = 500      # margen para preferir el cauce principal
MAIN_CHANNEL_RATIO = 10   # ...si su cuenca es al menos 10 veces mayor


def choose_reach(candidates: list[dict], max_m: float = SNAP_MAX_M) -> dict | None:
    """candidates: [{hyriv_id, d, upland_skm}] ordenados por distancia.

    El tramo más cercano no siempre es el río muestreado: junto al Kaká hay arroyos de
    13 km² a 200 m. Si dentro de (más cercano + 500 m) hay un río con cuenca ≥ 10 veces
    mayor, se elige ese. Para un arroyo de verdad, el laboratorio indica `tramo_id`.
    """
    if not candidates or candidates[0]["d"] > max_m:
        return None
    best = candidates[0]
    for c in candidates[1:]:
        if c["d"] <= min(candidates[0]["d"] + MAIN_CHANNEL_M, max_m) and \
                c["upland_skm"] >= MAIN_CHANNEL_RATIO * max(candidates[0]["upland_skm"], 1e-6) and \
                c["upland_skm"] > best["upland_skm"]:
            best = c
    return best


def snap_point(conn: Connection, lon: float, lat: float, max_m: float = SNAP_MAX_M) -> tuple[int | None, float | None]:
    cands = rows(conn, """
        SELECT hyriv_id, upland_skm,
               ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS d
        FROM river_reach ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) LIMIT 8""", lon=lon, lat=lat)
    cands.sort(key=lambda c: c["d"])
    best = choose_reach(cands, max_m)
    if best is None:
        return None, (cands[0]["d"] if cands else None)
    return int(best["hyriv_id"]), float(best["d"])

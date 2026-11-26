"""OpenStreetMap vía Overpass (tarea mensual): poblados, centros de salud, tomas de agua,
zonas de pesca. Upsert por osm_id, así repetir la tarea no duplica nada.
Sin datos personales en la petición: User-Agent genérico del proyecto.
"""
from __future__ import annotations

import httpx
from sqlalchemy import text

from ..db import tx
from ..settings import get_settings


def _query(bbox: tuple[float, float, float, float]) -> str:
    w, s, e, n = bbox
    b = f"({s},{w},{n},{e})"
    return f"""[out:json][timeout:180];
(
  node["place"~"city|town|village|hamlet|isolated_dwelling"]{b};
  nwr["amenity"~"hospital|clinic|doctors"]{b};
  nwr["healthcare"]{b};
  nwr["man_made"~"water_works|water_well|water_tap|storage_tank"]{b};
  nwr["amenity"="drinking_water"]{b};
  nwr["leisure"="fishing"]{b};
  nwr["fishing"]{b};
);
out center tags;"""


def ingest_osm() -> dict:
    s = get_settings()
    r = httpx.post(s.overpass_url, data={"data": _query(s.bbox)}, timeout=240,
                   headers={"User-Agent": s.http_user_agent})
    r.raise_for_status()
    return load_overpass_json(r.json())


def load_overpass_json(payload: dict) -> dict:
    places, health, intakes, fishing = [], [], [], []
    for el in payload.get("elements", []):
        tags = el.get("tags", {})
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if lat is None or lon is None:
            continue
        base = {"osm": f"{el['type']}/{el['id']}", "name": tags.get("name"), "lat": lat, "lon": lon}
        if "place" in tags:
            pop = tags.get("population", "").replace(".", "").replace(",", "")
            places.append({**base, "name": base["name"] or "(sin nombre)", "kind": tags["place"],
                           "pop": int(pop) if pop.isdigit() else None})
        elif tags.get("amenity") in ("hospital", "clinic", "doctors") or "healthcare" in tags:
            health.append({**base, "name": base["name"] or "Centro de salud", "phone": tags.get("phone")})
        elif tags.get("leisure") == "fishing" or "fishing" in tags:
            fishing.append(base)
        else:
            intakes.append(base)
    pt = "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)"
    with tx() as conn:
        if places:
            conn.execute(text(f"""
                INSERT INTO settlement (name, kind, osm_id, poblacion, geom, source)
                VALUES (:name, :kind, :osm, :pop, {pt}, 'osm')
                ON CONFLICT (osm_id) DO UPDATE SET name=EXCLUDED.name, kind=EXCLUDED.kind,
                    poblacion=COALESCE(settlement.poblacion, EXCLUDED.poblacion), geom=EXCLUDED.geom"""), places)
        if health:
            conn.execute(text(f"""
                INSERT INTO health_facility (name, phone, osm_id, geom, source) VALUES (:name, :phone, :osm, {pt}, 'osm')
                ON CONFLICT (osm_id) DO UPDATE SET name=EXCLUDED.name, phone=EXCLUDED.phone, geom=EXCLUDED.geom"""), health)
        for kind, items in (("toma_agua", intakes), ("zona_pesca", fishing)):
            if items:
                conn.execute(text(f"""
                    INSERT INTO exposure_feature (kind, name, osm_id, geom, source) VALUES ('{kind}', :name, :osm, {pt}, 'osm')
                    ON CONFLICT (osm_id) DO UPDATE SET geom=EXCLUDED.geom"""), items)
        from .base import build_cells
        cells = build_cells(conn)
    return {"poblados": len(places), "salud": len(health), "tomas_agua": len(intakes),
            "zonas_pesca": len(fishing), **cells}

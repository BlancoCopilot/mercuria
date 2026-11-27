"""OpenStreetMap vía Overpass (tarea mensual): poblados, centros de salud, tomas de agua,
zonas de pesca. Upsert por osm_id, así repetir la tarea no duplica nada.
Sin datos personales en la petición: User-Agent genérico del proyecto.
"""
from __future__ import annotations

import httpx
from sqlalchemy import text

from ..db import tx
from ..settings import get_settings


# Centros de salud: margen alrededor de la cuenca, para que quien vive en el borde vea el más cercano
SALUD_MARGEN = 0.4

# Lo que cuenta como lugar donde atienden a una persona (sin farmacias, dentistas, ópticas ni laboratorios)
_SALUD_HC = {"hospital": "Hospital", "clinic": "Centro de salud", "centre": "Centro de salud",
             "doctor": "Consultorio", "yes": "Centro de salud"}
_SALUD_AM = {"hospital": "Hospital", "clinic": "Centro de salud", "doctors": "Consultorio"}


def health_tipo(tags: dict) -> str | None:
    """Tipo legible del establecimiento, o None si no atiende pacientes (farmacia, dentista, etc.)."""
    hc, am = tags.get("healthcare"), tags.get("amenity")
    if hc and hc not in _SALUD_HC:
        return None
    if am and am not in _SALUD_AM and not hc:
        return None
    nombre = (tags.get("name") or "").lower()
    if "puesto" in nombre:
        return "Puesto de salud"
    if "hospital" in nombre:
        return "Hospital"
    return _SALUD_HC.get(hc or "") or _SALUD_AM.get(am or "") or "Centro de salud"


def _query(bbox: tuple[float, float, float, float]) -> str:
    w, s, e, n = bbox
    b = f"({s},{w},{n},{e})"
    m = SALUD_MARGEN
    hb = f"({s - m},{w - m},{n + m},{e + m})"
    return f"""[out:json][timeout:180];
(
  node["place"~"city|town|village|hamlet|isolated_dwelling"]{b};
  nwr["amenity"~"hospital|clinic|doctors"]{hb};
  nwr["healthcare"]{hb};
  nwr["man_made"~"water_works|water_well|water_tap|storage_tank"]{b};
  nwr["amenity"="drinking_water"]{b};
  nwr["leisure"="fishing"]{b};
  nwr["fishing"]{b};
);
out center tags;"""


def _salud_de(payload: dict) -> list[dict]:
    out = []
    for el in payload.get("elements", []):
        tags = el.get("tags", {})
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        tipo = health_tipo(tags) if lat is not None and lon is not None else None
        if tipo:
            out.append({"osm": f"{el['type']}/{el['id']}", "name": tags.get("name") or tipo, "tipo": tipo,
                        "phone": tags.get("phone") or tags.get("contact:phone"), "lat": lat, "lon": lon})
    return out


def _upsert_salud(conn, health: list[dict]) -> None:
    conn.execute(text("""
        INSERT INTO health_facility (name, level, phone, osm_id, geom, source)
        VALUES (:name, :tipo, :phone, :osm, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 'osm')
        ON CONFLICT (osm_id) DO UPDATE SET name=EXCLUDED.name, level=EXCLUDED.level, phone=EXCLUDED.phone,
            geom=EXCLUDED.geom"""), health)
    # lo que ya no está en OSM (o resultó ser farmacia, dentista…) sale, salvo que tenga derivaciones
    conn.execute(text("""
        DELETE FROM health_facility f WHERE f.source = 'osm' AND NOT (f.osm_id = ANY(:ids))
          AND NOT EXISTS (SELECT 1 FROM referral r WHERE r.facility_id = f.id)"""),
        {"ids": [h["osm"] for h in health]})


def ingest_salud(payload: dict | None = None) -> dict:
    """Solo centros de salud (no toca poblados ni recalcula el riesgo). `payload`: JSON de Overpass ya descargado."""
    if payload is None:
        s = get_settings()
        w, so, e, n = s.bbox
        m = SALUD_MARGEN
        hb = f"({so - m},{w - m},{n + m},{e + m})"
        q = f'[out:json][timeout:180];(nwr["amenity"~"hospital|clinic|doctors"]{hb};nwr["healthcare"]{hb};);out center tags;'
        r = httpx.post(s.overpass_url, data={"data": q}, timeout=240, headers={"User-Agent": s.http_user_agent})
        r.raise_for_status()
        payload = r.json()
    health = _salud_de(payload)
    if not health:
        return {"salud": 0, "nota": "Overpass no devolvió centros: no se cambió nada"}
    with tx() as conn:
        _upsert_salud(conn, health)
    tipos: dict[str, int] = {}
    for h in health:
        tipos[h["tipo"]] = tipos.get(h["tipo"], 0) + 1
    return {"salud": len(health), "por_tipo": tipos}


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
            tipo = health_tipo(tags)
            if tipo:
                phone = tags.get("phone") or tags.get("contact:phone")
                health.append({**base, "name": base["name"] or tipo, "phone": phone, "tipo": tipo})
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
            _upsert_salud(conn, health)
        for kind, items in (("toma_agua", intakes), ("zona_pesca", fishing)):
            if items:
                conn.execute(text(f"""
                    INSERT INTO exposure_feature (kind, name, osm_id, geom, source) VALUES ('{kind}', :name, :osm, {pt}, 'osm')
                    ON CONFLICT (osm_id) DO UPDATE SET geom=EXCLUDED.geom"""), items)
        from .base import build_cells
        cells = build_cells(conn)
    return {"poblados": len(places), "salud": len(health), "tomas_agua": len(intakes),
            "zonas_pesca": len(fishing), **cells}

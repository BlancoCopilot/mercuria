"""Normaliza una medición propuesta (de la IA o de un CSV): unidades, base, ubicación, peso y problemas.

Cada problema aquí sale de algo real que encontramos al revisar la literatura de la cuenca:
límites de detección altos, sitios sin coordenadas, peces de mercado sin río de origen,
peso seco sin aviso, sedimento en suspensión mezclado con sedimento de fondo.
"""
from __future__ import annotations

import re
from datetime import date

from pyproj import Transformer
from sqlalchemy import Connection

from ..db import one
from ..engine.params import load_yaml, params
from ..engine.units import CANONICA, to_canonical
from ..ingest.base import snap_point

MODELED = {"agua", "sedimento", "pez"}
FACTOR_SECO_HUMEDO = 3.8   # músculo de pez: ~70 % de agua (Laffont et al. 2009: pendiente 3,78)
PRECISION = {"coordenadas": 50, "utm": 50, "manual": 100, "comunidad": 5000}


def _species_group(f: dict) -> tuple[str | None, str | None]:
    """(código, grupo trófico) buscando la especie por nombre científico o común."""
    cat = load_yaml("fish_species.yaml")["especies"]
    sci = (f.get("especie_cientifica") or "").lower()
    com = (f.get("especie_comun") or "").lower()
    for e in cat:
        genero = e["cientifico"].lower().split()[0]
        if (sci and (e["cientifico"].lower() in sci or sci.startswith(genero))) or \
           (com and (e["codigo"] in com or e["nombre"].lower().split(" /")[0] in com)):
            return e["codigo"], e["grupo"]
    return None, None


def _utm(este: float, norte: float, zona: str | None) -> tuple[float, float] | None:
    m = re.match(r"\s*(\d{1,2})\s*([A-Za-z])?", zona or "19S")
    if not m:
        return None
    z = int(m.group(1))
    sur = (m.group(2) or "S").upper() < "N"           # bandas C–M = hemisferio sur
    epsg = (32700 if sur else 32600) + z
    lon, lat = Transformer.from_crs(epsg, 4326, always_xy=True).transform(este, norte)
    return lat, lon


def _geocode(conn: Connection, lugar: str | None) -> tuple[float, float, str] | None:
    """Comunidad con nombre parecido (pg_trgm). Precisión de ~5 km: el revisor puede corregir."""
    if not lugar:
        return None
    nombre = re.sub(r"\b(r[ií]o|comunidad|mercado( de)?|puerto|cerca de|near|river)\b", "", lugar, flags=re.I).strip(" ,.-")
    if len(nombre) < 3:
        return None
    r = one(conn, """SELECT name, ST_Y(geom) AS lat, ST_X(geom) AS lon, similarity(name, :q) AS s
                     FROM settlement WHERE name % :q OR name ILIKE :q || '%'
                     ORDER BY similarity(name, :q) DESC, poblacion DESC NULLS LAST LIMIT 1""", q=nombre)
    return (r["lat"], r["lon"], r["name"]) if r and r["s"] >= 0.45 else None


def prepare(conn: Connection, f: dict) -> dict:
    """Devuelve las columnas calculadas de study_record a partir de los campos vigentes."""
    cfg = params()
    problems: list[str] = []
    matriz = f.get("matriz")
    modeled = matriz in MODELED
    if not modeled:
        problems.append(f"Matriz «{matriz}»: no entra al mapa de riesgo; se publica como dato abierto.")

    # ── valor en unidad canónica ──
    value = unit = None
    try:
        v = float(f.get("valor"))
        if v <= 0:
            raise ValueError
        if modeled:
            value, unit = to_canonical(matriz, v, f.get("unidad") or CANONICA[matriz]), CANONICA[matriz]
        else:
            value, unit = v, f.get("unidad")
    except (TypeError, ValueError) as e:
        problems.append(f"Valor o unidad no válidos ({f.get('valor')} {f.get('unidad')}): {e}".rstrip(": "))
    base = f.get("base") or "desconocido"
    if matriz == "pez" and value is not None:
        if base == "seco":
            value /= FACTOR_SECO_HUMEDO
            problems.append(f"Peso seco convertido a húmedo (÷ {FACTOR_SECO_HUMEDO}).")
        elif base in ("desconocido", None):
            problems.append("No dice si es peso seco o húmedo: se asume húmedo. Revísalo.")
    if f.get("analito") == "metilmercurio" and matriz in ("agua", "sedimento"):
        problems.append("Metilmercurio en agua o sedimento: el modelo usa Hg total; no entra al mapa.")
        modeled = False
    if f.get("subtipo") in ("agua_particulada", "agua_disuelta"):
        problems.append("Agua filtrada (solo particulada o disuelta): el modelo usa Hg total en agua sin filtrar; no entra al mapa.")
        modeled = False
    if f.get("subtipo") == "sedimento_suspension":
        problems.append("Sedimento en suspensión: no es comparable con sedimento de fondo; no entra al mapa.")
        modeled = False
    if f.get("subtipo") == "sedimento_laguna":
        problems.append("Sedimento de laguna de inundación: no es cauce de río; no entra al mapa.")
        modeled = False

    # ── especie (peces) ──
    codigo = grupo = None
    if matriz == "pez":
        codigo, grupo = _species_group(f)
        if not grupo:
            problems.append("Especie de pez no reconocida: elige la especie para saber su nivel trófico.")
        if f.get("origen_pez") in ("mercado", "desconocido"):
            problems.append("Pez de mercado o de origen desconocido: la ubicación es la del mercado, no la del río.")

    # ── ubicación ──
    lat = lon = None
    src = None
    if f.get("lat") is not None and f.get("lon") is not None:
        lat, lon, src = float(f["lat"]), float(f["lon"]), f.get("_ubicacion") or "coordenadas"
    elif f.get("utm_este") and f.get("utm_norte"):
        ll = _utm(float(f["utm_este"]), float(f["utm_norte"]), f.get("utm_zona"))
        if ll:
            lat, lon, src = ll[0], ll[1], "utm"
    else:
        g = _geocode(conn, f.get("lugar"))
        if g:
            lat, lon, src = g[0], g[1], "comunidad"
            problems.append(f"Ubicación aproximada (~5 km): se usó la comunidad «{g[2]}». Corrígela si sabes el punto.")
    if lat is None:
        problems.append("Sin ubicación: indica coordenadas o marca el punto para que entre al mapa.")
    precision = PRECISION.get(src or "", None)
    if f.get("_precision_m") and lat is not None:      # el revisor declara la precisión real (p. ej. ~10 km)
        precision = float(f["_precision_m"])

    reach = None
    if lat is not None and modeled:
        reach, _ = snap_point(conn, lon, lat)
        if reach is None:
            problems.append("A más de 2 km de un río de la red: no entra al modelo.")

    # ── límite de detección ──
    if f.get("bajo_ld") and matriz == "agua" and value is not None and value >= 0.5:
        problems.append("Límite de detección muy alto para agua de río (≥ 0,5 µg/L): el dato casi no informa.")

    # ── fecha ──
    fecha = f.get("fecha")
    if not fecha:
        problems.append("Sin fecha de muestreo: el peso por antigüedad no se puede calcular (se usa la del estudio).")

    # ── peso del dato ──
    w = cfg["confianza_fuente"]["publicado"]
    if precision and precision > 2000:
        w *= 0.5
    if matriz == "pez" and f.get("origen_pez") in ("mercado", "desconocido"):
        w *= 0.5
    if (f.get("confianza") or 1) < 0.6:
        problems.append("La IA tiene baja confianza en esta lectura: compárala con el documento.")

    ready = modeled and value is not None and reach is not None and (matriz != "pez" or grupo)
    return {
        "problems": problems, "modeled": bool(ready), "value_canonical": value, "unit_canonical": unit,
        "lat": lat, "lon": lon, "precision_m": precision, "location_source": src, "reach_id": reach,
        "weight": round(w, 3), "_fish": (codigo, grupo),
    }


def parse_fecha(s: str | None, fallback_year: int | None) -> date | None:
    if s:
        m = re.match(r"(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?", str(s))
        if m:
            return date(int(m.group(1)), int(m.group(2) or 7), int(m.group(3) or 1))
    return date(fallback_year, 7, 1) if fallback_year else None

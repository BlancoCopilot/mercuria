"""MapBiomas Bolivia (clase 30 = minería) desde Google Earth Engine -> GeoJSON.

Fuente: projects/mapbiomas-public/assets/bolivia/lulc/v1 (MapBiomas, CC-BY-4.0), 30 m, anual.
El asset trae varias ediciones (colecciones) del mismo año: se usa solo la más reciente.

Cada polígono lleva:
  anio         último año en que el píxel aparece como minería (actividad reciente)
  anio_inicio  primer año en que aparece como minería (desde ANIO_DESDE)

El GeoJSON se guarda en data/raw/ y MAPBIOMAS_URL apunta a él; `rastrohg ingest mapbiomas`
(cron anual) lo carga como detecciones. Se genera en una máquina con credenciales de Earth
Engine (`earthengine authenticate` o cuenta de servicio):

    uv run rastrohg export-mapbiomas --out ../data/raw/mapbiomas/mapbiomas_mineria.geojson
"""
from __future__ import annotations

from pathlib import Path

import ee

from .earthengine import init, pilot_region

ASSET = "projects/mapbiomas-public/assets/bolivia/lulc/v1"
MINING_CLASS = 30
ANIO_DESDE = 2000


def latest_collection() -> ee.ImageCollection:
    """El asset mezcla ediciones (colección 3 y 4, ...): usar solo la más reciente."""
    col = ee.ImageCollection(ASSET)
    ids = [x for x in col.aggregate_array("collection_id").distinct().getInfo() if x is not None]
    latest = max(ids, key=lambda v: float(v))
    return col.filter(ee.Filter.eq("collection_id", latest))


def _mining_years(col: ee.ImageCollection, years: list[int]) -> ee.ImageCollection:
    def per_year(y):
        y = ee.Number(y)
        mosaic = col.filter(ee.Filter.eq("year", y)).mosaic().select("classification")
        return mosaic.eq(MINING_CLASS).selfMask().multiply(0).add(y).toInt16().rename("anio")
    return ee.ImageCollection(ee.List(years).map(per_year))


def export_mining_geojson(out: str, desde: int = ANIO_DESDE) -> dict:
    project = init()
    col = latest_collection()
    available = sorted({int(y) for y in col.aggregate_array("year").getInfo()})
    years = [y for y in available if y >= desde]
    if not years:
        raise RuntimeError("MapBiomas no tiene años disponibles en el rango pedido")

    per_year = _mining_years(col, years)
    last = per_year.max().rename("anio")
    first = per_year.min().rename("anio_inicio")

    region = pilot_region()
    vectors = last.addBands(first).reduceToVectors(
        geometry=region,
        scale=30,
        geometryType="polygon",
        eightConnected=True,
        labelProperty="anio",
        reducer=ee.Reducer.min(),          # agrega anio_inicio (mínimo) dentro de cada polígono
        maxPixels=1e10,
        tileScale=4,
    )
    gdf = ee.data.computeFeatures({"expression": vectors, "fileFormat": "GEOPANDAS_GEODATAFRAME"})
    gdf = gdf.set_crs(4326, allow_override=True)
    # reduceToVectors nombra la banda reducida "min"
    if "min" in gdf.columns:
        gdf = gdf.rename(columns={"min": "anio_inicio"})
    keep = [c for c in ("anio", "anio_inicio") if c in gdf.columns]
    gdf = gdf[keep + ["geometry"]]
    gdf["fuente"] = f"MapBiomas Bolivia ({ASSET}), clase {MINING_CLASS}"

    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(path, driver="GeoJSON")
    area_ha = float(gdf.to_crs(32719).area.sum() / 1e4) if len(gdf) else 0.0
    return {
        "proyecto_ee": project,
        "anios": f"{years[0]}–{years[-1]}",
        "poligonos": len(gdf),
        "area_ha": round(area_ha, 1),
        "por_ultimo_anio": gdf["anio"].value_counts().sort_index().to_dict() if len(gdf) else {},
        "archivo": str(path),
    }

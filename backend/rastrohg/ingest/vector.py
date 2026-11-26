"""Lectura de capas vectoriales (GeoJSON, GPKG, SHP, ZIP) desde URL o ruta local."""
from __future__ import annotations

import tempfile
from pathlib import Path

import geopandas as gpd
import httpx
from shapely.geometry import box

from ..settings import get_settings


def read_vector(src: str, layer: str | None = None, clip: bool = True) -> gpd.GeoDataFrame:
    s = get_settings()
    path = src
    if src.startswith(("http://", "https://")):
        suffix = Path(src.split("?")[0]).suffix or ".geojson"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        with httpx.stream("GET", src, timeout=300, follow_redirects=True,
                          headers={"User-Agent": s.http_user_agent}) as r:
            r.raise_for_status()
            for chunk in r.iter_bytes():
                tmp.write(chunk)
        tmp.close()
        path = tmp.name
    kwargs = {"bbox": s.bbox} if clip else {}
    if layer:
        kwargs["layer"] = layer
    gdf = gpd.read_file(path, engine="pyogrio", **kwargs)
    if gdf.crs is None:
        gdf = gdf.set_crs(4326)
    gdf = gdf.to_crs(4326)
    if clip:
        gdf = gdf[gdf.intersects(box(*s.bbox))]
    return gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()

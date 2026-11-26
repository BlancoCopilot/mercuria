"""Normaliza las capas gratuitas de GeoTienda Bolivia a columnas uniformes.

Entrada: data/raw/geotienda/<capa>/*.shp (descargadas el 2026-11-25)
Salida:  data/raw/geotienda/areas_protegidas_bolivia.gpkg (nombre, categoria, ambito)
         data/raw/geotienda/centros_mineros_pasivos.gpkg
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

D = Path(sys.argv[1])

nac = gpd.read_file(next((D / "ap_nacionales").glob("*.shp"))).to_crs(4326)
nac = gpd.GeoDataFrame({
    "nombre": nac["name"],
    "categoria": ["Nacional: " + json.loads(x).get("level_1", "") if isinstance(x, str) else "Nacional" for x in nac["nameLevels"]],
    "ambito": "nacional",
}, geometry=nac.geometry, crs=4326)

sub = gpd.read_file(next((D / "ap_subnacionales_2025").glob("*.shp"))).to_crs(4326)
sub = gpd.GeoDataFrame({
    "nombre": sub["nombre"],
    "categoria": "Subnacional: " + sub["cat"].fillna(""),
    "ambito": "subnacional",
}, geometry=sub.geometry, crs=4326)

ap = pd.concat([nac, sub], ignore_index=True)
ap["geometry"] = ap.geometry.make_valid()
ap.to_file(D / "areas_protegidas_bolivia.gpkg", driver="GPKG")
print("areas protegidas:", len(ap), ap["ambito"].value_counts().to_dict())

pas = gpd.read_file(next((D / "centros_mineros_pasivos").glob("*.shp"))).to_crs(4326)
pas.to_file(D / "centros_mineros_pasivos.gpkg", driver="GPKG")
print("centros mineros/pasivos:", len(pas))

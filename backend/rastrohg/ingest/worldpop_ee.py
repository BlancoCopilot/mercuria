"""Población estimada por poblado con WorldPop (Google Earth Engine).

No es el censo: es una ESTIMACIÓN modelada, que se usa mientras no se cargue el Censo 2024
del INE por comunidad (`rastrohg load-census`, que tiene prioridad y nunca se sobrescribe).

  * Población total 2024:  WorldPop/GP/100m/R2025A/v1/pop (año del Censo 2024)
  * Estructura por edad:   WorldPop/GP/100m/pop_age_sex_cons_unadj (2020, la última con edad y sexo)
      niños < 5      = M_0 + M_1 + F_0 + F_1
      mujeres 15–49  = F_15 + F_20 + ... + F_45
    Las proporciones de 2020 se aplican a la población 2024 de cada píxel.

Los píxeles (~100 m) se asignan al poblado de OSM más cercano dentro de `radio_m`.
La población dispersa más lejos de todo poblado se informa pero no se asigna.
Licencia WorldPop: CC-BY 4.0.

    uv run rastrohg load-worldpop --radio-m 3000
"""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree
from sqlalchemy import text

import ee

from ..db import rows, tx
from .earthengine import init, pilot_region

POP_ASSET = "WorldPop/GP/100m/R2025A/v1/pop"
AGESEX_ASSET = "WorldPop/GP/100m/pop_age_sex_cons_unadj"
POP_YEAR = 2024
SOURCE = f"worldpop{POP_YEAR}"
MIN_POP = 0.05   # personas por píxel de ~100 m (debajo de esto es ruido del modelo)


def _pixels() -> tuple[np.ndarray, np.ndarray]:
    """Píxeles de ~100 m con población 2024: coordenadas (lon, lat) y (pob, niños<5, mujeres 15–49).

    Se muestrean los valores crudos y las proporciones por edad se calculan aquí (en Earth
    Engine, combinar las dos fuentes píxel a píxel perdía la proyección nativa).
    """
    region = pilot_region()
    pop = (ee.ImageCollection(POP_ASSET).filter(ee.Filter.eq("country", "BOL"))
           .filter(ee.Filter.eq("year", POP_YEAR)).first().select("population"))
    a = ee.ImageCollection(AGESEX_ASSET).filter(ee.Filter.eq("country", "BOL")).first()
    img = (pop.rename("pob").updateMask(pop.gt(MIN_POP))
           .addBands(a.select("population").rename("t20").unmask(0))
           .addBands(a.select(["M_0", "M_1", "F_0", "F_1"]).reduce(ee.Reducer.sum()).rename("u5").unmask(0))
           .addBands(a.select(["F_15", "F_20", "F_25", "F_30", "F_35", "F_40", "F_45"])
                     .reduce(ee.Reducer.sum()).rename("w").unmask(0)))
    fc = img.sample(region=region, projection=pop.projection(), geometries=True, dropNulls=True, tileScale=4)
    gdf = ee.data.computeFeatures({"expression": fc, "fileFormat": "GEOPANDAS_GEODATAFRAME"})
    if gdf.empty:
        return np.empty((0, 2)), np.empty((0, 3))
    pob, t20, u5, w = (gdf[c].to_numpy(dtype=float) for c in ("pob", "t20", "u5", "w"))
    # proporción por edad del píxel en 2020; si no tenía población entonces, la de toda la cuenca
    has = t20 > 0
    share_u5 = np.where(has, u5 / np.where(has, t20, 1), u5.sum() / t20.sum())
    share_w = np.where(has, w / np.where(has, t20, 1), w.sum() / t20.sum())
    xy = np.column_stack([gdf.geometry.x.values, gdf.geometry.y.values])
    return xy, np.column_stack([pob, pob * share_u5, pob * share_w])


def load_worldpop(radio_m: int = 3000) -> dict:
    init()
    xy, vals = _pixels()
    with tx() as conn:
        conn.execute(text("ALTER TABLE settlement ADD COLUMN IF NOT EXISTS poblacion_fuente text"))
        sets = rows(conn, """SELECT id, ST_X(geom) AS lon, ST_Y(geom) AS lat, census_code
                             FROM settlement WHERE NOT is_synthetic""")
        if not sets or not len(xy):
            return {"poblados": len(sets), "pixeles": len(xy), "aviso": "nada que asignar"}
        lat0 = float(np.mean([s["lat"] for s in sets]))
        k = np.array([111_320 * np.cos(np.radians(lat0)), 110_540])   # grados -> metros
        tree = cKDTree(np.array([[s["lon"], s["lat"]] for s in sets]) * k)
        dist, idx = tree.query(xy * k, distance_upper_bound=radio_m)
        ok = np.isfinite(dist)
        acc = np.zeros((len(sets), 3))
        np.add.at(acc, idx[ok], vals[ok])

        updates = [{"id": s["id"], "pob": int(round(a[0])), "u5": int(round(a[1])), "muj": int(round(a[2])),
                    "src": SOURCE}
                   for s, a in zip(sets, acc) if not s["census_code"]]
        # el censo tiene prioridad: solo se tocan poblados sin código INE
        conn.execute(text("""UPDATE settlement SET poblacion=:pob, ninos_u5=:u5, mujeres_15_49=:muj,
                                    poblacion_fuente=:src WHERE id=:id AND census_code IS NULL"""), updates)
        from .base import build_cells
        build_cells(conn)
    return {
        "fuente": f"{POP_ASSET} ({POP_YEAR}) + estructura por edad {AGESEX_ASSET} (2020)",
        "pixeles_100m": int(len(xy)),
        "poblacion_cuenca": int(vals[:, 0].sum()),
        "poblacion_asignada": int(vals[ok, 0].sum()),
        "poblacion_dispersa_sin_poblado": int(vals[~ok, 0].sum()),
        "poblados_actualizados": len(updates),
        "poblados_con_poblacion": int((acc[:, 0] >= 1).sum()),
        "ninos_u5": int(acc[:, 1].sum()),
        "mujeres_15_49": int(acc[:, 2].sum()),
        "radio_m": radio_m,
    }

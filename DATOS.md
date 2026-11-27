# Datos reales de la cuenca piloto (Tipuani–Mapiri–Kaká)

Cargados el 25/11/2026. Orden de carga: ríos → poblados → población → minería → recálculo.

| Capa | Fuente | Licencia | Cómo se actualiza |
|---|---|---|---|
| Ríos (1703 tramos) | [HydroRIVERS v1.0](https://www.hydrosheds.org/products/hydrorivers), Sudamérica | CC-BY 4.0 | Fija. `rastrohg load-hydrorivers /data/raw/hydrorivers/HydroRIVERS_v10_sa_shp/HydroRIVERS_v10_sa.shp` |
| Poblados, salud, agua (679 / 82 / 4) | OpenStreetMap vía Overpass | ODbL | Cron mensual (`ingest osm`); solo centros de salud: `load-salud` (hospitales, centros, puestos y consultorios; sin farmacias ni dentistas; 0,4° de margen alrededor de la cuenca) |
| Población por poblado | **Estimación** WorldPop: total 2024 ([R2025A](https://developers.google.com/earth-engine/datasets/catalog/WorldPop_GP_100m_R2025A_v1_pop)) × estructura por edad 2020 | CC-BY 4.0 | Manual, con Earth Engine: `uv run rastrohg load-worldpop` |
| Minería, Amazon Mining Watch (1705 detecciones) | [Earth Genome](https://source.coop/earthgenome/amazon-mining-watch), `AMW_URL` | CC-BY 4.0 | Cron mensual (`ingest amw`), descarga el archivo oficial |
| Minería, MapBiomas Bolivia (2605 polígonos) | `projects/mapbiomas-public/assets/bolivia/lulc/v1`, clase 30, colección más reciente | CC-BY 4.0 | Una vez al año, con Earth Engine: `uv run rastrohg export-mapbiomas --out ../data/raw/mapbiomas/mapbiomas_mineria.geojson`; el cron anual (`ingest mapbiomas`) carga ese archivo |

## Población: estimación vs. censo
`settlement.poblacion_fuente` indica de dónde sale cada cifra: `worldpop2024` (estimación) o `censo2024`.
El Censo 2024 por comunidad no tiene descarga abierta: la API del geoportal del INE responde
"restringido" sin sesión. Para usarlo, exporta la tabla desde el [geoportal](https://geoportal.ine.gob.bo)
o [REDATAM](https://redatam.ine.gob.bo) con columnas
`codigo,nombre,lat,lon,poblacion,ninos_u5,mujeres_15_49[,municipio]` y cárgala con
`rastrohg load-census /data/raw/censo.csv`. El censo tiene prioridad y `load-worldpop` nunca lo sobrescribe.

## Earth Engine
Hoy funciona en la Mac (credenciales de `earthengine authenticate`). Los comandos que lo usan
(`export-mapbiomas`, `load-worldpop`) se corren desde `backend/` con `uv run` y la base en
`localhost:5433`:

```sh
cd backend
set -a; source ../.env; set +a
export DATABASE_URL="postgresql+psycopg://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:5433/$POSTGRES_DB"
export RASTROHG_CONFIG_DIR=$PWD/config
uv run rastrohg load-worldpop
```

Para el servidor: crea una cuenta de servicio en tu proyecto de Google Cloud (`EE_PROJECT` en `.env`),
regístrala en Earth Engine, monta el JSON en el contenedor y apunta `EE_SERVICE_ACCOUNT_KEY` a él.

## Advertencias
- Las áreas mineras salen grandes: AMW detecta parches de 480 m × 480 m. Sirven para ubicar
  la minería y estimar su presión; no son una medición precisa de superficie.
- Sin concesiones (AJAM) ni áreas protegidas (SERNAP) cargadas, el estado legal de cada sitio
  es `indeterminado`.
- No hay mediciones de laboratorio: el mapa de mercurio usa solo la presión minera, con
  intervalos amplios (p05–p95).

## Puertos locales
5432 y 8080 ya los usan otros proyectos en esta Mac. RastroHg usa la base en `127.0.0.1:5433`,
la API en `:8000` y Caddy en `:8090` (ver `docker-compose.override.yml`).

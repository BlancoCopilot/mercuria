<p align="center"><img src="panel/public/logo-mercuria@large.png" alt="MercurIA" width="320"></p>

# MercurIA

**Dónde hay mercurio de la minería aurífera en Bolivia, con qué certeza, y qué hacer.**

Plataforma abierta para el hackathon *Gold for Good* (retos 3 y 4):

- **Detecta** la minería con satélite (Amazon Mining Watch, MapBiomas) y la cruza con áreas protegidas y concesiones.
- **Estima** cuánto mercurio libera cada sitio y cuánto llega a cada tramo de río (agua, sedimento y peces), siempre con su rango de incertidumbre.
- **Traduce** eso a riesgo por comunidad y a acciones: qué pescado comer, qué hacer, adónde ir; avisos por ubicación; promotores de salud; denuncias anónimas sin señal.
- **Abre los datos**: cualquiera los descarga en *Datos abiertos*, y universidades e investigadores pueden **aportar sus estudios** (PDF o CSV): una IA propone los puntos, el autor los revisa y se publican con su cita.

> El nombre interno del código y la base de datos es `rastrohg`.

| | |
|---|---|
| Backend | FastAPI · PostgreSQL/PostGIS/pgvector · Redis + RQ · motor estadístico propio (kriging en red fluvial, H3) |
| Web | Vite + React + TypeScript · MapLibre · h3-js |
| IA | OpenAI (chat con fuentes, RAG) y extracción de datos de PDFs con salida estructurada |
| Despliegue | Un VPS con Docker Compose y Caddy (HTTPS automático) |

## Arranque rápido

```bash
cp .env.example .env            # completar POSTGRES_PASSWORD y JWT_SECRET
docker compose up -d --build    # en local usa docker-compose.override.yml (puertos en 127.0.0.1)
docker compose exec api rastrohg seed-synthetic      # cuenca SINTÉTICA + usuarios demo
cd backend && uv run python ../scripts/demo.py       # los 6 pasos de la demo
```

- API: http://localhost:8000/docs (Swagger) · vía Caddy: http://localhost:8090
- Usuarios demo (solo local): `{admin,laboratorio,promotor,lider,autoridad,investigador}@demo.rastrohg` / `demo-rastrohg-2026`.
  ⚠️ **Nunca corras `seed-synthetic` en un servidor público**: estas credenciales están en este repositorio.
  En producción crea las cuentas con `rastrohg create-user` y contraseñas propias.
- La web compilada (`panel/dist`) no se versiona: `cd panel && npm install && npm run build` antes de levantar Caddy.
- `rastrohg purge-synthetic` borra **todo** lo sintético antes de trabajar con datos reales.
  No mezcles las dos cosas en la misma base: la cuenca sintética está dentro del bbox piloto y se cruza con HydroRIVERS real.

### Tests

```bash
cd backend
uv run pytest tests/test_engine.py                       # motor, sin base de datos
RASTROHG_TEST_PG=postgresql://rastrohg:<pass>@localhost:5433 uv run pytest   # + integración en una base aislada (rastrohg_test)
```

## Chat con Gota: texto, voz e internet

- **Texto** (`POST /v1/chat`): búsqueda híbrida en los documentos (pgvector + texto) y respuesta con citas. Si los documentos no responden, el modelo usa `web_search` de OpenAI, prefiere fuentes oficiales y lo dice ("Según lo que encontré en internet…"); las fuentes web se muestran como enlaces. Se apaga con `CHAT_WEB_SEARCH=false`.
- **Voz en tiempo real** (botón *Hablar*): GPT-Live (`gpt-live-1.1`) por WebRTC. El servidor crea la sesión con la oferta SDP del navegador (`POST /v1/chat/voz`), así la clave nunca llega al navegador. GPT-Live conversa y delega cada pregunta a un modelo de texto que llama a `buscar_documentos` (lo atiende el navegador con `POST /v1/chat/voz/buscar`) y, si hace falta, a `web_search`. Lo hablado queda transcrito en el mismo chat. Necesita HTTPS (o `localhost`) para el micrófono.
- Costo de la voz: USD 0,05 por minuto activo (0,02 en espera) más los tokens del modelo de texto. Límites: `LIVE_MAX_MINUTES` por llamada, `LIVE_PER_IP_HOUR` y `LIVE_GLOBAL_PER_HOUR`.

## Aportes de investigación y datos abiertos

- `/aportar`: universidades e investigadores solicitan cuenta (un admin la activa en `/admin`), suben un PDF o CSV y la IA (`backend/rastrohg/research/`) propone cada medición con su página, cita textual y confianza. El autor revisa, ubica los sitios sin coordenadas y publica con licencia CC BY 4.0, CC0 o CC BY-SA 4.0, con embargo opcional de hasta 12 meses.
- `/datos`: descarga libre de mediciones (CSV/GeoJSON), riesgo por zona, estimaciones por tramo de río, sitios mineros y estudios. La API está en `/v1/open/…`.
- Datos de personas: solo agregados de 5 o más. Las denuncias se publican solo como zona.

## Licencias de los datos

Las fuentes y licencias de cada capa están en [`DATOS.md`](DATOS.md), [`data/raw/mediciones/FUENTES.md`](data/raw/mediciones/FUENTES.md) y [`data/raw/geotienda/LEEME.md`](data/raw/geotienda/LEEME.md). Los archivos grandes o de terceros (HydroRIVERS, AMW, PDFs del chatbot) no están en el repositorio: se descargan con los comandos indicados ahí.

## Web (panel/)

Vite + React + TypeScript + MapLibre + h3-js. Estilo "cuaderno de campo": crema, verde pino, una sola barra caléndula por pantalla. El contexto de diseño está en `PRODUCT.md` y `DESIGN.md`.

```bash
cd panel && npm install
npm run dev      # http://localhost:5173 (proxy de /v1 a la API local)
npm run build    # genera panel/dist, que Caddy sirve en http://localhost:8090
```

| Ruta | Para quién | Qué hace |
|---|---|---|
| `/` | todos | Mapa de riesgo H3 (las zonas pálidas significan "no sabemos bien"), ríos por matriz y sitios mineros (hueco = en área protegida); panel lateral en escritorio y hoja inferior en celular |
| `/comunidades`, `/comunidad/:id` | comunidades | Buscar o ubicarse; ficha con nivel, pescado (comidas por semana), qué hacer, centro de salud y audio frase por frase |
| `/denunciar` | todos | Denuncia anónima que funciona sin señal: se guarda y se envía al volver la conexión |
| `/preguntar` | todos | Chat con fuentes citadas |
| `/panel` | autoridad | Datos clave, muestreo sugerido en mapa, campañas de salud, recuperación del ecosistema, indicadores mensuales |
| `/laboratorio` | laboratorio | Carga de CSV con el resultado de cada fila; lista de mediciones |
| `/salud` | promotor | Caso con consentimiento obligatorio, triaje, derivación, recordatorios y campañas de cabello |
| `/validar` | líder | Denuncias (ubicación exacta y foto) y traducciones con audio |
| `/admin` | admin | Versiones del mapa, recálculo, ingestas, avisos y cuentas |

## Datos reales

| Capa | Comando | Fuente |
|---|---|---|
| Ríos | `rastrohg load-hydrorivers /data/raw/hydrorivers/.../HydroRIVERS_v10_sa.shp [--outlet HYRIV_ID]` | HydroSHEDS |
| Poblados, salud, tomas, pesca | `rastrohg load-osm` (o `--file overpass.json`) | OSM / Overpass |
| Censo 2024 | `rastrohg load-census censo.csv` (codigo,nombre,lat,lon,poblacion,ninos_u5,mujeres_15_49) | INE |
| Concesiones / áreas protegidas | `rastrohg load-concessions …` / `load-protected …` | AJAM, RAISG, GeoTienda / SERNAP |
| Minería | `rastrohg ingest amw` / `ingest mapbiomas` (`AMW_URL`, `MAPBIOMAS_URL`) | Amazon Mining Watch, MapBiomas clase 30 |
| Mediciones publicadas | `rastrohg load-measurements publicadas.csv` (plantilla: `GET /v1/measurements/template.csv`) | Estudios con cita |

## Estructura

```
docker-compose.yml          caddy · api · worker · cron · db · redis (solo Caddy expone 80/443)
docker-compose.override.yml solo desarrollo: puertos locales y código montado
Caddyfile                   HTTPS, /v1 → API, /tiles → PMTiles, / → panel; sin logs de acceso
db/Dockerfile               Postgres 16 + PostGIS + pgvector (paquetes PGDG, multi-arquitectura)
db/init/*.sql               esquema (se aplica al crear el volumen) · db/migrations/ cambios posteriores
backend/
  config/params.yaml        TODOS los supuestos numéricos, con marcas VERIFICAR/CALIBRAR
  config/fish_species.yaml  especies y nivel trófico · health_protocol.yaml  triaje (borrador)
  rastrohg/engine/          motor puro (sin BD): emisiones, red, presión, kriging, riesgo, muestreo, pescado
  rastrohg/worker/          pipeline BD→motor→versión, cola RQ, push (outbox)
  rastrohg/ingest/          HydroRIVERS, OSM, censo, concesiones, detecciones (AMW/MapBiomas/denuncias), H3
  rastrohg/services/        carga de mediciones, ficha "Mi comunidad", triaje
  rastrohg/api/             FastAPI: routers por módulo, auth JWT, token de dispositivo
  rastrohg/synthetic.py     cuenca sintética de ensayo (todo con is_synthetic = true)
  crontab                   tareas programadas (supercronic)
scripts/demo.py             guion de la demo
```

## Decisiones (y por qué)

**Motor**
- **Emisiones por Monte Carlo** (`engine/emissions.py`): área × rendimiento de oro × razón Hg:Au por técnica × actividad. El resultado es siempre un rango p05–p50–p95. La semilla es fija por sitio, así que recalcular sin datos nuevos da lo mismo.
- **Presión río abajo** (`pressure.py`): Σ confianza × Hg al agua × e^(−d/L). Usamos el Hg estimado y no el área sola porque incluye técnica, actividad y confianza (una denuncia pesa 0,2).
- **Kriging en red fluvial, no euclidiano** (`kriging.py`): la covarianza "tail-up" solo correlaciona tramos conectados por el flujo. Dos tributarios vecinos que se juntan más abajo no se influyen entre sí. pykrige no permite eso ni un error distinto por dato (laboratorio 1, kit 0,5), así que el kriging está escrito con numpy en unas 100 líneas.
- **Regresión bayesiana con prior físico**: sin datos, el mapa sale del fondo natural más un balance de masa, con mucha incertidumbre. Con datos, β se calibra solo. Hay un modelo por matriz (agua, sedimento, pez) y nunca se mezclan.
- **Calibración congelada**: β y los hiperparámetros se recalibran solo cuando llegan mediciones. Una mina nueva cambia **exactamente** los tramos río abajo; hay un test que lo verifica.
- **Peligro anclado en el fondo natural**: 0 en el fondo, 0,5 en el valor de referencia, 1 en 10× la referencia. Sin esto, todo río amazónico salía con peligro "medio" por el mercurio natural del pescado.
- **Riesgo = (P·E·V)^⅓** por celda H3 res 7. La confianza es la probabilidad (Monte Carlo) de que la celda esté en la clase mostrada; si es menor a 0,6, la celda se pinta pálida.
- **Muestreo**: se elige el tramo que más reduce la varianza ponderada por población. En un modelo gaussiano eso no depende del valor que se vaya a medir, así que se calcula antes de salir al campo. La selección es voraz: el segundo punto no repite la información del primero.

**Datos y actualización**
- **SQL a la vista, sin ORM**: casi toda la lógica espacial es PostGIS.
- **Versiones delta**: `cell_risk` guarda una fila por celda solo cuando cambia. El teléfono pide `?since=v` y baja solo lo que cambió. La capa de riesgo viaja como ids H3 (el teléfono las dibuja con h3-js); PMTiles queda para el mapa base.
- **Recálculo coalescido y en serie**: 50 resultados en un CSV generan un solo recálculo. Un worker y un lock de Postgres garantizan que dos versiones nunca compitan.
- **Encolar después del commit** (`Db.after_commit`): así el worker nunca lee la base antes de que existan los datos nuevos.
- **Outbox de push**: las alertas se escriben en la misma transacción que la versión, y cron reintenta los envíos.

**Privacidad y seguridad**
- Denuncias anónimas: el teléfono guarda un token; el servidor solo guarda su SHA-256. La IP se usa hasheada y solo para el límite de registros; no se guarda. Caddy no escribe logs de acceso.
- Las fotos se re-codifican desde los píxeles, sin EXIF, GPS, XMP ni ICC (hay un test).
- Mapa público: las denuncias y los sitios que vienen de una denuncia se muestran como celda H3, nunca como punto exacto. Solo los líderes ven la ubicación exacta para validar.
- Salud: sin consentimiento no se guarda nada (validado en la API y con un CHECK en la base). No se guardan nombre ni CI. Cada promotor ve solo sus casos, y las autoridades ven solo agregados de 5 casos o más.
- Lenguaje: "sin concesión registrada" en vez de "ilegal", porque esa determinación le corresponde a una autoridad.
- Lo sintético siempre lleva `is_synthetic` y se purga con un comando.

## Pendiente / a validar antes de publicar a comunidades

1. `params.yaml`: rendimiento de oro por ha (calibrar con SENARECOM y el área de AMW), razones Hg:Au, fracción al agua, fondos y referencias (NB 512, Codex, CCME).
2. `health_protocol.yaml`: reemplazarlo por el protocolo oficial del Ministerio de Salud (hoy `validado: false`).
3. Consejo de pescado (JECFA 1,6 µg/kg/semana): validarlo con autoridades de salud.
4. Grabar los audios en aymara, quechua y guaraní, frase por frase (`/v1/translations`), y que los validen líderes.
5. Fase 2: RAG (pgvector ya está instalado), generación de PMTiles del mapa base, panel web y app Expo.

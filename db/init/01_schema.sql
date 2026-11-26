-- RastroHg — esquema MVP
-- Convenciones:
--   * Geometrías en EPSG:4326. Áreas y distancias con ::geography (metros reales).
--   * is_synthetic marca todo dato inventado para la demo. Nunca se mezcla en silencio.
--   * client_uuid = id generado en el teléfono: hace idempotente la sincronización offline.

------------------------------------------------------------------------------
-- 1. BASE FIJA
------------------------------------------------------------------------------
CREATE TABLE river_reach (
    hyriv_id      bigint PRIMARY KEY,           -- HydroRIVERS HYRIV_ID
    next_down     bigint NOT NULL DEFAULT 0,    -- 0 = desembocadura
    main_riv      bigint,
    length_km     double precision NOT NULL,
    dist_dn_km    double precision,
    upland_skm    double precision NOT NULL,
    dis_av_cms    double precision NOT NULL,
    ord_stra      smallint,
    name          text,
    geom          geometry(LineString, 4326) NOT NULL,
    is_synthetic  boolean NOT NULL DEFAULT false
);
CREATE INDEX ON river_reach (next_down);
CREATE INDEX ON river_reach USING gist (geom);

CREATE TABLE h3_cell (
    h3            text PRIMARY KEY,
    res           smallint NOT NULL,
    geom          geometry(Polygon, 4326) NOT NULL,
    -- insumos precalculados (se refrescan cuando cambian OSM o censo)
    poblacion     integer NOT NULL DEFAULT 0,
    ninos_u5      integer NOT NULL DEFAULT 0,
    mujeres_15_49 integer NOT NULL DEFAULT 0,
    comidas_pescado_semana real,                 -- de encuestas (módulo 9); null = valor por defecto
    n_tomas_agua  integer NOT NULL DEFAULT 0,
    n_zonas_pesca integer NOT NULL DEFAULT 0,
    exposure      real NOT NULL DEFAULT 0,
    vulnerability real NOT NULL DEFAULT 0
);
CREATE INDEX ON h3_cell USING gist (geom);

-- Qué tramos tocan cada celda (ring 0). Se calcula una vez al cargar la red.
CREATE TABLE reach_cell (
    reach_id  bigint REFERENCES river_reach ON DELETE CASCADE,
    h3        text REFERENCES h3_cell ON DELETE CASCADE,
    PRIMARY KEY (reach_id, h3)
);
CREATE INDEX ON reach_cell (h3);

CREATE TABLE settlement (
    id            serial PRIMARY KEY,
    name          text NOT NULL,
    kind          text,                          -- city/town/village/hamlet
    census_code   text UNIQUE,                   -- código INE (Censo 2024)
    osm_id        text UNIQUE,
    municipio     text,
    poblacion     integer,
    ninos_u5      integer,
    mujeres_15_49 integer,
    poblacion_fuente text,                       -- censo2024 | worldpop2024 (estimación) | osm
    h3            text,
    geom          geometry(Point, 4326) NOT NULL,
    source        text NOT NULL,
    is_synthetic  boolean NOT NULL DEFAULT false
);
CREATE INDEX ON settlement USING gist (geom);
CREATE INDEX ON settlement USING gin (name gin_trgm_ops);

CREATE TABLE exposure_feature (
    id            serial PRIMARY KEY,
    kind          text NOT NULL CHECK (kind IN ('toma_agua', 'zona_pesca')),
    name          text,
    osm_id        text UNIQUE,
    h3            text,
    geom          geometry(Geometry, 4326) NOT NULL,
    source        text NOT NULL,
    is_synthetic  boolean NOT NULL DEFAULT false
);
CREATE INDEX ON exposure_feature USING gist (geom);

CREATE TABLE health_facility (
    id            serial PRIMARY KEY,
    name          text NOT NULL,
    level         text,                          -- 1er/2do/3er nivel
    phone         text,
    osm_id        text UNIQUE,
    geom          geometry(Point, 4326) NOT NULL,
    source        text NOT NULL,
    is_synthetic  boolean NOT NULL DEFAULT false
);
CREATE INDEX ON health_facility USING gist (geom);

CREATE TABLE concession (
    id            serial PRIMARY KEY,
    code          text,
    holder        text,
    status        text,                          -- vigente / en trámite / ...
    mineral       text,
    valid_from    date,
    valid_to      date,
    geom          geometry(MultiPolygon, 4326) NOT NULL,
    source        text NOT NULL                  -- AJAM / RAISG / GeoTienda
);
CREATE INDEX ON concession USING gist (geom);

CREATE TABLE protected_area (
    id            serial PRIMARY KEY,
    name          text NOT NULL,
    category      text,
    geom          geometry(MultiPolygon, 4326) NOT NULL,
    source        text NOT NULL
);
CREATE INDEX ON protected_area USING gist (geom);

------------------------------------------------------------------------------
-- 2. SITIOS MINEROS (módulo 1) Y EMISIONES (módulo 2a)
------------------------------------------------------------------------------
CREATE TABLE mining_site (
    id               serial PRIMARY KEY,
    name             text,
    first_detected   date,
    last_detected    date,
    area_ha          double precision NOT NULL,
    -- No decimos "ilegal": eso lo determina una autoridad. Decimos lo que muestran los datos.
    legal_status     text NOT NULL DEFAULT 'indeterminado'
                     CHECK (legal_status IN ('con_concesion', 'sin_concesion', 'en_area_protegida', 'indeterminado')),
    concession_id    integer REFERENCES concession,
    protected_area_id integer REFERENCES protected_area,
    reach_id         bigint REFERENCES river_reach,   -- tramo al que drena (más cercano)
    snap_distance_m  double precision,
    origin           text NOT NULL CHECK (origin IN ('satelite', 'denuncia', 'manual')),
    confianza        real NOT NULL DEFAULT 1.0,       -- 1 satélite, 0.2 denuncia
    mezcla_tecnicas  jsonb,                           -- null = mezcla por defecto
    status           text NOT NULL DEFAULT 'activo' CHECK (status IN ('activo', 'inactivo', 'descartado')),
    geom             geometry(MultiPolygon, 4326) NOT NULL,
    is_synthetic     boolean NOT NULL DEFAULT false,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON mining_site USING gist (geom);

CREATE TABLE mining_detection (
    id            serial PRIMARY KEY,
    source        text NOT NULL CHECK (source IN ('amw', 'mapbiomas', 'denuncia', 'manual')),
    source_ref    text NOT NULL,                 -- id de la fuente o hash de la geometría
    detected_on   date NOT NULL,
    area_ha       double precision NOT NULL,
    geom          geometry(MultiPolygon, 4326) NOT NULL,
    site_id       integer REFERENCES mining_site ON DELETE SET NULL,
    ingested_at   timestamptz NOT NULL DEFAULT now(),
    is_synthetic  boolean NOT NULL DEFAULT false,
    UNIQUE (source, source_ref)
);
CREATE INDEX ON mining_detection USING gist (geom);

CREATE TABLE site_emission (
    site_id       integer PRIMARY KEY REFERENCES mining_site ON DELETE CASCADE,
    hg_total_p05  double precision, hg_total_p50 double precision, hg_total_p95 double precision,
    hg_agua_p05   double precision, hg_agua_p50  double precision, hg_agua_p95  double precision,
    hg_agua_media double precision NOT NULL,
    detalle       jsonb,
    params_hash   text NOT NULL,
    computed_at   timestamptz NOT NULL DEFAULT now()
);

------------------------------------------------------------------------------
-- 3. MEDICIONES (módulo 4)
------------------------------------------------------------------------------
CREATE TABLE lab (
    id     serial PRIMARY KEY,
    name   text NOT NULL UNIQUE,
    accredited boolean NOT NULL DEFAULT false
);

CREATE TABLE measurement (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    matrix         text NOT NULL CHECK (matrix IN ('agua', 'sedimento', 'pez')),
    value          double precision NOT NULL CHECK (value > 0),   -- unidad canónica de la matriz
    unit           text NOT NULL,                                 -- canónica: ug/L | mg/kg
    value_original double precision NOT NULL,
    unit_original  text NOT NULL,
    hg_species     text NOT NULL DEFAULT 'total' CHECK (hg_species IN ('total', 'metil')),
    below_dl       boolean NOT NULL DEFAULT false,
    source_type    text NOT NULL CHECK (source_type IN ('laboratorio', 'publicado', 'kit')),
    weight         real NOT NULL,
    lab_id         integer REFERENCES lab,
    method         text,
    fish_species   text,                         -- código de config/fish_species.yaml
    fish_group     text,                         -- carnivoro/omnivoro/...; valor normalizado a carnívoro
    reference      text,                         -- cita / DOI si es publicado
    sampled_on     date,
    geom           geometry(Point, 4326) NOT NULL,
    reach_id       bigint REFERENCES river_reach,
    snap_distance_m double precision,
    status         text NOT NULL DEFAULT 'valido' CHECK (status IN ('valido', 'en_revision', 'rechazado')),
    season         text CHECK (season IN ('seca', 'humeda')),   -- null = desconocida
    notes          text,                         -- procedencia: precisión de ubicación, advertencias
    reach_forced   boolean NOT NULL DEFAULT false,  -- tramo indicado a mano (no por cercanía)
    covariate_u    double precision,             -- covariable congelada en la última calibración
    calibrated_at  timestamptz,
    batch_id       uuid,
    uploaded_by    integer,
    is_synthetic   boolean NOT NULL DEFAULT false,
    created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON measurement (matrix, status);
CREATE INDEX ON measurement USING gist (geom);

------------------------------------------------------------------------------
-- 4. MODELO Y VERSIONES DEL MAPA (módulos 2b, 3, 5)
------------------------------------------------------------------------------
CREATE TABLE map_version (
    id                 serial PRIMARY KEY,
    created_at         timestamptz NOT NULL DEFAULT now(),
    triggers           jsonb NOT NULL,           -- [{"tipo":"sitio","ref":12}, ...]
    reaches_changed    integer NOT NULL,
    cells_changed      integer NOT NULL,
    params_hash        text NOT NULL,
    model_info         jsonb                     -- hiperparámetros usados por matriz, n datos
);

CREATE TABLE reach_pressure (
    reach_id    bigint REFERENCES river_reach ON DELETE CASCADE,
    matrix      text NOT NULL,
    pressure    double precision NOT NULL,       -- kg/año equivalentes
    PRIMARY KEY (reach_id, matrix)
);

-- Estado actual por tramo y matriz + versión en que cambió por última vez.
CREATE TABLE reach_estimate (
    reach_id    bigint REFERENCES river_reach ON DELETE CASCADE,
    matrix      text NOT NULL CHECK (matrix IN ('agua', 'sedimento', 'pez')),
    log_mu      double precision NOT NULL,
    log_sd      double precision NOT NULL,
    p05         double precision NOT NULL,
    p50         double precision NOT NULL,
    p95         double precision NOT NULL,
    n_cercanos  integer NOT NULL,
    version_id  integer NOT NULL REFERENCES map_version,
    PRIMARY KEY (reach_id, matrix)
);

-- Historial delta: una fila por celda SOLO cuando cambia. El teléfono pide "desde v".
CREATE TABLE cell_risk (
    h3            text REFERENCES h3_cell ON DELETE CASCADE,
    version_id    integer REFERENCES map_version,
    hazard        real NOT NULL,
    exposure      real NOT NULL,
    vulnerability real NOT NULL,
    risk          real NOT NULL,
    risk_class    text NOT NULL CHECK (risk_class IN ('bajo', 'medio', 'alto')),
    confidence    real NOT NULL,
    p_alto        real NOT NULL,
    palida        boolean NOT NULL,
    drivers       jsonb,
    PRIMARY KEY (h3, version_id)
);
CREATE INDEX ON cell_risk (version_id);

CREATE VIEW cell_risk_current AS
SELECT DISTINCT ON (h3) * FROM cell_risk ORDER BY h3, version_id DESC;

CREATE TABLE sampling_suggestion (
    id            serial PRIMARY KEY,
    version_id    integer NOT NULL REFERENCES map_version,
    matrix        text NOT NULL,
    rank          smallint NOT NULL,
    reach_id      bigint NOT NULL REFERENCES river_reach,
    geom          geometry(Point, 4326) NOT NULL,
    reduccion_varianza real NOT NULL,
    var_antes     real NOT NULL,
    nearest_settlement text,
    created_at    timestamptz NOT NULL DEFAULT now()
);

------------------------------------------------------------------------------
-- 5. USUARIOS, DISPOSITIVOS Y PARTICIPACIÓN (módulo 9)
------------------------------------------------------------------------------
CREATE TABLE app_user (
    id            serial PRIMARY KEY,
    email         text NOT NULL UNIQUE,
    name          text NOT NULL,
    role          text NOT NULL CHECK (role IN ('admin', 'laboratorio', 'promotor', 'lider', 'autoridad')),
    org           text,
    lab_id        integer REFERENCES lab,
    settlement_id integer REFERENCES settlement,   -- comunidad del líder / promotor
    password_hash text NOT NULL,
    active        boolean NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- Anónimo: solo el hash del token. Ningún dato personal.
CREATE TABLE device (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    token_hash    text NOT NULL UNIQUE,
    platform      text,
    push_token    text,
    lang          text NOT NULL DEFAULT 'es' CHECK (lang IN ('es', 'ay', 'qu', 'gn')),
    banned        boolean NOT NULL DEFAULT false,
    created_at    timestamptz NOT NULL DEFAULT now(),
    last_seen     timestamptz
);

CREATE TABLE device_subscription (
    device_id  uuid REFERENCES device ON DELETE CASCADE,
    h3         text REFERENCES h3_cell ON DELETE CASCADE,
    PRIMARY KEY (device_id, h3)
);

CREATE TABLE report (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_uuid     uuid NOT NULL UNIQUE,
    device_id       uuid REFERENCES device ON DELETE SET NULL,
    kind            text NOT NULL CHECK (kind IN ('mineria', 'agua_turbia', 'peces_muertos', 'salud', 'otro')),
    description     text,
    geom            geometry(Point, 4326) NOT NULL,   -- exacta: solo la ven líderes/admin
    h3              text NOT NULL,                    -- difuminada: lo único público
    area_ha         real,                             -- estimación del denunciante (opcional)
    photo_path      text,
    status          text NOT NULL DEFAULT 'pendiente' CHECK (status IN ('pendiente', 'validada', 'rechazada')),
    validated_by    integer REFERENCES app_user,
    validated_at    timestamptz,
    site_id         integer REFERENCES mining_site ON DELETE SET NULL,
    created_client_at timestamptz NOT NULL,           -- cuándo se hizo (quizás en modo avión)
    received_at     timestamptz NOT NULL DEFAULT now(),
    is_synthetic    boolean NOT NULL DEFAULT false
);
CREATE INDEX ON report (status);
CREATE INDEX ON report (h3);

CREATE TABLE fish_survey (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_uuid     uuid NOT NULL UNIQUE,
    device_id       uuid REFERENCES device ON DELETE SET NULL,
    settlement_id   integer REFERENCES settlement,
    h3              text NOT NULL,
    comidas_semana  real NOT NULL CHECK (comidas_semana BETWEEN 0 AND 30),
    especies        text[] NOT NULL DEFAULT '{}',
    created_client_at timestamptz NOT NULL,
    received_at     timestamptz NOT NULL DEFAULT now(),
    is_synthetic    boolean NOT NULL DEFAULT false
);

-- Textos de la ficha y su audio grabado/validado por líderes (módulo 6/9)
CREATE TABLE translation (
    id            serial PRIMARY KEY,
    key           text NOT NULL,
    lang          text NOT NULL CHECK (lang IN ('es', 'ay', 'qu', 'gn')),
    text          text NOT NULL,
    audio_path    text,
    status        text NOT NULL DEFAULT 'borrador' CHECK (status IN ('borrador', 'validada')),
    validated_by  integer REFERENCES app_user,
    UNIQUE (key, lang)
);

------------------------------------------------------------------------------
-- 6. SALUD Y SEGUIMIENTO (módulo 8)
-- Minimización: sin nombre, sin CI, sin fecha de nacimiento. El promotor guarda
-- su propio código local si necesita reconocer a la persona.
------------------------------------------------------------------------------
CREATE TABLE health_case (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_uuid     uuid NOT NULL UNIQUE,
    promotor_id     integer NOT NULL REFERENCES app_user,
    settlement_id   integer NOT NULL REFERENCES settlement,
    consent_given   boolean NOT NULL CHECK (consent_given),   -- sin consentimiento no se guarda
    consent_at      timestamptz NOT NULL,
    age_group       text NOT NULL CHECK (age_group IN ('0-4', '5-14', '15-49', '50+')),
    sex             text CHECK (sex IN ('f', 'm', 'otro')),
    pregnant        boolean NOT NULL DEFAULT false,
    symptoms        text[] NOT NULL DEFAULT '{}',
    alarm_signs     text[] NOT NULL DEFAULT '{}',
    exposures       text[] NOT NULL DEFAULT '{}',
    triage          text NOT NULL CHECK (triage IN ('rutina', 'prioritario', 'urgente')),
    status          text NOT NULL DEFAULT 'registrado'
                    CHECK (status IN ('registrado', 'derivado', 'atendido', 'seguimiento', 'cerrado')),
    created_client_at timestamptz NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    is_synthetic    boolean NOT NULL DEFAULT false
);

CREATE TABLE referral (
    id            serial PRIMARY KEY,
    case_id       uuid NOT NULL REFERENCES health_case ON DELETE CASCADE,
    facility_id   integer NOT NULL REFERENCES health_facility,
    reason        text,
    referred_at   timestamptz NOT NULL DEFAULT now(),
    outcome       text,
    outcome_at    timestamptz
);

CREATE TABLE followup_reminder (
    id          serial PRIMARY KEY,
    case_id     uuid NOT NULL REFERENCES health_case ON DELETE CASCADE,
    due_on      date NOT NULL,
    kind        text NOT NULL,
    done_at     timestamptz
);
CREATE INDEX ON followup_reminder (due_on) WHERE done_at IS NULL;

CREATE TABLE hair_campaign (
    id              serial PRIMARY KEY,
    name            text NOT NULL,
    settlement_id   integer NOT NULL REFERENCES settlement,
    planned_on      date NOT NULL,
    status          text NOT NULL DEFAULT 'planificada' CHECK (status IN ('planificada', 'en_curso', 'cerrada')),
    created_by      integer REFERENCES app_user
);

CREATE TABLE hair_result (
    id            serial PRIMARY KEY,
    campaign_id   integer NOT NULL REFERENCES hair_campaign ON DELETE CASCADE,
    case_id       uuid REFERENCES health_case ON DELETE SET NULL,
    age_group     text NOT NULL CHECK (age_group IN ('0-4', '5-14', '15-49', '50+')),
    value_ug_g    double precision NOT NULL CHECK (value_ug_g >= 0),
    lab_id        integer REFERENCES lab
);

-- Al mapa solo llegan agregados por comunidad y con k ≥ 5 (si hay menos, se oculta).
CREATE VIEW health_aggregate AS
SELECT s.id AS settlement_id, s.name, s.h3,
       count(*)                                         AS casos,
       count(*) FILTER (WHERE c.triage = 'urgente')     AS urgentes,
       count(*) FILTER (WHERE c.status <> 'registrado') AS derivados
FROM health_case c JOIN settlement s ON s.id = c.settlement_id
GROUP BY s.id, s.name, s.h3
HAVING count(*) >= 5;

------------------------------------------------------------------------------
-- 7. ALERTAS, INDICADORES, AUDITORÍA
------------------------------------------------------------------------------
CREATE TABLE alert (
    id          serial PRIMARY KEY,
    version_id  integer NOT NULL REFERENCES map_version,
    h3          text NOT NULL REFERENCES h3_cell,
    old_class   text,
    new_class   text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE push_outbox (
    id          bigserial PRIMARY KEY,
    device_id   uuid NOT NULL REFERENCES device ON DELETE CASCADE,
    alert_id    integer REFERENCES alert,
    title       text NOT NULL,
    body        text NOT NULL,
    data        jsonb,
    status      text NOT NULL DEFAULT 'pendiente' CHECK (status IN ('pendiente', 'enviado', 'error')),
    attempts    smallint NOT NULL DEFAULT 0,
    last_error  text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    sent_at     timestamptz
);
CREATE INDEX ON push_outbox (status) WHERE status = 'pendiente';

-- "Personas alcanzadas": fichas servidas, audios escuchados, charlas.
CREATE TABLE outreach_event (
    id            bigserial PRIMARY KEY,
    kind          text NOT NULL CHECK (kind IN ('ficha', 'audio', 'charla', 'alerta')),
    settlement_id integer REFERENCES settlement,
    device_id     uuid REFERENCES device ON DELETE SET NULL,
    people        integer NOT NULL DEFAULT 1,
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON outreach_event (created_at);

CREATE TABLE audit_log (
    id          bigserial PRIMARY KEY,
    user_id     integer REFERENCES app_user,
    action      text NOT NULL,
    entity      text,
    entity_id   text,
    detail      jsonb,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Versión 0: el mapa vacío, para que los teléfonos siempre tengan un "desde".
INSERT INTO map_version (id, triggers, reaches_changed, cells_changed, params_hash)
VALUES (0, '[{"tipo":"inicial"}]', 0, 0, 'none');

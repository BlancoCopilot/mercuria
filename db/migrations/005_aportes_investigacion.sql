-- Aportes de universidades e investigadores (PDF o CSV → IA → revisión → mapa) y datos abiertos.
-- No destructiva: se puede aplicar sobre una base existente.

-- Nuevo rol: investigador (cuenta solicitada por la persona, activada por un admin)
ALTER TABLE app_user DROP CONSTRAINT IF EXISTS app_user_role_check;
ALTER TABLE app_user ADD CONSTRAINT app_user_role_check
    CHECK (role IN ('admin', 'laboratorio', 'promotor', 'lider', 'autoridad', 'investigador'));

CREATE TABLE IF NOT EXISTS study (
    id              serial PRIMARY KEY,
    title           text NOT NULL,
    authors         text,
    year            smallint,
    doi             text,
    url             text,
    institution     text,
    license         text NOT NULL DEFAULT 'CC-BY-4.0'
                    CHECK (license IN ('CC-BY-4.0', 'CC0-1.0', 'CC-BY-SA-4.0')),
    embargo_until   date,                         -- datos ocultos hasta esta fecha (máx. 12 meses)
    source_kind     text NOT NULL CHECK (source_kind IN ('pdf', 'csv')),
    file_path       text,                         -- archivo original (privado salvo pdf_open_access)
    pdf_open_access boolean NOT NULL DEFAULT false,
    status          text NOT NULL DEFAULT 'procesando'
                    CHECK (status IN ('procesando', 'en_revision', 'publicado', 'embargado', 'error', 'retirado')),
    summary         text,                         -- resumen breve (IA o autor)
    warnings        text[] NOT NULL DEFAULT '{}',
    extraction      jsonb,                        -- salida cruda de la IA (trazabilidad)
    extraction_model text,
    error           text,
    submitted_by    integer REFERENCES app_user,
    created_at      timestamptz NOT NULL DEFAULT now(),
    published_at    timestamptz
);

-- Propuestas de datos (de la IA o de un CSV) que alguien revisa antes de publicar.
CREATE TABLE IF NOT EXISTS study_record (
    id             serial PRIMARY KEY,
    study_id       integer NOT NULL REFERENCES study ON DELETE CASCADE,
    fields         jsonb NOT NULL,               -- valores vigentes (editables por el revisor)
    raw            jsonb NOT NULL,               -- propuesta original, nunca se modifica
    status         text NOT NULL DEFAULT 'propuesto' CHECK (status IN ('propuesto', 'aprobado', 'rechazado')),
    problems       text[] NOT NULL DEFAULT '{}', -- advertencias calculadas al normalizar
    modeled        boolean NOT NULL DEFAULT false, -- la matriz entra al modelo (agua, sedimento, pez)
    value_canonical double precision,
    unit_canonical text,
    lat            double precision,
    lon            double precision,
    precision_m    real,
    location_source text,                        -- coordenadas | utm | comunidad | manual
    reach_id       bigint,
    weight         real,
    measurement_id uuid REFERENCES measurement ON DELETE SET NULL,
    updated_by     integer REFERENCES app_user,
    updated_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS study_record_study ON study_record (study_id);

ALTER TABLE measurement ADD COLUMN IF NOT EXISTS study_id integer REFERENCES study ON DELETE SET NULL;
ALTER TABLE measurement ADD COLUMN IF NOT EXISTS basis text;          -- humedo | seco (original)
ALTER TABLE measurement ADD COLUMN IF NOT EXISTS subtype text;        -- agua_total, sedimento_fondo, ...
ALTER TABLE measurement ADD COLUMN IF NOT EXISTS precision_m real;    -- precisión de la ubicación

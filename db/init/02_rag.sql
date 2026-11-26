-- Chatbot RAG (fase 2): documentos, fragmentos con embedding y búsqueda de texto en español.
-- Idempotente: se puede aplicar sobre una base ya creada
--   docker compose exec -T db psql -U rastrohg -d rastrohg < db/init/02_rag.sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Español sin tildes: "pacu" encuentra "pacú", "mercurio" encuentra "Mercurio".
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'es_unaccent') THEN
        CREATE TEXT SEARCH CONFIGURATION es_unaccent (COPY = spanish);
        ALTER TEXT SEARCH CONFIGURATION es_unaccent
            ALTER MAPPING FOR hword, hword_part, word WITH unaccent, spanish_stem;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS rag_document (
    id          serial PRIMARY KEY,
    filename    text NOT NULL UNIQUE,
    title       text NOT NULL,
    kind        text NOT NULL CHECK (kind IN ('pdf', 'faq')),
    tema        text,
    pages       integer,
    sha256      text NOT NULL,
    ingested_at timestamptz NOT NULL DEFAULT now()
);

-- Dimensión 1536 = OpenAI text-embedding-3-small (settings.rag_embed_model).
-- Si se cambia el modelo hay que cambiar la dimensión y volver a ingestar.
CREATE TABLE IF NOT EXISTS chunks (
    id          bigserial PRIMARY KEY,
    document_id integer NOT NULL REFERENCES rag_document ON DELETE CASCADE,
    kind        text NOT NULL CHECK (kind IN ('pdf', 'faq')),
    tema        text,
    page        integer,              -- página física del PDF (1 = primera); NULL en preguntas frecuentes
    ord         integer NOT NULL,     -- orden dentro del documento (para traer fragmentos vecinos)
    content     text NOT NULL,
    meta        jsonb NOT NULL DEFAULT '{}',
    embedding   vector(1536) NOT NULL,
    tsv         tsvector GENERATED ALWAYS AS (to_tsvector('es_unaccent', content)) STORED,
    UNIQUE (document_id, ord)
);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS chunks_tema_idx ON chunks (tema);

-- Registro mínimo de preguntas (sin dispositivo ni IP) para mejorar el contenido.
CREATE TABLE IF NOT EXISTS chat_log (
    id          bigserial PRIMARY KEY,
    question    text NOT NULL,
    answer      text,
    chunk_ids   bigint[],
    model       text,
    stop_reason text,
    latency_ms  integer,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Cuántos fragmentos contienen cada palabra (se recalcula al final de cada ingesta).
-- En este corpus "mercurio" está en casi todo: buscarla por texto no distingue nada.
CREATE TABLE IF NOT EXISTS rag_lexeme (
    word text PRIMARY KEY,
    ndoc integer NOT NULL
);

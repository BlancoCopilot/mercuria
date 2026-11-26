-- Embeddings locales (384) -> OpenAI text-embedding-3-small (1536). Borra los fragmentos: volver a ingestar
--   docker compose exec -T db psql -U rastrohg -d rastrohg < db/migrations/003_rag_openai_embeddings.sql
--   docker compose exec api rastrohg rag-ingest /data/raw/rag --force
BEGIN;
TRUNCATE rag_document, chunks, rag_lexeme;
DROP INDEX IF EXISTS chunks_embedding_idx;
ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(1536);
CREATE INDEX chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
COMMIT;

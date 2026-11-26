"""Búsqueda híbrida: similitud de embeddings (pgvector) + texto en español (tsvector), fusionadas con RRF.

El vector encuentra paráfrasis ("me tiemblan las manos" ~ "temblores"); el texto encuentra nombres
exactos (pacú, surubí, retorta, Minamata) que el modelo pequeño de embeddings a veces confunde.
"""
from __future__ import annotations

from sqlalchemy import Connection

from ..db import rows
from .embed import embed_query

RRF_K = 60
CANDIDATES = 40

# Las palabras que aparecen en más de MAX_DF de los fragmentos no se usan en la búsqueda por texto.
MAX_DF = 0.15
FAQ_CANDIDATES = 3

_SQL = """
WITH q AS (
    SELECT CAST(:e AS vector) AS e,
           -- palabras de la pregunta (raíz, sin tildes ni palabras vacías), sin las demasiado comunes, unidas con OR
           (SELECT string_agg(quote_literal(l.lexeme), ' | ')
            FROM unnest(to_tsvector('es_unaccent', :q)) l
            LEFT JOIN rag_lexeme x ON x.word = l.lexeme
            WHERE coalesce(x.ndoc, 0) <= :maxdf * (SELECT count(*) FROM chunks))::tsquery AS t
),
pool AS (
    SELECT c.* FROM chunks c
    WHERE CAST(:tema AS text) IS NULL OR c.tema = :tema OR c.kind = 'faq'
),
v AS (      -- 1) similitud de significado
    SELECT c.id, row_number() OVER (ORDER BY c.embedding <=> q.e) AS r
    FROM pool c, q ORDER BY c.embedding <=> q.e LIMIT :cand
),
t AS (      -- 2) palabras en común
    SELECT c.id, row_number() OVER (ORDER BY ts_rank_cd(c.tsv, q.t, 32) DESC) AS r
    FROM pool c, q WHERE c.tsv @@ q.t
    ORDER BY ts_rank_cd(c.tsv, q.t, 32) DESC LIMIT :cand
),
fq AS (     -- 3) las preguntas frecuentes verificadas compiten también entre sí
    SELECT c.id, row_number() OVER (ORDER BY c.embedding <=> q.e) AS r
    FROM pool c, q WHERE c.kind = 'faq' ORDER BY c.embedding <=> q.e LIMIT :faqk
),
f AS (
    SELECT id, sum(1.0 / (:rrf + r)) AS score
    FROM (SELECT * FROM v UNION ALL SELECT * FROM t UNION ALL SELECT * FROM fq) u GROUP BY id
)
SELECT c.id, c.document_id, c.kind, c.tema, c.page, c.ord, c.content, c.meta,
       d.filename, d.title, f.score,
       1 - (c.embedding <=> (SELECT e FROM q)) AS similitud
FROM f JOIN chunks c ON c.id = f.id JOIN rag_document d ON d.id = c.document_id
ORDER BY f.score DESC
LIMIT :k
"""

_NEIGHBORS = """
SELECT document_id, ord, content FROM chunks
WHERE (document_id, ord) IN (SELECT * FROM unnest(CAST(:docs AS int[]), CAST(:ords AS int[])))
"""


def search(conn: Connection, question: str, k: int = 6, tema: str | None = None) -> list[dict]:
    hits = rows(conn, _SQL, e=embed_query(question), q=question, tema=tema, cand=CANDIDATES, rrf=RRF_K,
                maxdf=MAX_DF, faqk=FAQ_CANDIDATES, k=k + 4)
    return _dedupe(hits)[:k]


def _dedupe(hits: list[dict]) -> list[dict]:
    """Quita fragmentos consecutivos del mismo documento (los vecinos se agregan después)."""
    out: list[dict] = []
    for h in hits:
        if any(o["document_id"] == h["document_id"] and abs(o["ord"] - h["ord"]) <= 1 for o in out):
            continue
        out.append(h)
    return out


def expand(conn: Connection, hits: list[dict]) -> list[dict]:
    """Agrega el fragmento anterior y el siguiente de cada PDF para dar contexto al modelo."""
    pdf = [h for h in hits if h["kind"] == "pdf"]
    if not pdf:
        return hits
    docs, ords = [], []
    for h in pdf:
        for o in (h["ord"] - 1, h["ord"] + 1):
            docs.append(h["document_id"])
            ords.append(o)
    near = {(r["document_id"], r["ord"]): r["content"] for r in rows(conn, _NEIGHBORS, docs=docs, ords=ords)}
    for h in pdf:
        parts = [near.get((h["document_id"], h["ord"] - 1)), h["content"], near.get((h["document_id"], h["ord"] + 1))]
        h["context"] = " ".join(p for p in parts if p)
    return hits

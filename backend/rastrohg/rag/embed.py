"""Embeddings con la API de OpenAI (text-embedding-3-small, 1536 dimensiones, hasta 8191 tokens por texto).

La dimensión está fija en db/init/02_rag.sql: si se cambia el modelo, cambiarla allí y volver a ingestar.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Iterable

from ..settings import get_settings

BATCH = 128


@lru_cache
def _client():
    import openai

    return openai.OpenAI(api_key=get_settings().openai_api_key or None, timeout=60, max_retries=3)


def to_pgvector(v) -> str:
    return "[" + ",".join(f"{float(x):.7f}" for x in v) + "]"


def _embed(texts: list[str]) -> list[list[float]]:
    r = _client().embeddings.create(model=get_settings().rag_embed_model, input=texts)
    return [d.embedding for d in sorted(r.data, key=lambda d: d.index)]


def embed_passages(texts: Iterable[str]) -> list[str]:
    texts = list(texts)
    out: list[str] = []
    for i in range(0, len(texts), BATCH):
        out += [to_pgvector(v) for v in _embed(texts[i:i + BATCH])]
    return out


@lru_cache(maxsize=1024)          # las preguntas se repiten mucho (las mismas 30-40 dudas)
def embed_query(text: str) -> str:
    return to_pgvector(_embed([text])[0])

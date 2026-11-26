"""Chatbot RAG: preguntas sobre mercurio respondidas con los documentos de Gold4Good.

Anónimo (como los reportes): no se guarda dispositivo ni IP; la IP hasheada solo limita abusos.
"""
from __future__ import annotations

from fastapi import APIRouter, Query, Request

from ...rag.chat import answer, zone_card
from ...rag.search import search
from ...settings import get_settings
from ..deps import DbDep, client_ip_hash, rate_limit
from ..schemas import ChatIn, ChatOut, Tema

router = APIRouter(prefix="/v1/chat", tags=["chatbot"])


@router.post("", response_model=ChatOut)
def chat(body: ChatIn, db: DbDep, request: Request):
    rate_limit(f"chat:{client_ip_hash(request)}", get_settings().chat_per_ip_hour)
    zone = zone_card(db.conn, body.lat, body.lon, body.comunidad_id)   # la ubicación no se guarda
    return answer(db.conn, body.pregunta.strip(), [t.model_dump() for t in body.historial], body.tema, zone=zone)


@router.get("/buscar")
def buscar(db: DbDep, q: str = Query(min_length=2, max_length=500), tema: Tema | None = None,
           k: int = Query(default=6, ge=1, le=20)):
    """Solo la búsqueda (sin OpenAI): para revisar qué fragmentos encuentra el RAG."""
    return [{"archivo": h["filename"], "pagina": h["page"], "tipo": h["kind"], "tema": h["tema"],
             "score": round(float(h["score"]), 4), "similitud": round(float(h["similitud"]), 3),
             "texto": h["content"]} for h in search(db.conn, q, k=k, tema=tema)]

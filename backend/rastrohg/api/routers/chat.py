"""Chatbot RAG: preguntas sobre mercurio respondidas con los documentos de Gold4Good.

Anónimo (como los reportes): no se guarda dispositivo ni IP; la IP hasheada solo limita abusos.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from ...rag.chat import answer, zone_card
from ...rag.search import search
from ...settings import get_settings
from ..deps import DbDep, client_ip_hash, rate_limit
from ..schemas import ChatIn, ChatOut, Tema, VozBuscarIn, VozIn

log = logging.getLogger(__name__)

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


@router.post("/voz")
def voz(body: VozIn, db: DbDep, request: Request):
    """Inicia una conversación por voz (GPT-Live): recibe la oferta SDP del navegador y devuelve la respuesta."""
    s = get_settings()
    if not s.openai_api_key:
        raise HTTPException(503, "La voz no está disponible: falta configurar OPENAI_API_KEY.")
    ip = client_ip_hash(request)
    rate_limit(f"voz:{ip}", s.live_per_ip_hour)
    rate_limit("voz:global", s.live_global_per_hour)
    zone = zone_card(db.conn, body.lat, body.lon, body.comunidad_id)
    import openai

    from ...rag.voice import create_session
    try:
        return create_session(body.sdp, zone, [t.model_dump() for t in body.historial], safety_id=ip)
    except openai.RateLimitError:
        raise HTTPException(429, "Hay muchas conversaciones en este momento. Intenta en un minuto.")
    except (openai.APIStatusError, openai.APIConnectionError) as e:
        log.warning("GPT-Live: %s", getattr(e, "message", e))
        raise HTTPException(502, "No se pudo iniciar la voz. Intenta de nuevo o escribe tu pregunta.")


@router.post("/voz/buscar")
def voz_buscar(body: VozBuscarIn, db: DbDep, request: Request):
    """Herramienta buscar_documentos de la conversación por voz (la llama el navegador)."""
    rate_limit(f"vozb:{client_ip_hash(request)}", 200)
    from ...rag.voice import search_for_voice
    return search_for_voice(db.conn, body.pregunta.strip(), body.tema)

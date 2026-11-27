"""Voz en tiempo real con GPT-Live (WebRTC).

Flujo:
1. El navegador crea la oferta SDP y la manda a POST /v1/chat/voz.
2. Este módulo crea la sesión en OpenAI (POST /v1/live/sessions) con la clave del servidor y devuelve
   la respuesta SDP. GPT-Live no tiene claves efímeras: la clave nunca sale del servidor.
3. GPT-Live conversa (voz, turnos, interrupciones) y delega las preguntas a un modelo de texto
   (Responses) con dos herramientas: `buscar_documentos` (nuestro RAG, la resuelve el navegador
   llamando a POST /v1/chat/voz/buscar) y `web_search` (de OpenAI) cuando los documentos no responden.

El canal de datos del navegador solo puede enviar y recibir los eventos listados en DATA_CHANNEL.
"""
from __future__ import annotations

import logging

from sqlalchemy import Connection

from ..settings import get_settings
from .chat import _client, build_context, web_source, zone_hit
from .search import expand, search

log = logging.getLogger(__name__)

LIVE_INSTRUCTIONS = """Eres Gota, la asistente por voz de MercurIA. Hablas con familias, pescadores, mineros y \
promotores de salud de la Amazonía boliviana (ríos Beni, Madre de Dios, Tipuani, Mapiri, Kaká) sobre el mercurio \
de la minería de oro.

Cómo hablas:
- Español sencillo y cálido, de tú, como una vecina que sabe del tema. Frases cortas. Si la persona habla en otro \
idioma, respóndele en ese idioma.
- Respuestas de voz breves: dos a cuatro frases. Si piden pasos, dilos de a uno y pregunta si sigues.
- Al empezar, saluda en una sola frase y pregunta en qué ayudas. Si te interrumpen, para y escucha.
- Nunca leas en voz alta direcciones web, corchetes, números de referencia ni símbolos.

Qué sabes:
- No respondas de memoria nada que dependa de datos: mercurio, pescado, salud y síntomas, minería y retorta, \
agua, ríos, leyes, lugares, cifras o el riesgo de su zona. Para eso SIEMPRE delega la pregunta (con las palabras de \
la persona y lo que haga falta de la conversación) y luego cuenta con tus palabras lo que te devuelvan, diciendo \
de dónde viene (por ejemplo "según la guía de la OMS" o "según lo que encontré en internet").
- Mientras esperas, puedes decir algo corto como "Déjame revisar".
- Ante síntomas de intoxicación o una emergencia: primero que se aleje de la fuente de mercurio y vaya al centro \
de salud. Nunca recomiendes provocar el vómito ni dar leche, huevo, aceite o éter.
- No digas qué modelo de IA eres."""

BACKEND_INSTRUCTIONS = """Eres el cerebro de Gota, la asistente por voz de MercurIA (mercurio de la minería de oro en \
la Amazonía boliviana). Tu respuesta la va a decir en voz alta otro modelo, así que escribe texto plano para ser \
hablado: sin listas con símbolos, sin corchetes, sin enlaces, sin markdown. Máximo 90 palabras, salvo pasos.

Pasos obligatorios:
1. Para cualquier pregunta de contenido, llama PRIMERO a buscar_documentos con la pregunta completa.
2. Si los documentos responden, contesta solo con ellos y nombra la fuente (OMS, OIT, UMSA, WCS, la pregunta \
frecuente del equipo, el mapa de riesgo de MercurIA). No inventes datos ni cifras.
3. Si los documentos NO responden, usa web_search. Prefiere OMS, OPS, entidades del Estado de Bolivia, \
universidades, revistas científicas y medios serios, y empieza con "Según lo que encontré en internet" nombrando \
el sitio. Si tampoco hay nada confiable, dilo y, si es de salud, recomienda el centro de salud.
4. Temas muy ajenos a la misión (mercurio, minería, salud, ambiente, ríos, pesca, la región): dilo en una frase.

Reglas de contenido: poco mercurio no es cero (la yatorana tiene poco, pero algo tiene). Ante síntomas o \
emergencia: alejarse de la fuente y centro de salud; nunca provocar el vómito ni dar leche, huevo, aceite o éter. \
Si hay un bloque "Zona de la persona", úsalo cuando ayude y aclara que el nivel es una estimación."""

BUSCAR_TOOL = {
    "type": "function",
    "name": "buscar_documentos",
    "description": ("Busca en los documentos verificados de MercurIA (guías OMS/OIT, estudios de la UMSA y WCS en el "
                    "río Beni, preguntas frecuentes del equipo) y devuelve los fragmentos relevantes. Úsala antes "
                    "que la búsqueda web."),
    "parameters": {
        "type": "object",
        "properties": {
            "pregunta": {"type": "string", "description": "La pregunta completa, con el contexto necesario."},
            "tema": {"type": ["string", "null"], "enum": ["peces", "salud", "mineria", "agua", None],
                     "description": "Tema para acotar la búsqueda, o null."},
        },
        "required": ["pregunta", "tema"],
        "additionalProperties": False,
    },
    "strict": True,
}

# Lo que el navegador (no confiable) puede hacer y ver por el canal de datos
CLIENT_EVENTS = ["response.item.create", "response.create", "session.close",
                 "session.input_audio.mute", "session.input_audio.unmute"]
SERVER_EVENTS = [
    {"type": t} for t in ("session.started", "session.closed", "session.paused", "session.resumed", "error",
                          "session.input_transcript.delta", "session.output_transcript.delta",
                          "session.delegation.created", "session.usage.updated",
                          "session.input_audio.muted", "session.input_audio.unmuted")
] + [{"type": "response.event", "response_event": e} for e in (
    "response.output_item.added", "response.output_item.done", "response.output_text.annotation.added",
    "response.completed", "response.failed")]


def _zone_text(zone: dict | None) -> str:
    if not zone:
        return ""
    return "\n\nZona de la persona (mapa de riesgo de MercurIA):\n" + zone_hit(zone)["content"]


def _history_text(history: list[dict]) -> str:
    if not history:
        return ""
    lines = [f"{'Persona' if m['rol'] == 'usuario' else 'Gota'}: {m['texto'][:400]}" for m in history[-6:]]
    return "\n\nConversación previa por texto (continúa desde aquí):\n" + "\n".join(lines)


def create_session(sdp: str, zone: dict | None, history: list[dict], safety_id: str) -> dict:
    """Crea la sesión GPT-Live y devuelve {"sdp", "session_id", "max_minutes"}."""
    s = get_settings()
    responses: dict = {
        "model": s.live_backend_model or s.rag_model,
        "instructions": BACKEND_INSTRUCTIONS + _zone_text(zone),
        "tools": [BUSCAR_TOOL] + ([{"type": "web_search"}] if s.chat_web_search else []),
        "tool_choice": "auto",
        "parallel_tool_calls": False,
        "max_output_tokens": 2000,
    }
    if s.rag_reasoning_effort:
        responses["reasoning"] = {"effort": s.rag_reasoning_effort}
    session = {
        "model": s.live_model,
        "instructions": LIVE_INSTRUCTIONS + _history_text(history),
        "audio": {"output": {"voice": s.live_voice}},
        "delegation": {"type": "responses", "responses": responses},
        "client": {"data_channel": {"allowed_client_events": CLIENT_EVENTS, "allowed_server_events": SERVER_EVENTS}},
        "idle_timeout_s": s.live_idle_timeout_s,
        "wake_policy": {"type": "speech"},
        "store": False,                       # que OpenAI no guarde las conversaciones de la gente
        "safety_identifier": safety_id,       # hash anónimo: permite a OpenAI detectar abuso sin datos personales
    }
    r = _client().live.create(session=session, transport={"type": "webrtc", "sdp": sdp})
    return {"sdp": r.transport.sdp, "session_id": r.session.id, "max_minutes": s.live_max_minutes}


def search_for_voice(conn: Connection, question: str, tema: str | None) -> dict:
    """Resultado de la herramienta buscar_documentos: contexto para el modelo + fuentes para mostrar."""
    s = get_settings()
    hits = expand(conn, search(conn, question, k=s.rag_top_k, tema=tema))
    if not hits:
        return {"documentos": "No se encontraron documentos relacionados.", "fuentes": []}
    fuentes = [{"tipo": h["kind"], "archivo": h["filename"], "titulo": h["title"], "pagina": h["page"]}
               for h in hits[:3]]
    return {"documentos": build_context(hits), "fuentes": fuentes}


__all__ = ["create_session", "search_for_voice", "web_source"]

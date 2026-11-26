"""Respuesta del chatbot: búsqueda -> contexto numerado -> OpenAI -> respuesta con citas [n]."""
from __future__ import annotations

import logging
import re
import time
from functools import lru_cache

from sqlalchemy import Connection

from ..db import execute, one
from ..settings import get_settings
from .search import expand, search

log = logging.getLogger(__name__)

SYSTEM = """Eres el asistente de RastroHg / Gold4Good. Respondes preguntas de familias, pescadores, \
mineros y promotores de salud de la Amazonía boliviana (ríos Beni, Madre de Dios, Tipuani, Mapiri, Kaká) \
sobre el mercurio de la minería de oro: qué pescado comer, salud y síntomas, la retorta y el trabajo \
minero, el agua y los ríos.

Reglas:
1. Responde SOLO con lo que dicen los fragmentos numerados que vienen con la pregunta. Si los fragmentos \
no responden la pregunta, dilo con claridad ("No tengo esa información en mis documentos") y, si es un tema \
de salud, recomienda ir al centro de salud. No inventes datos, cifras, nombres ni recomendaciones.
2. Cita cada dato con el número del fragmento entre corchetes, por ejemplo [2]. Solo números que existan. \
Si no tienes la información, no pongas citas y no ofrezcas ayuda con otros temas.
3. Lenguaje sencillo, frases cortas, como hablando con alguien de la comunidad. Habla de tú. Si la persona \
pregunta por sí misma, adapta los consejos a ella ("sal al aire libre", no "sácalo al aire libre"). Máximo 120 palabras, salvo \
que pidan pasos (por ejemplo, cómo usar la retorta): entonces una lista numerada corta. Texto plano: sin negritas, \
asteriscos, tablas ni títulos (la app no muestra formato).
4. Ante síntomas de intoxicación o una emergencia: primero que la persona se aleje de la fuente de mercurio y \
vaya al centro de salud. Usa solo los primeros auxilios de la ficha OIT/OMS. Nunca recomiendes provocar el \
vómito ni dar leche, huevo, aceite o éter.
5. Si los fragmentos no coinciden, da prioridad a las preguntas frecuentes verificadas y a los estudios hechos \
en Bolivia (por ejemplo, el estudio UMSA-WCS del río Beni para los peces) y menciona la diferencia si importa.
6. Si viene un bloque "Mapa de riesgo RastroHg", es la zona de la persona: menciona su nivel de riesgo y el \
centro de salud más cercano cuando ayude a la pregunta, y aclara que es una estimación. Para elegir pescado, \
combina el consejo local del mapa con los documentos; si no coinciden, di las dos cosas.
7. Poco mercurio no es cero. Cuando recomiendes peces con poco mercurio, aclara que igual tienen un poco. \
En particular la yatorana: tiene poca probabilidad de tener mucho mercurio, pero aún tiene un poco.
8. Responde en el idioma de la pregunta. No digas qué modelo de IA eres ni hables de "fragmentos": habla de \
"los documentos" o nombra la fuente (OMS, UMSA, etc.)."""

NO_KEY_MSG = ("El asistente todavía no tiene configurada la clave de OpenAI (OPENAI_API_KEY). "
              "Estos son los textos más relacionados que encontré:")


@lru_cache
def _client():
    import openai

    return openai.OpenAI(api_key=get_settings().openai_api_key, timeout=60, max_retries=2)


MAX_KM_COMUNIDAD = 25     # más lejos que esto, la ubicación no se asocia a ninguna comunidad


def zone_card(conn: Connection, lat: float | None = None, lon: float | None = None,
              settlement_id: int | None = None) -> dict | None:
    """Ficha "Mi comunidad" (riesgo, peces, centro de salud) de la comunidad elegida o la más cercana."""
    from ..services.card import community_card

    if settlement_id is None:
        if lat is None or lon is None:
            return None
        near = one(conn, """
            SELECT id, ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) / 1000 AS km
            FROM settlement ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) LIMIT 1""", lat=lat, lon=lon)
        if not near or near["km"] > MAX_KM_COMUNIDAD:
            return None
        settlement_id = near["id"]
    return community_card(conn, settlement_id)


def zone_hit(card: dict) -> dict:
    """La ficha como un 'fragmento' más, para que el modelo la cite con [n]."""
    com = card["comunidad"]
    grupos = {c: [p["nombre"] for p in card["peces"] if p["consejo"] == c] for c in ("comer", "limitar", "evitar")}
    lines = [f"Comunidad: {com['nombre']}" + (" (DATOS SINTÉTICOS DE DEMOSTRACIÓN)" if com["sintetico"] else ""),
             f"Nivel de riesgo por mercurio estimado: {card['nivel'].upper().replace('_', ' ')}"]
    if card["palida"]:
        lines.append("Hay pocos datos de esta zona: el nivel puede cambiar cuando lleguen muestras.")
    if grupos["comer"]:
        lines.append("Peces que se pueden comer en esta zona: " + ", ".join(grupos["comer"]))
    if grupos["limitar"]:
        lines.append("Peces para comer poco (1 o 2 veces por semana): " + ", ".join(grupos["limitar"]))
    if grupos["evitar"]:
        lines.append("Peces que embarazadas y niños deben evitar: " + ", ".join(grupos["evitar"]))
    for p in card["peces"]:
        if p.get("nota"):
            lines.append(f"{p['nombre']}: {p['nota']}")
    if c := card["centro_salud"]:
        lines.append(f"Centro de salud más cercano: {c['name']}, a {c['km']:.0f} km" + (f", teléfono {c['phone']}" if c.get("phone") else ""))
    lines.append(card["aviso"])
    return {"id": None, "kind": "mapa", "filename": "mapa_rastrohg", "page": None, "tema": None, "meta": {},
            "title": f"Mapa de riesgo RastroHg — {com['nombre']}", "content": "\n".join(lines), "score": 0.0}


def _label(h: dict) -> str:
    if h["kind"] == "mapa":
        return h["title"]
    if h["kind"] == "faq":
        src = (h["meta"] or {}).get("fuente")
        return "Pregunta frecuente verificada por el equipo" + (f" (fuente: {src})" if src else "")
    return f"{h['title']} — {h['filename']}, página {h['page']}"


def build_context(hits: list[dict]) -> str:
    return "\n\n".join(f"[{i}] {_label(h)}\n{h.get('context') or h['content']}" for i, h in enumerate(hits, start=1))


def _source(i: int, h: dict) -> dict:
    return {"n": i, "tipo": h["kind"], "archivo": h["filename"], "titulo": h["title"], "pagina": h["page"],
            "tema": h["tema"], "fragmento": h["content"][:300], "score": round(float(h["score"]), 4)}


def answer(conn: Connection, question: str, history: list[dict] | None = None, tema: str | None = None,
           k: int | None = None, zone: dict | None = None) -> dict:
    """zone = ficha de zone_card() (opcional): se agrega como la última fuente."""
    s = get_settings()
    t0 = time.monotonic()
    history = (history or [])[-6:]
    # En una repregunta corta ("¿y el surubí?") se busca también con la pregunta anterior.
    prev_user = next((m["texto"] for m in reversed(history) if m["rol"] == "usuario"), "")
    query = f"{prev_user} {question}" if prev_user and len(question) < 60 else question
    hits = expand(conn, search(conn, query, k=k or s.rag_top_k, tema=tema))
    if zone:
        hits.append(zone_hit(zone))

    if not s.openai_api_key:
        faq = next((h for h in hits[:2] if h["kind"] == "faq"), None)
        text_ = faq["content"].split("Respuesta: ", 1)[1].split("\nPalabras clave:")[0] if faq else NO_KEY_MSG
        return {"respuesta": text_, "fuentes": [_source(i, h) for i, h in enumerate(hits, 1)],
                "modelo": None, "sin_modelo": True, "zona": _zone_summary(zone)}

    messages: list[dict] = []
    for m in history:
        role = "user" if m["rol"] == "usuario" else "assistant"
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] += "\n" + m["texto"]
        else:
            messages.append({"role": role, "content": m["texto"]})
    if messages and messages[0]["role"] != "user":
        messages.pop(0)
    user_msg = (f"<documentos>\n{build_context(hits)}\n</documentos>\n\n"
                f"Pregunta: {question}") if hits else f"(No se encontraron documentos relacionados.)\n\nPregunta: {question}"
    if messages and messages[-1]["role"] == "user":
        messages[-1]["content"] += "\n\n" + user_msg
    else:
        messages.append({"role": "user", "content": user_msg})

    import openai

    params: dict = {"model": s.rag_model, "instructions": SYSTEM, "input": messages,
                    "max_output_tokens": 4000,
                    "store": False}            # que OpenAI no guarde las conversaciones de la gente
    if s.rag_reasoning_effort:                 # solo modelos de razonamiento (gpt-5, o-series); "" para gpt-4.1, etc.
        params["reasoning"] = {"effort": s.rag_reasoning_effort}
    try:
        resp = _client().responses.create(**params)
    except openai.RateLimitError:
        log.warning("OpenAI: límite de uso o saldo agotado")
        return {"respuesta": "Hay muchas consultas en este momento. Intente de nuevo en un minuto.",
                "fuentes": [], "modelo": s.rag_model, "error": "rate_limit"}
    except (openai.APIStatusError, openai.APIConnectionError) as e:
        log.exception("OpenAI: error de API")
        return {"respuesta": "El asistente no está disponible ahora. Intente más tarde.",
                "fuentes": [], "modelo": s.rag_model, "error": type(e).__name__}

    refused = any(getattr(part, "type", None) == "refusal"
                  for item in resp.output if getattr(item, "type", None) == "message"
                  for part in item.content)
    reply = (resp.output_text or "").strip()
    status = "refusal" if refused and not reply else resp.status
    if not reply:
        reply = ("No puedo responder esa pregunta ahora. "
                 "Si es un tema de salud, acuda al centro de salud más cercano.")

    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", reply) if 1 <= int(n) <= len(hits)})
    sources = [_source(i, hits[i - 1]) for i in cited]
    ms = int((time.monotonic() - t0) * 1000)
    execute(conn, """INSERT INTO chat_log (question, answer, chunk_ids, model, stop_reason, latency_ms)
                     VALUES (:q, :a, :c, :m, :s, :l)""",
            q=question, a=reply, c=[h["id"] for h in hits if h["id"] is not None], m=resp.model, s=status, l=ms)
    return {"respuesta": reply, "fuentes": sources, "modelo": resp.model, "latencia_ms": ms,
            "zona": _zone_summary(zone)}


def _zone_summary(card: dict | None) -> dict | None:
    if not card:
        return None
    return {"comunidad_id": card["comunidad"]["id"], "comunidad": card["comunidad"]["nombre"],
            "nivel": card["nivel"], "palida": card["palida"], "centro_salud": card["centro_salud"],
            "sintetico": card["comunidad"]["sintetico"]}

"""IA: de un PDF de investigación a una lista de mediciones propuestas (para revisión humana).

Principios:
* La IA PROPONE; una persona confirma. Nada entra al mapa sin revisión.
* Prohibido inventar: cada valor trae la cita textual y la página de donde sale. Lo que el
  documento no dice queda en null (sin ubicación, sin fecha…) y se marca como problema.
* Se envía el PDF (no solo el texto) para que el modelo lea tablas; de documentos largos solo
  van las páginas con datos de mercurio (más la portada), para acotar costo y ruido.
* store=False: OpenAI no guarda los documentos.
"""
from __future__ import annotations

import base64
import json
import logging
import re

from ..settings import get_settings

log = logging.getLogger(__name__)

MAX_PAGES = 14
KEYWORDS = re.compile(r"(mercur|\bhg\b|thg|mehg|metilmercur|µg|μg|ug/|ng/|mg/kg|ppm|ppb)", re.I)
NUMBERS = re.compile(r"\d+[.,]\d+")

_NUM = {"type": ["number", "null"]}
_STR = {"type": ["string", "null"]}

RECORD_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "matriz": {"type": "string", "enum": ["agua", "sedimento", "pez", "cabello", "sangre", "orina", "suelo", "otro"]},
        "subtipo": {"type": ["string", "null"], "enum": [
            "agua_total", "agua_disuelta", "agua_particulada", "sedimento_fondo", "sedimento_suspension",
            "sedimento_laguna", "musculo", None]},
        "analito": {"type": "string", "enum": ["hg_total", "metilmercurio"]},
        "valor": {"type": "number"},
        "unidad": {"type": "string"},
        "base": {"type": "string", "enum": ["humedo", "seco", "no_aplica", "desconocido"]},
        "bajo_ld": {"type": "boolean"},
        "limite_deteccion": _NUM,
        "estadistico": {"type": "string", "enum": ["individual", "media", "mediana", "media_geometrica", "maximo", "minimo"]},
        "n": {"type": ["integer", "null"]},
        "desviacion": _NUM, "minimo": _NUM, "maximo": _NUM,
        "lat": _NUM, "lon": _NUM,
        "utm_este": _NUM, "utm_norte": _NUM, "utm_zona": _STR,
        "lugar": _STR, "rio": _STR,
        "fecha": _STR,
        "estacion": {"type": "string", "enum": ["seca", "humeda", "desconocida"]},
        "metodo": _STR, "laboratorio": _STR,
        "especie_cientifica": _STR, "especie_comun": _STR,
        "origen_pez": {"type": "string", "enum": ["captura", "mercado", "desconocido", "no_aplica"]},
        "pagina": {"type": ["integer", "null"]},
        "tabla": _STR,
        "cita_textual": {"type": "string"},
        "confianza": {"type": "number"},
    },
}
RECORD_SCHEMA["required"] = list(RECORD_SCHEMA["properties"])

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "titulo": _STR, "autores": _STR, "anio": {"type": ["integer", "null"]}, "doi": _STR, "institucion": _STR,
        "resumen": {"type": "string"},
        "zona_estudio": _STR,
        "advertencias": {"type": "array", "items": {"type": "string"}},
        "mediciones": {"type": "array", "items": RECORD_SCHEMA},
    },
}
SCHEMA["required"] = list(SCHEMA["properties"])

INSTRUCTIONS = """Eres un asistente de extracción de datos científicos para MercurIA, una plataforma pública sobre mercurio de la minería aurífera en Bolivia.

Tarea: leer el documento y devolver TODAS las mediciones de mercurio que reporta (agua, sedimento, peces, cabello, sangre, orina, suelo), una por fila.

Reglas estrictas:
1. No inventes nada. Si el documento no da un dato (coordenadas, fecha, base húmedo/seco, especie…), devuelve null o "desconocido". Nunca estimes coordenadas a partir de tu conocimiento geográfico.
2. Copia en "cita_textual" el fragmento exacto (máx. 200 caracteres) del documento que respalda el valor: la fila de la tabla o la frase.
3. "pagina" es el número de página del ORIGINAL indicado en el encabezado de cada página que recibes.
4. Coordenadas: lat/lon en grados decimales WGS84 SOLO si el documento las da (convierte grados-minutos-segundos a decimal; sur y oeste son negativos). Si da UTM, usa utm_este/utm_norte/utm_zona (p. ej. "19S") y deja lat/lon en null.
5. "lugar" = nombre del sitio de muestreo tal como aparece (comunidad, estación, mercado). "rio" = río muestreado si se menciona.
6. Valores bajo el límite de detección ("< 0,001", "ND", "<LD"): bajo_ld=true y valor = el límite.
7. Si una tabla da media, mediana o rango de un grupo, usa estadistico (media, mediana…), n, desviacion, minimo y maximo. No inventes individuos.
8. Peces: especie_cientifica y especie_comun si aparecen; origen_pez = "mercado" si se compraron en un mercado, "captura" si se pescaron en un sitio conocido.
9. Base: "seco" (peso seco, dw, d.m.), "humedo" (peso fresco, ww, w.m.); para agua usa "no_aplica".
10. Fechas como "AAAA-MM-DD", "AAAA-MM" o "AAAA". Estación: seca (abr–oct) o húmeda (nov–mar) solo si el documento lo dice o da el mes.
11. "confianza" 0–1: qué tan seguro estás de haber leído bien esa fila.
12. No repitas el mismo valor citado en dos lugares (p. ej. resumen y tabla): quédate con la tabla.
13. En "advertencias" anota problemas para quien revise (datos solo en gráficos, unidades ambiguas, sitios sin coordenadas, peces de mercado sin origen…).
Si el documento no contiene mediciones de mercurio, devuelve "mediciones": [] y explícalo en advertencias."""


def _parse(resp) -> dict:
    """El texto de salida puede traer más de un mensaje: se usa el primer objeto JSON completo y válido."""
    textos = [part.text for item in resp.output if getattr(item, "type", None) == "message"
              for part in item.content if getattr(part, "type", None) == "output_text"]
    dec = json.JSONDecoder()
    for t in textos + [resp.output_text or ""]:
        t = t.strip()
        i = t.find("{")
        while i != -1:
            try:
                obj, _ = dec.raw_decode(t[i:])
                if isinstance(obj, dict) and "mediciones" in obj:
                    return obj
            except json.JSONDecodeError:
                pass
            i = t.find("{", i + 1)
    raise RuntimeError("La IA no devolvió datos legibles. Vuelve a intentar la extracción.")


def select_pages(pdf_bytes: bytes) -> tuple[bytes, list[int], int]:
    """Devuelve (pdf reducido, páginas originales incluidas 1-based, total de páginas)."""
    import pymupdf

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        total = doc.page_count
        if total <= MAX_PAGES:
            return pdf_bytes, list(range(1, total + 1)), total
        scores = []
        for i, page in enumerate(doc):
            t = page.get_text()
            scores.append((len(KEYWORDS.findall(t)) * 3 + min(len(NUMBERS.findall(t)), 60), i))
        keep = {0, 1}
        for sc, i in sorted(scores, reverse=True):
            if len(keep) >= MAX_PAGES:
                break
            if sc > 6:
                keep.add(i)
        pages = sorted(keep)
        out = pymupdf.open()
        for i in pages:
            out.insert_pdf(doc, from_page=i, to_page=i)
        data = out.tobytes(garbage=3, deflate=True)
        out.close()
        return data, [p + 1 for p in pages], total


def extract_pdf(pdf_bytes: bytes, filename: str) -> dict:
    """Llama al modelo con el PDF y el esquema estricto. Devuelve el JSON + metadatos de la llamada."""
    import openai

    s = get_settings()
    if not s.openai_api_key:
        raise RuntimeError("Falta OPENAI_API_KEY: sin modelo no se puede extraer el PDF (use la vía CSV).")
    data, pages, total = select_pages(pdf_bytes)
    mapa = ", ".join(f"pág. {k + 1} del archivo = pág. {p} del original" for k, p in enumerate(pages))
    nota = (f"El documento original tiene {total} páginas; recibes solo {len(pages)} con datos ({mapa})."
            if len(pages) < total else f"Documento completo ({total} páginas).")
    client = openai.OpenAI(api_key=s.openai_api_key, timeout=240, max_retries=2)
    params: dict = {
        "model": s.research_model or s.rag_model,
        "instructions": INSTRUCTIONS,
        "input": [{"role": "user", "content": [
            {"type": "input_file", "filename": filename,
             "file_data": "data:application/pdf;base64," + base64.b64encode(data).decode()},
            {"type": "input_text", "text": nota + "\nExtrae las mediciones de mercurio siguiendo las reglas."},
        ]}],
        "text": {"format": {"type": "json_schema", "name": "mediciones_mercurio", "schema": SCHEMA, "strict": True}},
        "max_output_tokens": 32000,
        "store": False,
    }
    if s.research_reasoning_effort:
        params["reasoning"] = {"effort": s.research_reasoning_effort}
    resp = client.responses.create(**params)
    if resp.status != "completed":
        raise RuntimeError(f"La IA no terminó ({resp.status}: {resp.incomplete_details}). Prueba con un PDF más corto.")
    out = _parse(resp)
    out["_meta"] = {"modelo": resp.model, "paginas_enviadas": pages, "paginas_totales": total,
                    "tokens": getattr(resp.usage, "total_tokens", None)}
    return out

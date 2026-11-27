"""Figuras de los PDFs -> texto que se puede vectorizar.

Los gráficos, tablas en imagen, mapas y fotos con datos no tienen texto que pymupdf pueda leer.
Cada figura útil se recorta de la página, un modelo de visión de OpenAI la describe en español
(con las cifras que se ven) y esa descripción se guarda como un fragmento más del PDF, con su página.
Así el chatbot puede citar "página 12, figura" igual que un párrafo.

Se omiten:
* imágenes chicas (logos, íconos, viñetas);
* la imagen que cubre toda la página en los libros escaneados que ya tienen OCR (su texto ya está);
* imágenes repetidas en muchas páginas (logos de encabezado);
* lo que el modelo marca como decorativo (SIN_INFORMACION).

Las descripciones se guardan en un caché JSON por hash de la imagen: volver a ingestar no vuelve a pagar.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..settings import get_settings

log = logging.getLogger(__name__)

MIN_SIDE_PT = 120          # ~4 cm: menos que eso es un ícono o un logo
MIN_AREA_FRAC = 0.04       # al menos el 4 % de la página
SCANNED_AREA_FRAC = 0.85   # una imagen así de grande en una página con texto = página escaneada con OCR
SCANNED_MIN_TEXT = 200
REPEAT_PAGES = 3           # la misma imagen en 3 páginas o más = logo de encabezado
RENDER_DPI = 150
EMPTY = "SIN_INFORMACION"

PROMPT = """Eres parte de un asistente sobre el mercurio de la minería del oro en Bolivia.
Esta imagen es una figura de la página {page} del documento «{title}».
Texto cercano en la página (puede ayudar a entender la figura): «{near}»

Describe en español sencillo, en un solo párrafo de 120 palabras como máximo, lo que la figura
muestra y que le sirva a una persona: qué mide, dónde, cuándo, y las cifras, nombres de peces,
lugares o pasos que se ven. Copia los números tal como aparecen, con sus unidades. No inventes
nada que no se vea. Si es un logo, una foto decorativa o no tiene información útil, responde
solo: SIN_INFORMACION"""


@dataclass
class Figure:
    page: int
    png: bytes
    sha: str
    near_text: str


def _client():
    return _openai_client()


@lru_cache
def _openai_client():
    import openai

    return openai.OpenAI(api_key=get_settings().openai_api_key or None, timeout=90, max_retries=3)


def extract_figures(path: Path, max_figures: int | None = None) -> list[Figure]:
    """Recorta las figuras útiles de un PDF, en orden de página."""
    import pymupdf

    max_figures = max_figures or get_settings().rag_images_max_per_doc
    out: list[Figure] = []
    with pymupdf.open(path) as doc:
        # Cuántas páginas usan cada imagen (por su xref): las repetidas son logos.
        uses: Counter = Counter()
        for page in doc:
            for xref in {img[0] for img in page.get_images(full=True)}:
                uses[xref] += 1
        seen: set[str] = set()
        for i, page in enumerate(doc, start=1):
            page_area = page.rect.width * page.rect.height
            page_text = page.get_text().strip()
            for img in page.get_images(full=True):
                xref = img[0]
                if uses[xref] >= REPEAT_PAGES:
                    continue
                for rect in page.get_image_rects(xref):
                    rect = rect & page.rect
                    if rect.is_empty or min(rect.width, rect.height) < MIN_SIDE_PT:
                        continue
                    frac = (rect.width * rect.height) / page_area
                    if frac < MIN_AREA_FRAC:
                        continue
                    if frac > SCANNED_AREA_FRAC and len(page_text) >= SCANNED_MIN_TEXT:
                        continue
                    png = page.get_pixmap(clip=rect, dpi=RENDER_DPI).tobytes("png")
                    sha = hashlib.sha256(png).hexdigest()
                    if sha in seen:
                        continue
                    seen.add(sha)
                    out.append(Figure(i, png, sha, " ".join(page_text.split())[:600]))
                    if len(out) >= max_figures:
                        log.info("%s: se alcanzó el máximo de %d figuras", path.name, max_figures)
                        return out
    return out


def describe(fig: Figure, title: str) -> str:
    s = get_settings()
    url = "data:image/png;base64," + base64.b64encode(fig.png).decode()
    params: dict = {
        "model": s.rag_vision_model or s.rag_model,
        "input": [{"role": "user", "content": [
            {"type": "input_text", "text": PROMPT.format(page=fig.page, title=title, near=fig.near_text)},
            {"type": "input_image", "image_url": url, "detail": "high"},
        ]}],
        "max_output_tokens": 1500,
        "store": False,
    }
    if s.rag_reasoning_effort:
        params["reasoning"] = {"effort": s.rag_reasoning_effort}
    resp = _client().responses.create(**params)
    return " ".join((resp.output_text or "").split())


def load_cache(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_cache(path: Path, cache: dict) -> None:
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def figure_texts(path: Path, title: str, cache: dict) -> list[tuple[int, str, str]]:
    """[(página, descripción, sha)] de las figuras con información. Usa y llena `cache` (sha -> texto)."""
    out = []
    for fig in extract_figures(path):
        key = fig.sha
        if key not in cache:
            try:
                cache[key] = {"archivo": path.name, "pagina": fig.page, "descripcion": describe(fig, title)}
            except Exception:                    # una figura que falla no detiene la ingesta del PDF
                log.exception("%s p. %d: no se pudo describir la figura", path.name, fig.page)
                continue
        desc = cache[key]["descripcion"]
        if not desc or EMPTY in desc.upper():
            continue
        out.append((fig.page, desc, key))
    return out

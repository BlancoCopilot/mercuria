"""Cosas que usan ingestar.py y api.py."""
import csv
import json
from pathlib import Path

BASE = Path(__file__).parent
DOCS = BASE / "docs"
INDICE_VEC = BASE / "indice_vectores.npy"
INDICE_META = BASE / "indice_textos.json"
MODELO_EMB = "text-embedding-3-small"
MODELO_CHAT = "gpt-4o-mini"


def _col(fila: dict, *opciones):
    """Busca una columna aunque se llame distinto (Pregunta, pregunta, PREGUNTA, pregunta_es...)."""
    for clave, valor in fila.items():
        if clave and any(o in clave.strip().lower() for o in opciones):
            return (valor or "").strip()
    return ""


def cargar_faq():
    """Lee preguntas_frecuentes.csv (de Leonie). Si no existe, usa faq.json."""
    csv_path = BASE / "preguntas_frecuentes.csv"
    if csv_path.exists():
        texto = csv_path.read_text(encoding="utf-8-sig")
        primera = texto.splitlines()[0] if texto else ""
        sep = ";" if primera.count(";") > primera.count(",") else ","
        faqs = []
        for i, fila in enumerate(csv.DictReader(texto.splitlines(), delimiter=sep), 1):
            p, r = _col(fila, "pregunta"), _col(fila, "respuesta")
            if p and r:
                faqs.append({
                    "id": _col(fila, "id") or f"p{i:02d}",
                    "pregunta": p,
                    "respuesta": r,
                    "fuente": _col(fila, "fuente") or "Preguntas frecuentes del equipo",
                    "tema": _col(fila, "tema") or "general",
                    "audios": {},
                })
        return faqs
    json_path = BASE / "faq.json"
    if json_path.exists():
        return json.loads(json_path.read_text(encoding="utf-8"))["preguntas"]
    return []

"""Pruebas del RAG sin base ni red: limpieza, corte, preguntas frecuentes y armado de la respuesta."""
from __future__ import annotations

from types import SimpleNamespace

from rastrohg.rag import chat
from rastrohg.rag.ingest import CHUNK_CHARS, clean, faq_chunks, read_titles, split_text


def test_clean_ocr_artifacts():
    assert clean("ﬁcha de seguri-\ndad") == "ficha de seguridad"
    assert clean("activa­ ción del  mercurio\n en el río") == "activación del mercurio en el río"


def test_split_text_sizes_and_overlap():
    t = " ".join(f"Oración número {i} sobre el mercurio en los peces del río Beni." for i in range(60))
    parts = split_text(t)
    assert len(parts) > 3
    assert all(len(p) <= CHUNK_CHARS + 80 for p in parts)
    assert parts[0].split(". ")[-1] in parts[1]          # hay solapamiento entre piezas consecutivas
    assert split_text("corto") == ["corto"]
    assert split_text("x" * 2000)                        # sin espacios: corte duro, no bucle infinito


def test_faq_and_titles(tmp_path):
    csv = tmp_path / "preguntas_frecuentes.csv"
    csv.write_text("﻿pregunta;respuesta;fuente;tema;palabras_clave;verificado;nota_revision\n"
                   "¿Cocinar quita el mercurio?;No.;oms.pdf p. 1;peces;cocinar, hervir;sí;\n"
                   ";sin pregunta;;;;;\n", encoding="utf-8")
    [(tema, c)] = faq_chunks(csv)
    assert tema == "peces" and c.page is None
    assert "Pregunta frecuente: ¿Cocinar quita el mercurio?" in c.content and "cocinar, hervir" in c.content
    assert c.meta["verificado"] == "sí" and c.meta["fuente"] == "oms.pdf p. 1"

    md = tmp_path / "DOCUMENTOS.md"
    md.write_text("| Archivo | Documento |\n|---|---|\n| oms.pdf | OMS: *El mercurio y la salud* | salud | 1 |\n")
    assert read_titles(md) == {"oms.pdf": "OMS: El mercurio y la salud"}


HITS = [
    {"id": 1, "kind": "faq", "filename": "preguntas_frecuentes.csv", "title": "Preguntas frecuentes", "page": None,
     "tema": "peces", "content": "Pregunta frecuente: ¿Cocinar quita el mercurio?\nRespuesta: No.", "score": 0.05,
     "meta": {"fuente": "oms.pdf p. 1"}},
    {"id": 2, "kind": "pdf", "filename": "oms.pdf", "title": "OMS", "page": 1, "tema": "salud",
     "content": "Cocinar no elimina el mercurio.", "context": "Antes. Cocinar no elimina el mercurio. Después.",
     "score": 0.03, "meta": {}},
]


class FakeClient:
    """Imita openai.OpenAI().responses.create (Responses API)."""

    def __init__(self, text, refusal=False):
        self.calls = []
        self.responses = SimpleNamespace(create=self._create)
        self.text, self.refusal = text, refusal

    def _create(self, **kw):
        self.calls.append(kw)
        part = SimpleNamespace(type="refusal", refusal="No.") if self.refusal else \
            SimpleNamespace(type="output_text", text=self.text)
        return SimpleNamespace(output=[SimpleNamespace(type="reasoning"),
                                       SimpleNamespace(type="message", content=[part])],
                               output_text="" if self.refusal else self.text,
                               status="completed", model=kw["model"])


def _patch(monkeypatch, client, key="sk-test", effort="low"):
    monkeypatch.setattr(chat, "search", lambda conn, q, k=6, tema=None: [dict(h) for h in HITS])
    monkeypatch.setattr(chat, "expand", lambda conn, hits: hits)
    monkeypatch.setattr(chat, "execute", lambda *a, **k: None)
    monkeypatch.setattr(chat, "_client", lambda: client)
    monkeypatch.setattr(chat, "get_settings", lambda: SimpleNamespace(
        openai_api_key=key, rag_model="gpt-5.4-mini", rag_reasoning_effort=effort, rag_top_k=6))


def test_answer_cites_only_used_sources(monkeypatch):
    fake = FakeClient("No, cocinar no quita el mercurio [2].")
    _patch(monkeypatch, fake)
    r = chat.answer(None, "¿El pescado ahumado tiene menos mercurio?",
                    history=[{"rol": "usuario", "texto": "hola"}, {"rol": "asistente", "texto": "¿En qué ayudo?"}])
    assert r["respuesta"].startswith("No, cocinar")
    assert [f["archivo"] for f in r["fuentes"]] == ["oms.pdf"]
    kw = fake.calls[0]
    assert kw["model"] == "gpt-5.4-mini" and kw["store"] is False and kw["reasoning"] == {"effort": "low"}
    assert "Responde SOLO" in kw["instructions"]
    assert [m["role"] for m in kw["input"]] == ["user", "assistant", "user"]
    last = kw["input"][-1]["content"]
    assert "[1] Pregunta frecuente verificada" in last and "[2] OMS — oms.pdf, página 1" in last
    assert "Antes. Cocinar no elimina el mercurio. Después." in last   # usa el contexto ampliado


def test_answer_refusal_and_no_key(monkeypatch):
    _patch(monkeypatch, FakeClient("", refusal=True))
    assert "centro de salud" in chat.answer(None, "x?")["respuesta"]

    fake = FakeClient("ok")
    _patch(monkeypatch, fake, effort="")                 # modelo sin razonamiento: no se manda `reasoning`
    chat.answer(None, "x?")
    assert "reasoning" not in fake.calls[0]

    _patch(monkeypatch, None, key="")
    r = chat.answer(None, "¿Cocinar quita el mercurio?")
    assert r["sin_modelo"] and r["respuesta"] == "No." and len(r["fuentes"]) == 2


CARD = {"comunidad": {"id": 11, "nombre": "Guanay", "h3": "x", "poblacion": 5000, "sintetico": False},
        "nivel": "medio", "palida": True, "confianza": 0.4, "version_mapa": 3, "frases": [],
        "peces": [{"nombre": "Pacú", "consejo": "comer"}, {"nombre": "Surubí", "consejo": "limitar"},
                  {"nombre": "Blanquillo", "consejo": "evitar"}],
        "centro_salud": {"id": 1, "name": "Hospital Guanay", "phone": None, "level": 2, "km": 1.2},
        "aviso": "Estimación con incertidumbre."}


def test_zone_is_cited_like_a_source(monkeypatch):
    fake = FakeClient("En Guanay el riesgo estimado es medio [3]. Come pacú [1].")
    _patch(monkeypatch, fake)
    r = chat.answer(None, "¿Qué pescado compro?", zone=CARD)
    last = fake.calls[0]["input"][-1]["content"]
    assert "[3] Mapa de riesgo RastroHg — Guanay" in last
    assert "MEDIO" in last and "pocos datos" in last and "Surubí" in last and "Hospital Guanay, a 1 km" in last
    assert [f["tipo"] for f in r["fuentes"]] == ["faq", "mapa"]
    assert r["zona"]["comunidad"] == "Guanay" and r["zona"]["nivel"] == "medio"

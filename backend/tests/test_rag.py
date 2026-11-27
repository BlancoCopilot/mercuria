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

    def __init__(self, text, refusal=False, citations=()):
        self.calls = []
        self.responses = SimpleNamespace(create=self._create)
        self.text, self.refusal, self.citations = text, refusal, citations

    def _create(self, **kw):
        self.calls.append(kw)
        part = SimpleNamespace(type="refusal", refusal="No.") if self.refusal else \
            SimpleNamespace(type="output_text", text=self.text, annotations=[
                SimpleNamespace(type="url_citation", url=u, title=t) for u, t in self.citations])
        return SimpleNamespace(output=[SimpleNamespace(type="reasoning"),
                                       SimpleNamespace(type="message", content=[part])],
                               output_text="" if self.refusal else self.text,
                               status="completed", model=kw["model"])


def _patch(monkeypatch, client, key="sk-test", effort="low", web=False):
    monkeypatch.setattr(chat, "search", lambda conn, q, k=6, tema=None: [dict(h) for h in HITS])
    monkeypatch.setattr(chat, "expand", lambda conn, hits: hits)
    monkeypatch.setattr(chat, "execute", lambda *a, **k: None)
    monkeypatch.setattr(chat, "_client", lambda: client)
    monkeypatch.setattr(chat, "get_settings", lambda: SimpleNamespace(
        openai_api_key=key, rag_model="gpt-5.4-mini", rag_reasoning_effort=effort, rag_top_k=6,
        chat_web_search=web))


def test_answer_cites_only_used_sources(monkeypatch):
    fake = FakeClient("No, cocinar no quita el mercurio [2].")
    _patch(monkeypatch, fake)
    r = chat.answer(None, "¿El pescado ahumado tiene menos mercurio?",
                    history=[{"rol": "usuario", "texto": "hola"}, {"rol": "asistente", "texto": "¿En qué ayudo?"}])
    assert r["respuesta"].startswith("No, cocinar")
    assert [f["archivo"] for f in r["fuentes"]] == ["oms.pdf"]
    kw = fake.calls[0]
    assert kw["model"] == "gpt-5.4-mini" and kw["store"] is False and kw["reasoning"] == {"effort": "low"}
    assert "Responde primero con lo que dicen los fragmentos" in kw["instructions"]
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


def test_web_search_tool_and_web_sources(monkeypatch):
    """Con búsqueda web activa: se ofrece la herramienta y las citas url_citation salen como fuentes 'web'."""
    fake = FakeClient("Según lo que encontré en internet, Guanay tiene 16.386 habitantes "
                      "([ine.gob.bo](https://www.ine.gob.bo/censo?utm_source=openai)).",
                      citations=[("https://www.ine.gob.bo/censo?utm_source=openai", "Censo 2024"),
                                 ("https://www.ine.gob.bo/censo?utm_source=openai", "repetida")])
    _patch(monkeypatch, fake, web=True)
    out = chat.answer(None, "¿Cuántos habitantes tiene Guanay?")
    call = fake.calls[0]
    assert call["tools"][0]["type"] == "web_search"
    assert "web_search" in call["instructions"] and "{web}" not in call["instructions"]
    assert "http" not in out["respuesta"] and "](" not in out["respuesta"]          # sin enlaces en el texto
    web = [f for f in out["fuentes"] if f["tipo"] == "web"]
    assert len(web) == 1 and web[0]["url"] == "https://www.ine.gob.bo/censo" and web[0]["archivo"] == "ine.gob.bo"


def test_no_web_search_when_disabled(monkeypatch):
    fake = FakeClient("No tengo esa información en mis documentos.")
    _patch(monkeypatch, fake, web=False)
    chat.answer(None, "¿algo?")
    assert "tools" not in fake.calls[0] and "No tengo esa información" in fake.calls[0]["instructions"]


def test_voice_session_config(monkeypatch):
    """La sesión GPT-Live delega en Responses con buscar_documentos + web_search y limita el canal del navegador."""
    from rastrohg.rag import voice

    seen = {}

    def create(session, transport):
        seen.update(session=session, transport=transport)
        return SimpleNamespace(transport=SimpleNamespace(sdp="v=0 answer"), session=SimpleNamespace(id="live_1"))

    monkeypatch.setattr(voice, "_client", lambda: SimpleNamespace(live=SimpleNamespace(create=create)))
    monkeypatch.setattr(voice, "get_settings", lambda: SimpleNamespace(
        live_model="gpt-live-1.1", live_voice="luciernaga", live_backend_model="", rag_model="gpt-5.4-mini",
        rag_reasoning_effort="low", chat_web_search=True, live_idle_timeout_s=20, live_max_minutes=5))
    out = voice.create_session("v=0 offer", None, [{"rol": "usuario", "texto": "hola"}], safety_id="abc")
    s = seen["session"]
    assert out == {"sdp": "v=0 answer", "session_id": "live_1", "max_minutes": 5}
    assert seen["transport"] == {"type": "webrtc", "sdp": "v=0 offer"}
    assert s["model"] == "gpt-live-1.1" and s["store"] is False and s["audio"]["output"]["voice"] == "luciernaga"
    tools = [t.get("name", t["type"]) for t in s["delegation"]["responses"]["tools"]]
    assert tools == ["buscar_documentos", "web_search"]
    assert "session.update" not in s["client"]["data_channel"]["allowed_client_events"]   # el navegador no cambia la sesión
    assert "Persona: hola" in s["instructions"]


def _pdf_with_figure(path, scanned=False):
    """PDF de 2 páginas: la 1 con un gráfico grande, la 2 con un ícono chico (o una página escaneada)."""
    import pymupdf

    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 400, 300), 0)
    pix.set_rect(pix.irect, (30, 120, 60))
    png = pix.tobytes("png")
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), "Mercurio en peces del río Beni, figura 1.")
    if scanned:
        p1.insert_image(p1.rect, stream=png, keep_proportion=False)
        p1.insert_textbox(pymupdf.Rect(72, 100, 520, 700), "texto OCR del libro escaneado " * 20)
    else:
        p1.insert_image(pymupdf.Rect(72, 120, 472, 420), stream=png)
    p2 = doc.new_page()
    p2.insert_text((72, 72), "Página con un ícono.")
    p2.insert_image(pymupdf.Rect(72, 100, 102, 130), stream=png)
    doc.save(path)


def test_figures_extracted_described_and_merged(tmp_path, monkeypatch):
    from rastrohg.rag import images
    from rastrohg.rag.ingest import Chunk, merge_figures

    pdf = tmp_path / "estudio.pdf"
    _pdf_with_figure(pdf)
    figs = images.extract_figures(pdf, max_figures=10)
    assert [f.page for f in figs] == [1]                     # el ícono de la p. 2 no cuenta

    calls = []
    monkeypatch.setattr(images, "describe", lambda fig, title: calls.append(fig.page) or "Gráfico: blanquillo 1,9 ppm.")
    cache: dict = {}
    out = images.figure_texts(pdf, "Estudio", cache)
    assert out[0][:2] == (1, "Gráfico: blanquillo 1,9 ppm.") and len(cache) == 1
    images.figure_texts(pdf, "Estudio", cache)               # segunda vez: sale del caché, no se vuelve a pagar
    assert calls == [1]

    merged = merge_figures([Chunk("texto p1", 1), Chunk("texto p2", 2)], out, "Estudio")
    assert [c.content[:6] for c in merged] == ["texto ", "Figura", "texto "]
    assert merged[1].page == 1 and merged[1].meta["figura"]


def test_scanned_page_and_decorative_images_are_skipped(tmp_path, monkeypatch):
    from rastrohg.rag import images

    pdf = tmp_path / "libro.pdf"
    _pdf_with_figure(pdf, scanned=True)
    assert images.extract_figures(pdf, max_figures=10) == []

    pdf2 = tmp_path / "logo.pdf"
    _pdf_with_figure(pdf2)
    monkeypatch.setattr(images, "describe", lambda fig, title: "SIN_INFORMACION")
    assert images.figure_texts(pdf2, "Logo", {}) == []

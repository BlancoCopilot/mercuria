"""Ingesta: PDFs (con texto, ya pasados por OCR) + preguntas frecuentes -> tabla `chunks`.

Estructura esperada de la carpeta (la del paquete Gold4Good_RAG_contenido):
    <dir>/docs/*.pdf
    <dir>/docs/temas.json          {"archivo.pdf": "peces" | "salud" | "mineria" | "agua"}
    <dir>/docs/DOCUMENTOS.md       tabla con el título de cada PDF (opcional)
    <dir>/preguntas_frecuentes.csv separado por ';' (opcional)

Idempotente: un documento cuyo sha256 no cambió no se vuelve a procesar.
"""
from __future__ import annotations

import csv
import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import Connection, text

from .. import db
from .embed import embed_passages

log = logging.getLogger(__name__)

# ~1000 caracteres ≈ 250 tokens: un párrafo o dos, con sentido propio.
# Al responder se agregan los fragmentos vecinos, así que el contexto final es más amplio.
CHUNK_CHARS = 1000
OVERLAP_CHARS = 150
MIN_CHARS = 60


@dataclass
class Chunk:
    content: str
    page: int | None
    meta: dict = field(default_factory=dict)


# --- Limpieza y corte -------------------------------------------------------
def clean(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)                 # ligaduras "ﬁ" -> "fi", espacios duros -> espacio
    s = re.sub(r"\u00ad\s*", "", s)                      # guion blando del OCR: "activa\u00ad ción" -> "activación"
    s = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", s)         # palabras cortadas con guion al final de línea
    s = re.sub(r"\s*\n\s*", " ", s)
    s = re.sub(r"[ \t ]+", " ", s)
    return s.strip()


_SENT = re.compile(r"(?<=[.!?;:])\s+(?=[\"“(¿¡A-ZÁÉÍÓÚÑ0-9•\-])")


def split_text(t: str, size: int = CHUNK_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    """Corta por oraciones en piezas de ~size caracteres, con solapamiento de ~overlap."""
    if len(t) <= size:
        return [t] if t else []
    sents: list[str] = []
    for s in _SENT.split(t):
        while len(s) > size:                              # oración enorme (tablas, OCR): corte duro por palabras
            cut = s.rfind(" ", 0, size)
            cut = cut if cut > size // 2 else size
            sents.append(s[:cut])
            s = s[cut:].lstrip()
        if s:
            sents.append(s)
    out: list[str] = []
    cur: list[str] = []
    n = 0
    for s in sents:
        if cur and n + len(s) + 1 > size:
            out.append(" ".join(cur))
            tail: list[str] = []                          # solapamiento: últimas oraciones del trozo anterior
            m = 0
            for prev in reversed(cur):
                if m + len(prev) > overlap:
                    break
                tail.insert(0, prev)
                m += len(prev) + 1
            cur, n = tail, m
        cur.append(s)
        n += len(s) + 1
    if cur:
        last = " ".join(cur)
        if out and len(last) < MIN_CHARS * 2:
            out[-1] = out[-1] + " " + last
        else:
            out.append(last)
    return out


def pdf_chunks(path: Path) -> tuple[list[Chunk], int]:
    import pymupdf

    out: list[Chunk] = []
    with pymupdf.open(path) as doc:
        for i, page in enumerate(doc, start=1):
            blocks = [clean(b[4]) for b in page.get_text("blocks", sort=True) if b[6] == 0]
            page_text = " ".join(b for b in blocks if b)
            for piece in split_text(page_text):
                if len(piece) >= MIN_CHARS:
                    out.append(Chunk(piece, i))
        return out, doc.page_count


def faq_chunks(path: Path) -> list[tuple[str, Chunk]]:
    """Cada pregunta frecuente es un fragmento entero (no se corta): devuelve (tema, Chunk)."""
    out = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for i, r in enumerate(csv.DictReader(fh, delimiter=";"), start=1):
            if not (r.get("pregunta") and r.get("respuesta")):
                continue
            content = f"Pregunta frecuente: {r['pregunta'].strip()}\nRespuesta: {r['respuesta'].strip()}"
            meta = {"n": i, "pregunta": r["pregunta"].strip(), "fuente": (r.get("fuente") or "").strip(),
                    "verificado": (r.get("verificado") or "").strip(),
                    "palabras_clave": (r.get("palabras_clave") or "").strip()}
            if meta["palabras_clave"]:
                content += f"\nPalabras clave: {meta['palabras_clave']}"
            out.append(((r.get("tema") or "").strip() or None, Chunk(content, None, meta)))
    return out


def read_titles(md: Path) -> dict[str, str]:
    """Títulos desde la tabla de DOCUMENTOS.md: | archivo.pdf | Título | tema | páginas |"""
    titles: dict[str, str] = {}
    if not md.exists():
        return titles
    for line in md.read_text(encoding="utf-8").splitlines():
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) >= 2 and cols[0].endswith(".pdf"):
            titles[cols[0]] = re.sub(r"[*_]", "", cols[1])
    return titles


# --- Carga a la base ---------------------------------------------------------
def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _store(conn: Connection, filename: str, title: str, kind: str, tema: str | None, pages: int | None,
           sha: str, items: list[tuple[str | None, Chunk]]) -> int:
    db.execute(conn, "DELETE FROM rag_document WHERE filename = :f", f=filename)
    doc_id = db.scalar(conn, """INSERT INTO rag_document (filename, title, kind, tema, pages, sha256)
                                VALUES (:f, :t, :k, :tema, :p, :s) RETURNING id""",
                       f=filename, t=title, k=kind, tema=tema, p=pages, s=sha)
    vectors = embed_passages(c.content for _, c in items)
    conn.execute(text("""INSERT INTO chunks (document_id, kind, tema, page, ord, content, meta, embedding)
                         VALUES (:d, :k, :tema, :p, :o, :c, CAST(:m AS jsonb), CAST(:e AS vector))"""),
                 [{"d": doc_id, "k": kind, "tema": t, "p": c.page, "o": o, "c": c.content,
                   "m": json.dumps(c.meta, ensure_ascii=False), "e": v}
                  for o, ((t, c), v) in enumerate(zip(items, vectors))])
    return len(items)


def ingest_dir(root: str | Path, force: bool = False) -> dict:
    root = Path(root)
    docs = root / "docs" if (root / "docs").is_dir() else root
    temas_path = docs / "temas.json"
    temas: dict[str, str] = json.loads(temas_path.read_text(encoding="utf-8")) if temas_path.exists() else {}
    titles = read_titles(docs / "DOCUMENTOS.md")
    report: dict = {"ingestados": [], "sin_cambios": [], "sin_texto": [], "fragmentos": 0}

    with db.tx() as conn:
        known = {r["filename"]: r["sha256"] for r in db.rows(conn, "SELECT filename, sha256 FROM rag_document")}

    for pdf in sorted(docs.glob("*.pdf")):
        sha = _sha(pdf)
        if not force and known.get(pdf.name) == sha:
            report["sin_cambios"].append(pdf.name)
            continue
        chunks, pages = pdf_chunks(pdf)
        if not chunks:
            report["sin_texto"].append(pdf.name)
            log.warning("%s: sin texto extraíble (¿falta OCR?)", pdf.name)
            continue
        tema = temas.get(pdf.name)
        with db.tx() as conn:
            n = _store(conn, pdf.name, titles.get(pdf.name, pdf.stem.replace("_", " ")), "pdf", tema, pages, sha,
                       [(tema, c) for c in chunks])
        log.info("%s: %d páginas, %d fragmentos", pdf.name, pages, n)
        report["ingestados"].append({"archivo": pdf.name, "paginas": pages, "fragmentos": n})
        report["fragmentos"] += n

    faq = next((p for p in (root / "preguntas_frecuentes.csv", docs / "preguntas_frecuentes.csv") if p.exists()), None)
    if faq:
        sha = _sha(faq)
        if force or known.get(faq.name) != sha:
            items = faq_chunks(faq)
            with db.tx() as conn:
                n = _store(conn, faq.name, "Preguntas frecuentes del equipo Gold4Good (verificadas)", "faq",
                           None, None, sha, items)
            report["ingestados"].append({"archivo": faq.name, "fragmentos": n})
            report["fragmentos"] += n
        else:
            report["sin_cambios"].append(faq.name)

    # Lo que ya no está en la carpeta sale de la base (p. ej. el manual de retorta en portugués,
    # reemplazado por la traducción sin los primeros auxilios de 1995): el chatbot no debe citarlo.
    present = [p.name for p in docs.glob("*.pdf")] + ([faq.name] if faq else [])
    with db.tx() as conn:
        report["eliminados"] = [r["filename"] for r in db.rows(
            conn, "DELETE FROM rag_document WHERE NOT (filename = ANY(:p)) RETURNING filename", p=present)]
        refresh_lexemes(conn)
    return report


def refresh_lexemes(conn: Connection) -> None:
    db.execute(conn, "TRUNCATE rag_lexeme")
    db.execute(conn, "INSERT INTO rag_lexeme (word, ndoc) SELECT word, ndoc FROM ts_stat('SELECT tsv FROM chunks')")

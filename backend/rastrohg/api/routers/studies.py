"""Aportes de investigación: subir PDF/CSV, revisar lo que propone la IA y publicar."""
from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ...db import one, rows
from ...research import service
from ...settings import get_settings
from ...worker.queue import enqueue, request_recompute
from ..deps import DbDep, require
from ..schemas import PublishIn, RecordUpdate

router = APIRouter(prefix="/v1/studies", tags=["aportes de investigación"])
Researcher = Annotated[dict, Depends(require("investigador"))]
LICENSES = ("CC-BY-4.0", "CC0-1.0", "CC-BY-SA-4.0")


def _own(db: DbDep, sid: int, user: dict) -> dict:
    st = one(db.conn, "SELECT * FROM study WHERE id=:id", id=sid)
    if not st or (st["submitted_by"] != user["id"] and user["role"] != "admin"):
        raise HTTPException(404, "Estudio no encontrado")
    return st


@router.post("", status_code=201)
async def create(db: DbDep, user: Researcher,
                 file: UploadFile = File(...), title: str = Form(..., min_length=3, max_length=400),
                 authors: str = Form(""), year: int | None = Form(None), doi: str = Form(""), url: str = Form(""),
                 institution: str = Form(""), license: str = Form("CC-BY-4.0"),
                 embargo_until: date | None = Form(None), pdf_open_access: bool = Form(False)):
    name = (file.filename or "").lower()
    if not name.endswith((".pdf", ".csv", ".txt")):
        raise HTTPException(400, "Sube un PDF (artículo, tesis, informe) o un CSV con las mediciones.")
    if license not in LICENSES:
        raise HTTPException(400, "Licencia no válida")
    if embargo_until and embargo_until > date.today() + timedelta(days=366):
        raise HTTPException(400, "El embargo puede durar como máximo 12 meses.")
    limit = get_settings().research_max_pdf_mb * 1024 * 1024
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(413, f"El archivo supera {get_settings().research_max_pdf_mb} MB.")
    if name.endswith(".pdf") and not content.startswith(b"%PDF"):
        raise HTTPException(400, "El archivo no parece un PDF válido.")
    meta = {"title": title.strip(), "authors": authors.strip() or None, "year": year, "doi": doi.strip() or None,
            "url": url.strip() or None, "institution": institution.strip() or user.get("org"), "license": license,
            "embargo": embargo_until, "oa": pdf_open_access}
    try:
        st = service.create_study(db.conn, meta, name if name.endswith(".pdf") else "datos.csv", content, user["id"])
    except Exception as e:  # noqa: BLE001  (CSV ilegible, etc.)
        raise HTTPException(400, f"No pudimos leer el archivo: {e}")
    if st["kind"] == "pdf":
        db.after_commit(enqueue, "rastrohg.worker.jobs.extract_study", st["id"])
    return {"id": st["id"], "estado": "procesando" if st["kind"] == "pdf" else "en_revision"}


@router.get("")
def mine(db: DbDep, user: Researcher):
    return rows(db.conn, """
        SELECT s.id, s.title, s.year, s.status, s.source_kind, s.license, s.embargo_until, s.created_at, s.published_at,
               count(r.id) AS registros, count(r.id) FILTER (WHERE r.status='aprobado') AS aprobados,
               count(r.measurement_id) AS en_mapa
        FROM study s LEFT JOIN study_record r ON r.study_id = s.id
        WHERE s.submitted_by = :u OR :admin
        GROUP BY s.id ORDER BY s.created_at DESC""", u=user["id"], admin=user["role"] == "admin")


@router.get("/{sid}")
def detail(sid: int, db: DbDep, user: Researcher):
    st = _own(db, sid, user)
    st.pop("extraction", None)
    recs = rows(db.conn, "SELECT * FROM study_record WHERE study_id=:s ORDER BY id", s=sid)
    return {"estudio": st, "registros": recs, "cita": service.citation(st)}


@router.get("/{sid}/file")
def original(sid: int, db: DbDep, user: Researcher):
    st = _own(db, sid, user)
    path = os.path.join(get_settings().upload_dir, st["file_path"] or "")
    if not st["file_path"] or not os.path.exists(path):
        raise HTTPException(404)
    return FileResponse(path, media_type="application/pdf" if st["source_kind"] == "pdf" else "text/csv")


@router.patch("/{sid}/records/{rid}")
def edit_record(sid: int, rid: int, body: RecordUpdate, db: DbDep, user: Researcher):
    _own(db, sid, user)
    if not one(db.conn, "SELECT 1 AS x FROM study_record WHERE id=:r AND study_id=:s", r=rid, s=sid):
        raise HTTPException(404)
    try:
        return service.update_record(db.conn, rid, body.fields, body.status, user["id"])
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.post("/{sid}/approve-all")
def approve_all(sid: int, db: DbDep, user: Researcher):
    """Aprueba de una vez las propuestas sin problemas que bloqueen el mapa."""
    _own(db, sid, user)
    r = one(db.conn, """UPDATE study_record SET status='aprobado', updated_by=:u, updated_at=now()
                        WHERE study_id=:s AND status='propuesto' AND modeled RETURNING count(*) OVER () AS n""",
            s=sid, u=user["id"])
    return {"aprobados": r["n"] if r else 0}


@router.post("/{sid}/publish")
def publish(sid: int, body: PublishIn, db: DbDep, user: Researcher):
    st = _own(db, sid, user)
    if st["status"] not in ("en_revision", "publicado"):
        raise HTTPException(409, f"El estudio está «{st['status']}»; no se puede publicar ahora.")
    if body.embargo_until and body.embargo_until > date.today() + timedelta(days=366):
        raise HTTPException(400, "El embargo puede durar como máximo 12 meses.")
    try:
        res = service.publish(db.conn, sid, body.license, body.embargo_until)
    except ValueError as e:
        raise HTTPException(409, str(e))
    if res.get("al_mapa"):
        db.after_commit(request_recompute, "medicion", {"estudio": sid, "n": res["al_mapa"]})
    return res


@router.post("/{sid}/reextract", status_code=202)
def reextract(sid: int, db: DbDep, user: Researcher):
    st = _own(db, sid, user)
    if st["source_kind"] != "pdf" or st["status"] == "publicado":
        raise HTTPException(409, "Solo se puede volver a extraer un PDF no publicado.")
    db.conn.exec_driver_sql("UPDATE study SET status='procesando', error=NULL WHERE id=%s", (sid,))
    db.after_commit(enqueue, "rastrohg.worker.jobs.extract_study", sid)
    return {"estado": "procesando"}

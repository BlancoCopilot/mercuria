"""Módulo 6 (ficha "Mi comunidad") y gestión de traducciones/audios por líderes."""
from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import text

from ...db import one, rows
from ...services.card import TEXTOS_ES, community_card
from ...settings import get_settings
from ..deps import DbDep, optional_device, require
from ..schemas import Lang, TranslationIn

router = APIRouter(prefix="/v1", tags=["comunidades"])
Leader = Annotated[dict, Depends(require("lider"))]


@router.get("/communities")
def search(db: DbDep, q: str | None = None, lat: float | None = None, lon: float | None = None, limit: int = 20):
    if q:
        return rows(db.conn, """SELECT id, name, municipio, poblacion, h3, similarity(name, :q) AS score
                                FROM settlement WHERE name % :q OR name ILIKE '%' || :q || '%'
                                ORDER BY score DESC LIMIT :n""", q=q, n=limit)
    if lat is not None and lon is not None:
        return rows(db.conn, """SELECT id, name, municipio, poblacion, h3,
                       round((ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon,:lat),4326)::geography)/1000)::numeric, 1) AS km
                       FROM settlement ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon,:lat),4326) LIMIT :n""",
                    lat=lat, lon=lon, n=limit)
    return rows(db.conn, "SELECT id, name, municipio, poblacion, h3 FROM settlement ORDER BY poblacion DESC NULLS LAST LIMIT :n", n=limit)


@router.get("/communities/{settlement_id}/card")
def card(settlement_id: int, db: DbDep, lang: Lang = "es",
         device: Annotated[dict | None, Depends(optional_device)] = None):
    c = community_card(db.conn, settlement_id, lang)
    if c is None:
        raise HTTPException(404, "Comunidad no encontrada")
    db.conn.execute(text("INSERT INTO outreach_event (kind, settlement_id, device_id) VALUES ('ficha', :s, :d)"),
                    {"s": settlement_id, "d": device["id"] if device else None})
    return c


@router.get("/translations")
def list_translations(db: DbDep, lang: Lang, _: Leader):
    have = {r["key"]: r for r in rows(db.conn, "SELECT * FROM translation WHERE lang=:l", l=lang)}
    return [{"key": k, "es": v, "traduccion": have.get(k)} for k, v in TEXTOS_ES.items()]


@router.put("/translations")
def upsert_translation(body: TranslationIn, db: DbDep, _: Leader):
    if body.key not in TEXTOS_ES:
        raise HTTPException(400, "Clave desconocida")
    return one(db.conn, """INSERT INTO translation (key, lang, text) VALUES (:k, :l, :t)
                           ON CONFLICT (key, lang) DO UPDATE SET text=EXCLUDED.text, status='borrador'
                           RETURNING id, key, lang, status""", k=body.key, l=body.lang, t=body.text)


@router.post("/translations/{tid}/audio")
async def upload_audio(tid: int, db: DbDep, _: Leader, file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".m4a", ".mp3", ".ogg", ".aac", ".wav"):
        raise HTTPException(400, "Formato de audio no soportado")
    folder = os.path.join(get_settings().upload_dir, "audio")
    os.makedirs(folder, exist_ok=True)
    name = f"t{tid}{ext}"
    with open(os.path.join(folder, name), "wb") as fh:
        fh.write(await file.read(10 * 1024 * 1024))
    db.conn.execute(text("UPDATE translation SET audio_path=:p, status='borrador' WHERE id=:id"), {"p": name, "id": tid})
    return {"ok": True, "audio_url": f"/media/audio/{name}"}


@router.post("/translations/{tid}/validate")
def validate_translation(tid: int, db: DbDep, user: Leader):
    r = one(db.conn, """UPDATE translation SET status='validada', validated_by=:u WHERE id=:id
                        RETURNING id, key, lang, status""", u=user["id"], id=tid)
    if not r:
        raise HTTPException(404)
    return r

"""Validación de denuncias por líderes comunitarios (módulo 9).

Solo líderes/admin ven la ubicación exacta y la foto. Validar no cambia el peso de la
denuncia (0,2); rechazarla descarta el sitio provisional y recalcula el mapa.
"""
from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import text

from ...db import one, rows
from ...settings import get_settings
from ...worker.queue import request_recompute
from ..deps import DbDep, require
from ..schemas import ReportReview

router = APIRouter(prefix="/v1/reports", tags=["denuncias"])
Leader = Annotated[dict, Depends(require("lider"))]


@router.get("")
def list_reports(db: DbDep, _: Leader, status: str = "pendiente", limit: int = 100):
    return rows(db.conn, """
        SELECT id, kind, description, status, area_ha, site_id, h3, photo_path IS NOT NULL AS tiene_foto,
               ST_Y(geom) AS lat, ST_X(geom) AS lon, created_client_at, received_at,
               received_at - created_client_at AS demora_sincronizacion
        FROM report WHERE status = :s ORDER BY received_at DESC LIMIT :n""", s=status, n=limit)


@router.post("/{rid}/review")
def review(rid: str, body: ReportReview, db: DbDep, user: Leader):
    r = one(db.conn, """UPDATE report SET status=:s, validated_by=:u, validated_at=now()
                        WHERE id=CAST(:id AS uuid) RETURNING id, kind, site_id, status""",
            s=body.decision, u=user["id"], id=rid)
    if not r:
        raise HTTPException(404)
    if body.decision == "rechazada" and r["site_id"]:
        db.conn.execute(text("""UPDATE mining_site SET status='descartado', updated_at=now()
                                WHERE id=:s AND origin='denuncia'"""), {"s": r["site_id"]})
        db.after_commit(request_recompute, "denuncia_rechazada", rid)
    db.conn.execute(text("INSERT INTO audit_log (user_id, action, entity, entity_id) VALUES (:u, :a, 'report', :id)"),
                    {"u": user["id"], "a": f"report.{body.decision}", "id": rid})
    return r


@router.get("/{rid}/photo")
def photo(rid: str, db: DbDep, _: Leader):
    r = one(db.conn, "SELECT photo_path FROM report WHERE id=CAST(:id AS uuid)", id=rid)
    if not r or not r["photo_path"]:
        raise HTTPException(404)
    return FileResponse(os.path.join(get_settings().upload_dir, r["photo_path"]), media_type="image/jpeg")

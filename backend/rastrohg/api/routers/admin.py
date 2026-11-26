from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from rq.job import Job
from shapely.geometry import shape

from ...db import one, rows
from ...ingest.detections import ingest_features
from ...worker.queue import enqueue, redis_conn, request_recompute
from ..deps import DbDep, require
from ..schemas import DetectionsIn, UserIn
from ..security import hash_password

router = APIRouter(prefix="/v1/admin", tags=["admin"])
Admin = Annotated[dict, Depends(require("admin"))]


@router.post("/detections")
def post_detections(body: DetectionsIn, db: DbDep, _: Admin):
    """Ingesta manual de polígonos de minería (misma ruta que la tarea mensual de AMW)."""
    feats = []
    for f in body.geojson.get("features", []):
        props = f.get("properties") or {}
        d = props.get("detected_on")
        feats.append((shape(f["geometry"]), date.fromisoformat(d) if d else date.today(), props.get("id")))
    res = ingest_features(db.conn, feats, body.source, body.is_synthetic)
    if res["sitios_cambiados"]:
        db.after_commit(request_recompute, "satelite", {"fuente": body.source, "sitios": res["sitios_cambiados"]})
    return {**res, "recalculo_pendiente": bool(res["sitios_cambiados"])}


@router.post("/ingest/{source}", status_code=202)
def ingest(source: str, _: Admin):
    if source not in ("amw", "mapbiomas", "osm"):
        raise HTTPException(400, "Fuente: amw | mapbiomas | osm")
    return {"job_id": enqueue("rastrohg.worker.jobs.ingest", source)}


@router.post("/recompute", status_code=202)
def recompute(_: Admin):
    return {"job_id": request_recompute("manual"), "nota": "null = ya había un recálculo en cola (se agregó el disparador)"}


@router.get("/jobs/{job_id}")
def job(job_id: str, _: Admin):
    try:
        j = Job.fetch(job_id, connection=redis_conn())
    except Exception:  # noqa: BLE001
        raise HTTPException(404, "Trabajo no encontrado")
    return {"id": j.id, "estado": j.get_status(), "resultado": j.return_value(),
            "error": j.exc_info.splitlines()[-1] if j.exc_info else None}


@router.get("/versions")
def versions(db: DbDep, _: Admin, limit: int = 20):
    return rows(db.conn, "SELECT * FROM map_version ORDER BY id DESC LIMIT :n", n=limit)


@router.post("/users", status_code=201)
def create_user(body: UserIn, db: DbDep, _: Admin):
    return one(db.conn, """INSERT INTO app_user (email, name, role, org, lab_id, settlement_id, password_hash)
                           VALUES (:e, :n, :r, :o, :l, :s, :p) RETURNING id, email, role""",
               e=body.email, n=body.name, r=body.role, o=body.org, l=body.lab_id, s=body.settlement_id,
               p=hash_password(body.password))


@router.get("/outbox")
def outbox(db: DbDep, _: Admin, limit: int = 20):
    """Notificaciones generadas (para verificar alertas en la demo)."""
    return rows(db.conn, """SELECT o.id, o.title, o.body, o.data, o.status, o.last_error, o.created_at
                            FROM push_outbox o ORDER BY o.id DESC LIMIT :n""", n=limit)



@router.get("/users")
def users(db: DbDep, _: Admin, pendientes: bool = False):
    return rows(db.conn, """SELECT id, email, name, role, org, active, created_at FROM app_user
                            WHERE (NOT :p OR NOT active) ORDER BY active, created_at DESC""", p=pendientes)


@router.post("/users/{uid}/activate")
def activate(uid: int, db: DbDep, _: Admin):
    r = one(db.conn, "UPDATE app_user SET active=true WHERE id=:id RETURNING id, email, role", id=uid)
    if not r:
        raise HTTPException(404)
    return r

"""Dispositivos anónimos, sincronización offline y fotos de denuncias (módulo 9).

Sincronización: el teléfono guarda denuncias/encuestas en SQLite con un client_uuid
propio. Al volver la señal manda TODO en un POST /v1/sync. El servidor inserta con
ON CONFLICT (client_uuid) DO NOTHING: reenviar el mismo lote (porque se cortó la
conexión a mitad) no duplica nada. En la misma respuesta devuelve las celdas del mapa
que cambiaron desde la versión que tiene el teléfono: un solo viaje de red.
"""
from __future__ import annotations

import io
import os
from typing import Annotated
from uuid import UUID

import h3
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from PIL import Image, ImageOps
from sqlalchemy import text

from ...db import one, rows
from ...ingest.base import cell_of
from ...ingest.detections import site_from_report
from ...settings import get_settings
from ...worker.queue import request_recompute
from ..deps import DbDep, client_ip_hash, current_device, rate_limit
from ..schemas import DeviceIn, DeviceOut, DeviceUpdate, SyncIn
from ..security import new_device_token
from .map import cells_since

router = APIRouter(prefix="/v1", tags=["dispositivos y sincronización"])
SYNTHETIC_PREFIX = "[SINTÉTICO]"
Device = Annotated[dict, Depends(current_device)]


@router.post("/devices", response_model=DeviceOut, status_code=201)
def register_device(body: DeviceIn, request: Request, db: DbDep):
    rate_limit(f"devreg:{client_ip_hash(request)}", get_settings().device_registrations_per_ip_hour)
    tok, h = new_device_token()
    d = one(db.conn, "INSERT INTO device (token_hash, platform, lang) VALUES (:h, :p, :l) RETURNING id",
            h=h, p=body.platform, l=body.lang)
    return DeviceOut(device_id=d["id"], device_token=tok)


@router.put("/devices/me")
def update_device(body: DeviceUpdate, dev: Device, db: DbDep):
    if body.push_token is not None:
        db.conn.execute(text("UPDATE device SET push_token=:t WHERE id=:id"), {"t": body.push_token, "id": dev["id"]})
    if body.lang:
        db.conn.execute(text("UPDATE device SET lang=:l WHERE id=:id"), {"l": body.lang, "id": dev["id"]})
    cells = set(body.subscribe_h3)
    if body.subscribe_settlements:
        cells |= {r["h3"] for r in rows(db.conn, "SELECT h3 FROM settlement WHERE id = ANY(:ids) AND h3 IS NOT NULL",
                                        ids=body.subscribe_settlements)}
    if body.subscribe_point:
        c = cell_of(*body.subscribe_point)
        cells |= set(h3.grid_disk(c, 1))
    if cells:
        db.conn.execute(text("""INSERT INTO device_subscription (device_id, h3)
                                SELECT :d, h3 FROM h3_cell WHERE h3 = ANY(:c) ON CONFLICT DO NOTHING"""),
                        {"d": dev["id"], "c": list(cells)})
    subs = [r["h3"] for r in rows(db.conn, "SELECT h3 FROM device_subscription WHERE device_id=:d", d=dev["id"])]
    return {"suscripciones": subs}


@router.post("/sync")
def sync(body: SyncIn, dev: Device, db: DbDep):
    s = get_settings()
    acc_r, dup_r, acc_f, dup_f = [], [], [], []
    mining_reports = []
    for r in body.reports:
        res = one(db.conn, """
            INSERT INTO report (client_uuid, device_id, kind, description, geom, h3, area_ha, created_client_at, is_synthetic)
            VALUES (:cu, :d, :k, :desc, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :h3, :a, :t, :syn)
            ON CONFLICT (client_uuid) DO NOTHING RETURNING id""",
            cu=r.client_uuid, d=dev["id"], k=r.kind, desc=r.description, lon=r.lon, lat=r.lat,
            h3=cell_of(r.lat, r.lon), a=r.area_ha, t=r.created_client_at,
            # ensayos/demo: el prefijo marca la denuncia como sintética (purge-synthetic la borra)
            syn=(r.description or "").startswith(SYNTHETIC_PREFIX))
        if res is None:
            dup_r.append(str(r.client_uuid))
            continue
        rate_limit(f"reports:{dev['id']}", s.reports_per_device_hour)   # solo cuenta lo nuevo
        acc_r.append(str(r.client_uuid))
        if r.kind == "mineria":
            mining_reports.append(str(res["id"]))
    for f in body.fish_surveys:
        res = one(db.conn, """
            INSERT INTO fish_survey (client_uuid, device_id, settlement_id, h3, comidas_semana, especies, created_client_at)
            VALUES (:cu, :d, :s, :h3, :c, :e, :t) ON CONFLICT (client_uuid) DO NOTHING RETURNING id""",
            cu=f.client_uuid, d=dev["id"], s=f.settlement_id, h3=cell_of(f.lat, f.lon), c=f.comidas_semana,
            e=f.especies, t=f.created_client_at)
        (acc_f if res else dup_f).append(str(f.client_uuid))

    # Denuncia de minería => sitio provisional con peso 0,2 que entra al mapa de inmediato.
    new_sites = [site_from_report(db.conn, rid) for rid in mining_reports]
    if new_sites or acc_f:
        db.after_commit(request_recompute, "denuncia" if new_sites else "encuesta",
                        {"sitios": new_sites, "encuestas": len(acc_f)})
    version, cells = cells_since(db.conn, body.since_version)
    return {
        "reports": {"aceptadas": acc_r, "duplicadas": dup_r},
        "fish_surveys": {"aceptadas": acc_f, "duplicadas": dup_f},
        "recalculo_pendiente": bool(new_sites or acc_f),
        "mapa": {"version": version, "celdas_cambiadas": cells},
    }


@router.post("/reports/{client_uuid}/photo")
async def upload_photo(client_uuid: UUID, dev: Device, db: DbDep, file: UploadFile = File(...)):
    s = get_settings()
    rep = one(db.conn, "SELECT id FROM report WHERE client_uuid=:c AND device_id=:d", c=client_uuid, d=dev["id"])
    if not rep:
        raise HTTPException(404, "Denuncia no encontrada para este dispositivo")
    raw = await file.read(s.max_photo_mb * 1024 * 1024 + 1)
    if len(raw) > s.max_photo_mb * 1024 * 1024:
        raise HTTPException(413, f"Foto mayor a {s.max_photo_mb} MB")
    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "Imagen no válida")
    img = img.convert("RGB")
    img.thumbnail((2048, 2048))
    # Imagen nueva solo con píxeles: sin EXIF (GPS, modelo de teléfono, fecha), sin XMP ni ICC.
    clean = Image.frombytes("RGB", img.size, img.tobytes())
    folder = os.path.join(s.upload_dir, "reports")
    os.makedirs(folder, exist_ok=True)
    name = f"{rep['id']}.jpg"
    clean.save(os.path.join(folder, name), "JPEG", quality=85)
    db.conn.execute(text("UPDATE report SET photo_path=:p WHERE id=:id"), {"p": f"reports/{name}", "id": rep["id"]})
    return {"ok": True}

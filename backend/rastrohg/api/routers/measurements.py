"""Módulo 4: carga de resultados por laboratorios (formulario JSON o CSV) y kits."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse

from ...db import one, rows
from ...services.measurements import CSV_COLUMNS, insert_measurements, parse_csv
from ...worker.queue import request_recompute
from ..deps import DbDep, require
from ..schemas import Matrix, MeasurementIn, MeasurementReview

router = APIRouter(prefix="/v1/measurements", tags=["mediciones"])
Lab = Annotated[dict, Depends(require("laboratorio"))]


def _after(db: DbDep, res: dict) -> dict:
    if res["validas"]:
        db.after_commit(request_recompute, "medicion", {"lote": res["lote"], "n": len(res["validas"])})
    res["recalculo_pendiente"] = bool(res["validas"])
    return res


@router.post("")
def create(items: list[MeasurementIn], db: DbDep, user: Lab):
    res = insert_measurements(db.conn, [i.model_dump() for i in items], user["id"], user["lab_id"])
    return _after(db, res)


@router.post("/csv")
async def upload_csv(db: DbDep, user: Lab, file: UploadFile = File(...)):
    content = await file.read(5 * 1024 * 1024)
    try:
        items = parse_csv(content)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"CSV ilegible: {exc}")
    if not items:
        raise HTTPException(400, "CSV vacío")
    return _after(db, insert_measurements(db.conn, items, user["id"], user["lab_id"]))


@router.get("/template.csv", response_class=PlainTextResponse)
def template():
    return ",".join(CSV_COLUMNS) + "\n" + \
        "agua,450,ng/L,-15.49,-67.87,2026-10-02,laboratorio,CV-AAS,,no,,total,no,seca,,,,\n" + \
        "pez,0.82,mg/kg,-15.50,-67.86,2026-10-02,laboratorio,DMA-80,surubi,no,,total,no,seca,,,,\n"


@router.get("")
def list_(db: DbDep, _: Annotated[dict, Depends(require("laboratorio", "autoridad"))],
          matrix: Matrix | None = None, status: str | None = None, limit: int = 200):
    return rows(db.conn, """
        SELECT id, matrix, value, unit, value_original, unit_original, below_dl, season, source_type, weight, fish_species,
               status, reach_id, round(snap_distance_m::numeric) AS snap_m, sampled_on, is_synthetic,
               ST_Y(geom) AS lat, ST_X(geom) AS lon, created_at
        FROM measurement
        WHERE (CAST(:m AS text) IS NULL OR matrix=:m) AND (CAST(:s AS text) IS NULL OR status=:s)
        ORDER BY created_at DESC LIMIT :n""", m=matrix, s=status, n=limit)


@router.patch("/{mid}")
def review(mid: str, body: MeasurementReview, db: DbDep, _: Annotated[dict, Depends(require("admin"))]):
    r = one(db.conn, "UPDATE measurement SET status=:s WHERE id=CAST(:id AS uuid) RETURNING id, status, reach_id",
            s=body.status, id=mid)
    if not r:
        raise HTTPException(404)
    if r["reach_id"] is not None:
        db.after_commit(request_recompute, "medicion_revisada", mid)
    return r

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from ..db import engine
from ..settings import get_settings
from ..worker.queue import redis_conn
from .routers import admin, auth, chat, communities, decision, devices, health, map, measurements, reports, open as open_data, studies

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="RastroHg API",
    version="0.1.0",
    description="Mercurio de la minería aurífera en Bolivia: sitios, estimaciones con incertidumbre, "
                "riesgo por comunidad y acciones de salud.",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

for r in (auth, devices, map, communities, measurements, reports, health, decision, admin, chat, studies, open_data):
    app.include_router(r.router)

_audio = os.path.join(get_settings().upload_dir, "audio")
os.makedirs(_audio, exist_ok=True)
app.mount("/media/audio", StaticFiles(directory=_audio), name="audio")


@app.get("/healthz", tags=["sistema"])
def healthz():
    with engine().connect() as c:
        c.exec_driver_sql("SELECT 1")
    redis_conn().ping()
    return {"ok": True}

"""Conexión a Google Earth Engine.

Proyecto de Cloud: settings.ee_project (registrado en Earth Engine).
Autenticación, en este orden:
  1. Cuenta de servicio si EE_SERVICE_ACCOUNT_KEY apunta a un JSON (servidor/worker).
  2. Credenciales locales de `earthengine authenticate` (desarrollo).

Uso rápido:  uv run python -m rastrohg.ingest.earthengine
"""
from __future__ import annotations

import json
from functools import lru_cache

import ee

from ..settings import get_settings


@lru_cache
def init() -> str:
    """Inicializa Earth Engine una sola vez por proceso. Devuelve el proyecto usado."""
    s = get_settings()
    if s.ee_service_account_key:
        with open(s.ee_service_account_key) as f:
            email = json.load(f)["client_email"]
        creds = ee.ServiceAccountCredentials(email, s.ee_service_account_key)
        ee.Initialize(creds, project=s.ee_project)
    else:
        ee.Initialize(project=s.ee_project)
    return s.ee_project


def pilot_region() -> ee.Geometry:
    """Rectángulo de la cuenca piloto (settings.pilot_bbox)."""
    init()
    return ee.Geometry.Rectangle(list(get_settings().bbox))


def check() -> dict:
    """Prueba de conexión: cuenta imágenes Sentinel-2 sobre la cuenca piloto en 2025."""
    project = init()
    n = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
         .filterBounds(pilot_region())
         .filterDate("2025-01-01", "2026-01-01")
         .size()
         .getInfo())
    return {"project": project, "sentinel2_images_2025": n}


if __name__ == "__main__":
    print(check())

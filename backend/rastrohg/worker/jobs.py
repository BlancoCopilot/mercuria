"""Trabajos RQ. Cada función se puede encolar por nombre: 'rastrohg.worker.jobs.<fn>'."""
from __future__ import annotations

import logging

from . import pipeline, push
from .queue import enqueue, pop_triggers

log = logging.getLogger(__name__)


def recompute() -> dict:
    triggers = pop_triggers()
    res = pipeline.run_recompute(triggers)
    if res.get("estado") == "nueva_version":
        if res["alertas"]:
            enqueue("rastrohg.worker.jobs.send_push")
        enqueue("rastrohg.worker.jobs.suggest_sampling", "agua")
    return res


def suggest_sampling(matrix: str = "agua", k: int | None = None) -> dict:
    return pipeline.run_sampling(matrix, k)


def send_push() -> dict:
    return push.flush_outbox()


def ingest(source: str) -> dict:
    """Tareas programadas: amw (mensual), osm (mensual), mapbiomas (anual)."""
    from ..ingest import detections, osm
    from .queue import request_recompute

    if source in ("amw", "mapbiomas"):
        res = detections.ingest_remote(source)
        if res["sitios_cambiados"]:
            request_recompute("satelite", {"fuente": source, "sitios": res["sitios_cambiados"]})
    elif source == "osm":
        res = osm.ingest_osm()
        request_recompute("osm", res)
    else:
        raise ValueError(f"fuente desconocida: {source}")
    return res


def extract_study(study_id: int) -> dict:
    """PDF de investigación → propuestas de la IA (para revisión humana)."""
    from ..research.service import run_extraction
    return run_extraction(study_id)


def release_embargoes() -> dict:
    from ..research.service import release_embargoes as rel
    return rel()

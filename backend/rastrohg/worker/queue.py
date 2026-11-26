"""Cola RQ y "coalescencia" de recálculos.

Si llegan 50 resultados en un CSV, o 20 denuncias sincronizadas a la vez, no queremos
50 recálculos: los disparadores se acumulan en una lista de Redis y se encola UN solo
trabajo. Como hay un solo worker, las versiones del mapa se generan en serie y nunca
compiten entre sí.
"""
from __future__ import annotations

import json
from functools import lru_cache

from redis import Redis
from rq import Queue

from ..settings import get_settings

TRIGGERS_KEY = "rastrohg:recompute:triggers"
PENDING_KEY = "rastrohg:recompute:pending"


@lru_cache
def redis_conn() -> Redis:
    return Redis.from_url(get_settings().redis_url)


def queue(name: str = "default") -> Queue:
    return Queue(name, connection=redis_conn(), default_timeout=1800)


def request_recompute(tipo: str, ref: object = None) -> str | None:
    """Registra un disparador y encola un recálculo si no hay uno pendiente."""
    r = redis_conn()
    r.rpush(TRIGGERS_KEY, json.dumps({"tipo": tipo, "ref": ref}, default=str))
    if r.set(PENDING_KEY, "1", nx=True, ex=3600):
        job = queue().enqueue("rastrohg.worker.jobs.recompute")
        return job.id
    return None


def pop_triggers() -> list[dict]:
    r = redis_conn()
    r.delete(PENDING_KEY)   # a partir de aquí, un disparador nuevo encola otro recálculo
    pipe = r.pipeline()
    pipe.lrange(TRIGGERS_KEY, 0, -1)
    pipe.delete(TRIGGERS_KEY)
    raw, _ = pipe.execute()
    return [json.loads(x) for x in raw] or [{"tipo": "manual"}]


def enqueue(func: str, *args, **kwargs) -> str:
    return queue().enqueue(func, *args, **kwargs).id

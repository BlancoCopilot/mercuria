"""Envío de notificaciones con Expo Push (patrón outbox).

Las alertas se escriben en push_outbox dentro de la misma transacción que la nueva
versión del mapa; este trabajo las envía después. Si Expo falla, quedan pendientes y
el cron las reintenta: nunca se pierde un aviso por un corte de red del servidor.
"""
from __future__ import annotations

import logging

import httpx
from sqlalchemy import text

from ..db import rows, tx
from ..settings import get_settings

log = logging.getLogger(__name__)


def flush_outbox(batch: int = 100) -> dict:
    s = get_settings()
    sent = failed = 0
    with tx() as conn:
        pending = rows(conn, """
            SELECT o.id, o.title, o.body, o.data, d.push_token
            FROM push_outbox o JOIN device d ON d.id = o.device_id
            WHERE o.status = 'pendiente' AND o.attempts < 5
            ORDER BY o.id LIMIT :n FOR UPDATE OF o SKIP LOCKED""", n=batch)
        if not pending:
            return {"enviados": 0, "errores": 0}
        if not s.push_enabled:
            conn.execute(text("""UPDATE push_outbox SET status='enviado', sent_at=now(),
                                 last_error='simulado (PUSH_ENABLED=false)' WHERE id = ANY(:ids)"""),
                         {"ids": [p["id"] for p in pending]})
            for p in pending:
                log.info("PUSH simulado -> %s: %s", (p["push_token"] or "")[:18], p["body"])
            return {"enviados": len(pending), "errores": 0, "simulado": True}
        msgs = [{"to": p["push_token"], "title": p["title"], "body": p["body"], "data": p["data"],
                 "sound": "default", "priority": "high"} for p in pending]
        try:
            resp = httpx.post(s.expo_push_url, json=msgs, timeout=20,
                              headers={"Accept": "application/json", "User-Agent": s.http_user_agent})
            resp.raise_for_status()
            tickets = resp.json().get("data", [])
        except Exception as exc:  # noqa: BLE001
            conn.execute(text("UPDATE push_outbox SET attempts = attempts + 1, last_error=:e WHERE id = ANY(:ids)"),
                         {"e": str(exc)[:500], "ids": [p["id"] for p in pending]})
            return {"enviados": 0, "errores": len(pending)}
        for p, t in zip(pending, tickets):
            if t.get("status") == "ok":
                sent += 1
                conn.execute(text("UPDATE push_outbox SET status='enviado', sent_at=now() WHERE id=:id"), {"id": p["id"]})
            else:
                failed += 1
                conn.execute(text("""UPDATE push_outbox SET attempts=attempts+1, last_error=:e,
                                     status = CASE WHEN attempts >= 4 THEN 'error' ELSE status END WHERE id=:id"""),
                             {"id": p["id"], "e": str(t.get("message"))[:500]})
    return {"enviados": sent, "errores": failed}

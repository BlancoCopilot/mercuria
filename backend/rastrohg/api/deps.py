"""Dependencias: conexión con transacción, usuario (JWT), dispositivo anónimo, límites."""
from __future__ import annotations

import hashlib
from typing import Annotated, Callable

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Connection, text

from ..db import engine, one
from ..settings import get_settings
from ..worker.queue import redis_conn
from .security import decode_token, hash_device_token


class Db:
    """Conexión + acciones a ejecutar DESPUÉS del commit.

    Encolar un recálculo antes del commit sería un error: el worker podría leer la
    base antes de que existan los datos nuevos. Por eso se registra con after_commit.
    """

    def __init__(self, conn: Connection):
        self.conn = conn
        self._after: list[tuple[Callable, tuple]] = []

    def after_commit(self, fn: Callable, *args) -> None:
        self._after.append((fn, args))


def get_db():
    with engine().connect() as conn:
        trans = conn.begin()
        db = Db(conn)
        try:
            yield db
            trans.commit()
        except BaseException:
            trans.rollback()
            raise
    for fn, args in db._after:
        fn(*args)


DbDep = Annotated[Db, Depends(get_db)]
bearer = HTTPBearer(auto_error=False)


def current_user(db: DbDep, cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if cred is None:
        raise HTTPException(401, "Falta el token (Authorization: Bearer ...)")
    try:
        claims = decode_token(cred.credentials)
    except Exception:  # noqa: BLE001
        raise HTTPException(401, "Token inválido o vencido")
    u = one(db.conn, "SELECT id, email, name, role, org, lab_id, settlement_id FROM app_user WHERE id=:id AND active",
            id=int(claims["sub"]))
    if not u:
        raise HTTPException(401, "Usuario inactivo")
    return u


def require(*roles: str):
    def dep(user: Annotated[dict, Depends(current_user)]) -> dict:
        if user["role"] not in roles and user["role"] != "admin":
            raise HTTPException(403, f"Requiere rol: {', '.join(roles)}")
        return user
    return dep


def current_device(db: DbDep, x_device_token: str | None = Header(default=None)) -> dict:
    if not x_device_token:
        raise HTTPException(401, "Falta X-Device-Token (registre el dispositivo en POST /v1/devices)")
    d = one(db.conn, "SELECT id, banned, lang FROM device WHERE token_hash = :h", h=hash_device_token(x_device_token))
    if not d:
        raise HTTPException(401, "Dispositivo no registrado")
    if d["banned"]:
        raise HTTPException(403, "Dispositivo bloqueado")
    db.conn.execute(text("UPDATE device SET last_seen = now() WHERE id = :id"), {"id": d["id"]})
    return d


def optional_device(db: DbDep, x_device_token: str | None = Header(default=None)) -> dict | None:
    if not x_device_token:
        return None
    return one(db.conn, "SELECT id, lang FROM device WHERE token_hash = :h", h=hash_device_token(x_device_token))


def rate_limit(key: str, limit: int, window_s: int = 3600, msg: str = "Demasiados envíos. Intenta {cuando}.") -> None:
    """Ventana fija por clave. `msg` puede usar {cuando} ("en 12 minutos")."""
    r = redis_conn()
    k = f"rastrohg:rl:{key}"
    n = r.incr(k)
    if n == 1:
        r.expire(k, window_s)
    if n > limit:
        ttl = r.ttl(k)
        if ttl is None or ttl < 0:          # clave sin vencimiento (no debería pasar): que no quede bloqueada para siempre
            r.expire(k, window_s)
            ttl = window_s
        mins = max(1, -(-ttl // 60))
        cuando = "en 1 minuto" if mins == 1 else f"en {mins} minutos"
        raise HTTPException(429, msg.format(cuando=cuando), headers={"Retry-After": str(ttl)})


def client_ip_hash(request: Request) -> str:
    """La IP solo se usa, hasheada y de forma transitoria, para limitar registros. No se guarda."""
    h = get_settings().ip_header
    ip = (request.headers.get(h) if h else None) \
        or request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0]
    ip = ip.strip()
    return hashlib.sha256((get_settings().jwt_secret + ip).encode()).hexdigest()[:16]

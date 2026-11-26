"""Acceso a PostgreSQL/PostGIS con SQLAlchemy Core y SQL explícito.

Decisión: el esquema vive en db/init/*.sql y las consultas son SQL a la vista.
Con PostGIS casi toda la lógica espacial es SQL (ST_Intersects, KNN <->), y un ORM
solo la escondería.
"""
from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Iterator

from sqlalchemy import Connection, create_engine, text
from sqlalchemy.engine import Engine

from .settings import get_settings


@lru_cache
def engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=5, max_overflow=5)


@contextmanager
def tx() -> Iterator[Connection]:
    with engine().begin() as conn:
        yield conn


def rows(conn: Connection, sql: str, **params: Any) -> list[dict]:
    return [dict(r._mapping) for r in conn.execute(text(sql), params)]


def one(conn: Connection, sql: str, **params: Any) -> dict | None:
    r = conn.execute(text(sql), params).first()
    return dict(r._mapping) if r else None


def scalar(conn: Connection, sql: str, **params: Any) -> Any:
    return conn.execute(text(sql), params).scalar()


def execute(conn: Connection, sql: str, **params: Any) -> None:
    conn.execute(text(sql), params)

"""Contraseñas (scrypt de la librería estándar), JWT para personal y tokens de dispositivo."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from ..settings import get_settings


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(h).decode()


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, salt_b64, h_b64 = stored.split("$")
    except ValueError:
        return False
    h = hashlib.scrypt(pw.encode(), salt=base64.b64decode(salt_b64), n=2**14, r=8, p=1)
    return hmac.compare_digest(h, base64.b64decode(h_b64))


def create_token(user_id: int, role: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "role": role, "iat": now, "exp": now + timedelta(hours=s.jwt_hours)},
                      s.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])


def new_device_token() -> tuple[str, str]:
    """(token para el teléfono, hash para la base). El token en claro nunca se guarda."""
    tok = secrets.token_urlsafe(32)
    return tok, hash_device_token(tok)


def hash_device_token(tok: str) -> str:
    return hashlib.sha256(tok.encode()).hexdigest()

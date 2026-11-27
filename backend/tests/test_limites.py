"""Límites de uso: IP real detrás de Cloudflare y mensaje con el tiempo que falta (sin Redis real)."""
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from rastrohg.api import deps


def _req(headers: dict[str, str], host: str = "172.27.0.1") -> Request:
    return Request({"type": "http", "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
                    "client": (host, 0)})


class _S:
    def __init__(self, ip_header=""):
        self.ip_header, self.jwt_secret = ip_header, "x"


def test_ip_real_detras_de_cloudflare(monkeypatch):
    monkeypatch.setattr(deps, "get_settings", lambda: _S("cf-connecting-ip"))
    tunel = {"x-forwarded-for": "172.27.0.1"}        # lo que deja Caddy: la IP del túnel, igual para todos
    a = deps.client_ip_hash(_req({**tunel, "cf-connecting-ip": "200.87.1.1"}))
    b = deps.client_ip_hash(_req({**tunel, "cf-connecting-ip": "190.129.2.2"}))
    assert a != b                                     # dos personas = dos contadores


def test_sin_cabecera_configurada_no_se_confia(monkeypatch):
    monkeypatch.setattr(deps, "get_settings", lambda: _S(""))
    a = deps.client_ip_hash(_req({"x-forwarded-for": "10.0.0.1", "cf-connecting-ip": "1.1.1.1"}))
    b = deps.client_ip_hash(_req({"x-forwarded-for": "10.0.0.1", "cf-connecting-ip": "2.2.2.2"}))
    assert a == b                                     # en local, CF-Connecting-IP se ignora (se podría falsificar)


class _Redis:
    def __init__(self):
        self.d, self.t = {}, {}
    def incr(self, k):
        self.d[k] = self.d.get(k, 0) + 1
        return self.d[k]
    def expire(self, k, s):
        self.t[k] = s
    def ttl(self, k):
        return self.t.get(k, -1)


def test_mensaje_dice_cuanto_falta(monkeypatch):
    r = _Redis()
    monkeypatch.setattr(deps, "redis_conn", lambda: r)
    for _ in range(2):
        deps.rate_limit("voz:a", 2, 600, msg="Vuelve a llamar {cuando}.")
    with pytest.raises(HTTPException) as e:
        deps.rate_limit("voz:a", 2, 600, msg="Vuelve a llamar {cuando}.")
    assert e.value.status_code == 429
    assert e.value.detail == "Vuelve a llamar en 10 minutos."
    assert e.value.headers["Retry-After"] == "600"

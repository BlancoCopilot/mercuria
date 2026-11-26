"""Integración API + base + motor, en una base AISLADA (rastrohg_test).

Ejecutar con la base del compose arriba:
    RASTROHG_TEST_PG=postgresql://rastrohg:<pass>@localhost:5433 uv run pytest tests/test_integration.py -v
Los recálculos se ejecutan en el mismo proceso (no se usa el worker compartido).
"""
from __future__ import annotations

import io
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

PG = os.environ.get("RASTROHG_TEST_PG")
pytestmark = pytest.mark.skipif(not PG, reason="definir RASTROHG_TEST_PG para la prueba de integración")
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    import psycopg

    with psycopg.connect(PG + "/postgres", autocommit=True) as c:
        c.execute("DROP DATABASE IF EXISTS rastrohg_test WITH (FORCE)")
        c.execute("CREATE DATABASE rastrohg_test")
    with psycopg.connect(PG + "/rastrohg_test", autocommit=True) as c:
        for f in sorted((ROOT / "db" / "init").glob("*.sql")):
            c.execute(f.read_text())

    os.environ["DATABASE_URL"] = PG.replace("postgresql://", "postgresql+psycopg://") + "/rastrohg_test"
    os.environ["UPLOAD_DIR"] = str(tmp_path_factory.mktemp("uploads"))
    os.environ["JWT_SECRET"] = "x" * 40
    from rastrohg import db, settings
    settings.get_settings.cache_clear()
    db.engine.cache_clear()

    from rastrohg.worker import pipeline

    log: list[dict] = []

    def recompute_now(tipo, ref=None):
        res = pipeline.run_recompute([{"tipo": tipo, "ref": ref}])
        log.append(res)
        if res.get("estado") == "nueva_version":
            pipeline.run_sampling("agua")
        return "inline"

    from rastrohg.api import deps
    from rastrohg.api.routers import admin, auth, devices, measurements, reports
    mp = pytest.MonkeyPatch()
    for mod in (devices, measurements, reports, admin):
        mp.setattr(mod, "request_recompute", recompute_now)
    for mod in (deps, devices, auth):
        mp.setattr(mod, "rate_limit", lambda *a, **k: None)

    from fastapi.testclient import TestClient
    from rastrohg.api.main import app as fastapi_app
    from rastrohg import synthetic

    synthetic.seed()
    log.append(pipeline.run_recompute([{"tipo": "inicial_sintetico"}]))
    yield TestClient(fastapi_app), log
    mp.undo()


def _login(client, role):
    from rastrohg.synthetic import DEMO_PASSWORD
    r = client.post("/v1/auth/login", json={"email": f"{role}@demo.rastrohg", "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _downstream(reach_id):
    from rastrohg.db import tx
    from rastrohg.worker.pipeline import load_network
    with tx() as c:
        net = load_network(c)
    return {r for r, _ in net.downstream(reach_id)}


def _changed_reaches(client, since):
    out = set()
    for m in ("agua", "sedimento", "pez"):
        out |= {f["properties"]["hyriv_id"] for f in client.get("/v1/map/rivers", params={"matrix": m, "since": since}).json()["features"]}
    return out


def test_mina_nueva_cambia_solo_rio_abajo_y_avisa(app):
    client, log = app
    from rastrohg.synthetic import demo_new_mine_geojson
    admin = _login(client, "admin")
    com = {x["name"]: x for x in client.get("/v1/communities", params={"q": "sintética"}).json()}
    dev = client.post("/v1/devices", json={"platform": "android"}).json()
    phone = {"X-Device-Token": dev["device_token"]}
    client.put("/v1/devices/me", headers=phone, json={
        "push_token": "ExponentPushToken[test]",
        "subscribe_settlements": [com["Comunidad D (sintética)"]["id"]]}).raise_for_status()

    v0 = client.get("/v1/map/version").json()["version"]
    r = client.post("/v1/admin/detections", headers=admin,
                    json={"source": "amw", "is_synthetic": True, "geojson": demo_new_mine_geojson()})
    assert r.status_code == 200, r.text
    site_id = r.json()["sitios_nuevos"][0]
    assert log[-1]["estado"] == "nueva_version"
    assert log[-1]["modelos"]["agua"]["recalibrado"] is False

    site = next(f for f in client.get("/v1/map/sites").json()["features"] if f["properties"]["id"] == site_id)
    p = site["properties"]
    assert p["legal_status"] == "sin_concesion"
    assert p["hg_total_p05"] < p["hg_total_p50"] < p["hg_total_p95"]

    from rastrohg.db import one, tx
    with tx() as c:
        reach = one(c, "SELECT reach_id FROM mining_site WHERE id=:i", i=site_id)["reach_id"]
    changed = _changed_reaches(client, v0)
    assert changed and changed <= _downstream(reach), changed - _downstream(reach)

    ficha = client.get(f"/v1/communities/{com['Comunidad D (sintética)']['id']}/card", params={"lang": "qu"}).json()
    assert ficha["frases"] and all(f["traduccion_pendiente"] for f in ficha["frases"])
    outbox = client.get("/v1/admin/outbox", headers=admin).json()
    print(f"\nnivel D: {ficha['nivel']} | alertas: {log[-1]['alertas']} | push: {[o['body'] for o in outbox]}")
    # La Comunidad D está justo río abajo de la mina: pasa de "medio" a "alto" y su teléfono recibe el aviso
    assert ficha["nivel"] == "alto"
    assert any(o["data"]["nivel"] == "alto" for o in outbox)


def test_sugerencias_de_muestreo(app):
    client, _ = app
    sug = client.get("/v1/sampling/suggestions", headers=_login(client, "autoridad")).json()["sugerencias"]
    assert [s["rank"] for s in sug] == [1, 2, 3]
    assert len({s["reach_id"] for s in sug}) == 3


def test_denuncia_offline_idempotente_y_actualiza_mapa(app):
    client, log = app
    dev = client.post("/v1/devices", json={}).json()
    phone = {"X-Device-Token": dev["device_token"]}
    v0 = client.get("/v1/map/version").json()["version"]
    rep = {"client_uuid": str(uuid.uuid4()), "kind": "mineria", "lat": -15.405, "lon": -68.02, "area_ha": 5,
           "description": "[SINTÉTICO] prueba",
           "created_client_at": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()}
    a = client.post("/v1/sync", headers=phone, json={"since_version": v0, "reports": [rep]}).json()
    b = client.post("/v1/sync", headers=phone, json={"since_version": v0, "reports": [rep]}).json()
    assert a["reports"]["aceptadas"] == [rep["client_uuid"]]
    assert b["reports"]["duplicadas"] == [rep["client_uuid"]]
    assert log[-1]["estado"] == "nueva_version"
    from rastrohg.db import one, tx
    with tx() as c:
        s = one(c, "SELECT s.reach_id, s.confianza FROM report r JOIN mining_site s ON s.id=r.site_id WHERE r.client_uuid=:u",
                u=rep["client_uuid"])
    assert s["confianza"] == pytest.approx(0.2)
    with tx() as c:
        assert one(c, "SELECT is_synthetic FROM report WHERE client_uuid=:u", u=rep["client_uuid"])["is_synthetic"]
    assert _changed_reaches(client, v0) <= _downstream(s["reach_id"])
    # En el mapa público la denuncia aparece como celda, no como polígono exacto
    feats = client.get("/v1/map/sites").json()["features"]
    assert any(f["properties"]["origin"] == "denuncia" and "h3" in f["properties"] for f in feats)


def test_rechazo_de_denuncia_descarta_sitio(app):
    client, log = app
    lider = _login(client, "lider")
    pend = client.get("/v1/reports", headers=lider).json()
    assert pend and "lat" in pend[0]   # el líder sí ve la ubicación exacta
    r = client.post(f"/v1/reports/{pend[0]['id']}/review", headers=lider, json={"decision": "rechazada"})
    assert r.status_code == 200
    assert log[-1]["estado"] in ("nueva_version", "sin_cambios")


def test_csv_laboratorio_recalibra(app):
    client, log = app
    lab = _login(client, "laboratorio")
    tramo = client.get("/v1/map/rivers", params={"matrix": "agua"}).json()["features"][0]
    lon, lat = tramo["geometry"]["coordinates"][0]
    header = client.get("/v1/measurements/template.csv").text.splitlines()[0]
    csv = header.replace(",", ";") + f"\nagua;0,35;ug/L;{lat};{lon};2026-10-02;laboratorio;CV-AAS;;no;;total;si;húmeda\n"
    r = client.post("/v1/measurements/csv", headers=lab, files={"file": ("r.csv", csv.encode(), "text/csv")})
    assert r.status_code == 200, r.text
    assert r.json()["errores"] == [] and len(r.json()["validas"]) == 1, r.json()
    from rastrohg.db import one, tx
    with tx() as c:
        assert one(c, "SELECT season FROM measurement WHERE id = CAST(:i AS uuid)",
                   i=r.json()["validas"][0]["id"])["season"] == "humeda"
    assert log[-1]["modelos"]["agua"]["recalibrado"] is True
    malo = "matriz,valor,unidad,lat,lon\nagua,5,mg/kg,-15.4,-68\n"
    r = client.post("/v1/measurements/csv", headers=lab, files={"file": ("m.csv", malo.encode(), "text/csv")})
    assert r.json()["errores"] and "unidad" in r.json()["errores"][0]["error"]
    assert client.post("/v1/measurements/csv", files={"file": ("m.csv", b"x", "text/csv")}).status_code == 401


def test_salud_consentimiento_triaje_y_privacidad(app):
    client, _ = app
    prom = _login(client, "promotor")
    com = client.get("/v1/communities", params={"q": "Comunidad D"}).json()[0]
    now = datetime.now(timezone.utc).isoformat()
    base = {"client_uuid": str(uuid.uuid4()), "settlement_id": com["id"], "consent_at": now, "age_group": "15-49",
            "pregnant": True, "symptoms": ["hormigueo"], "created_client_at": now}
    assert client.post("/v1/health/cases", headers=prom, json={**base, "consent_given": False}).status_code == 422
    caso = client.post("/v1/health/cases", headers=prom, json={**base, "consent_given": True}).json()
    assert caso["triage"] == "prioritario"
    ref = client.post(f"/v1/health/cases/{caso['id']}/referrals", headers=prom, json={}).json()
    assert len(ref["recordatorios"]) == 3
    # la autoridad no ve casos individuales, y el agregado se oculta con < 5 casos
    aut = _login(client, "autoridad")
    assert client.get("/v1/health/cases", headers=aut).status_code == 403
    assert client.get("/v1/health/aggregates", headers=aut).json() == []


def test_foto_sin_exif(app):
    client, _ = app
    from PIL import Image
    dev = client.post("/v1/devices", json={}).json()
    phone = {"X-Device-Token": dev["device_token"]}
    cu = str(uuid.uuid4())
    client.post("/v1/sync", headers=phone, json={"reports": [{
        "client_uuid": cu, "kind": "agua_turbia", "lat": -15.4, "lon": -68.0,
        "created_client_at": datetime.now(timezone.utc).isoformat()}]}).raise_for_status()
    img = Image.new("RGB", (64, 64), "brown")
    exif = Image.Exif()
    exif[0x8825] = {2: (15.0, 24.0, 0.0)}   # GPSInfo
    exif[0x0110] = "TelefonoX"              # modelo
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    assert Image.open(io.BytesIO(buf.getvalue())).getexif()
    r = client.post(f"/v1/reports/{cu}/photo", headers=phone, files={"file": ("f.jpg", buf.getvalue(), "image/jpeg")})
    assert r.status_code == 200, r.text
    saved = next(Path(os.environ["UPLOAD_DIR"], "reports").glob("*.jpg"))
    assert not Image.open(saved).getexif()
    assert "exif" not in Image.open(saved).info


def test_panel(app):
    client, _ = app
    aut = _login(client, "autoridad")
    s = client.get("/v1/dashboard/summary", headers=aut).json()
    assert s["mediciones_sinteticas"] > 0
    pr = client.get("/v1/dashboard/priorities", headers=aut).json()
    assert "campanas_salud" in pr and "recuperacion_ecosistema" in pr
    ind = client.get("/v1/dashboard/indicators", headers=aut, params={"months": 3}).json()
    assert len(ind) == 3 and ind[-1]["minas_nuevas"] >= 1

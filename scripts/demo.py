"""Guion de la demo del hackathon (6 pasos) contra la API en marcha.

Requisitos: `docker compose up -d` y `docker compose exec api rastrohg seed-synthetic`.
Uso (desde backend/):  uv run python ../scripts/demo.py [--api http://localhost:8000]

TODOS los datos de esta demo son SINTÉTICOS y están marcados como tales.
"""
from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx

from rastrohg.synthetic import DEMO_PASSWORD, demo_new_mine_geojson


def title(t: str) -> None:
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


def show(x) -> None:
    print(json.dumps(x, indent=2, ensure_ascii=False, default=str))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    api = ap.parse_args().api
    c = httpx.Client(base_url=api, timeout=60)

    def login(role: str) -> dict:
        r = c.post("/v1/auth/login", json={"email": f"{role}@demo.rastrohg", "password": DEMO_PASSWORD})
        r.raise_for_status()
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    admin, autoridad, promotor = login("admin"), login("autoridad"), login("promotor")

    def version() -> int:
        return c.get("/v1/map/version").json()["version"]

    def wait_version(v0: int, timeout: float = 60) -> int:
        t0 = time.time()
        while time.time() - t0 < timeout:
            v = version()
            if v > v0:
                return v
            time.sleep(0.5)
        raise SystemExit("el recálculo no terminó a tiempo (revise `docker compose logs worker`)")

    comunidades = {x["name"]: x for x in c.get("/v1/communities", params={"q": "sintética"}).json()}
    com_c, com_d = comunidades["Comunidad C (sintética)"], comunidades["Comunidad D (sintética)"]

    # Un teléfono de la Comunidad D se registra (anónimo) y se suscribe a su zona.
    dev = c.post("/v1/devices", json={"platform": "android", "lang": "qu"}).json()
    phone = {"X-Device-Token": dev["device_token"]}
    c.put("/v1/devices/me", headers=phone, json={
        "push_token": "ExponentPushToken[demo-comunidad-d]",
        "subscribe_settlements": [com_c["id"], com_d["id"]]}).raise_for_status()
    v_phone = version()
    antes = {n: c.get(f"/v1/communities/{x['id']}/card").json()["nivel"] for n, x in
             (("C", com_c), ("D", com_d))}

    # ---------------------------------------------------------------- 1
    title("1. Aparece una mina nueva detectada por satélite (Tributario Este)")
    v0 = version()
    r = c.post("/v1/admin/detections", headers=admin, json={
        "source": "amw", "is_synthetic": True, "geojson": demo_new_mine_geojson()})
    show(r.json())
    if not r.json()["sitios_cambiados"]:
        raise SystemExit("La mina de la demo ya estaba cargada. Reinicie los datos sintéticos:\n"
                         "  docker compose exec api rastrohg purge-synthetic && "
                         "docker compose exec api rastrohg seed-synthetic")
    new_site = r.json()["sitios_cambiados"][0]

    # ---------------------------------------------------------------- 2
    title("2. Estima el mercurio liberado y recalcula el riesgo río abajo")
    v1 = wait_version(v0)
    site = next(f for f in c.get("/v1/map/sites").json()["features"] if f["properties"]["id"] == new_site)
    p = site["properties"]
    print(f"Sitio {new_site}: {p['area_ha']} ha, estado legal: {p['legal_status']}")
    print(f"Hg liberado: {p['hg_total_p50']:.1f} kg/año (rango p05–p95: {p['hg_total_p05']:.1f}–{p['hg_total_p95']:.1f})")
    ver = c.get("/v1/admin/versions", headers=admin, params={"limit": 1}).json()[0]
    print(f"Versión del mapa {v1}: {ver['reaches_changed']} tramos y {ver['cells_changed']} celdas cambiaron")
    agua = c.get("/v1/map/rivers", params={"matrix": "agua", "since": v0}).json()["features"]
    print("Tramos de agua que cambiaron (todos río abajo de la mina):",
          sorted(f["properties"]["hyriv_id"] for f in agua))

    # ---------------------------------------------------------------- 3
    title("3. Le avisa a la comunidad, que recibe su ficha (con audio por frases)")
    print("Push generado:")
    show([{k: o[k] for k in ("body", "status", "last_error")} for o in
          c.get("/v1/admin/outbox", headers=admin, params={"limit": 3}).json()])
    sync0 = c.post("/v1/sync", headers=phone, json={"since_version": v_phone}).json()
    print(f"El teléfono tenía la versión {v_phone}; baja solo {len(sync0['mapa']['celdas_cambiadas'])} celdas.")
    despues = {n: c.get(f"/v1/communities/{x['id']}/card").json()["nivel"] for n, x in (("C", com_c), ("D", com_d))}
    print(f"Nivel antes -> después: C {antes['C']} -> {despues['C']}, D {antes['D']} -> {despues['D']}")
    ficha = c.get(f"/v1/communities/{com_d['id']}/card", params={"lang": "qu"}, headers=phone).json()
    print(f"Ficha de {ficha['comunidad']['nombre']} (idioma {ficha['idioma']}):")
    for f in ficha["frases"]:
        marca = " [audio quechua pendiente de grabar]" if f["traduccion_pendiente"] else ""
        print("  -", f["texto"] + marca)

    # ---------------------------------------------------------------- 4
    title("4. Sugiere al ministerio los 3 mejores puntos de muestreo")
    time.sleep(2)   # el worker los calcula justo después de la nueva versión
    sug = c.get("/v1/sampling/suggestions", headers=autoridad, params={"matrix": "agua"}).json()
    for s in sug["sugerencias"]:
        print(f"  #{s['rank']} tramo {s['reach_id']} cerca de {s['comunidad_cercana']} "
              f"({s['lat']:.4f}, {s['lon']:.4f}): reduce {s['reduccion_pct']}% de la incertidumbre ponderada")

    # ---------------------------------------------------------------- 5
    title("5. Un promotor de salud registra un caso sospechoso y lo deriva")
    now = datetime.now(timezone.utc)
    caso = c.post("/v1/health/cases", headers=promotor, json={
        "client_uuid": str(uuid.uuid4()), "settlement_id": com_d["id"], "consent_given": True,
        "consent_at": now.isoformat(), "age_group": "15-49", "sex": "f", "pregnant": True,
        "symptoms": ["hormigueo", "temblor"], "exposures": ["pescado_diario"],
        "created_client_at": now.isoformat()}).json()
    print(f"Triaje: {caso['triage']} — {caso['mensaje']} (protocolo validado: {caso['protocolo_validado']})")
    ref = c.post(f"/v1/health/cases/{caso['id']}/referrals", headers=promotor,
                 json={"reason": "embarazo + síntomas neurológicos"}).json()
    print(f"Derivado a: {caso['centro_sugerido']['name']} ({caso['centro_sugerido']['km']} km). "
          f"Recordatorios: {ref['recordatorios']}")

    # ---------------------------------------------------------------- 6
    title("6. Denuncia hecha en modo avión: se sincroniza al volver la señal")
    v2 = version()
    denuncia = {"client_uuid": str(uuid.uuid4()), "kind": "mineria", "description": "[SINTÉTICO] Balsa nueva con motor",
                "lat": -15.405, "lon": -68.02, "area_ha": 5,
                "created_client_at": (now - timedelta(hours=3)).isoformat()}  # hecha hace 3 h sin señal
    s1 = c.post("/v1/sync", headers=phone, json={"since_version": v2, "reports": [denuncia]}).json()
    print("Primer envío:", s1["reports"])
    s2 = c.post("/v1/sync", headers=phone, json={"since_version": v2, "reports": [denuncia]}).json()
    print("Reenvío (se cortó la señal a mitad):", s2["reports"], "-> sin duplicados")
    v3 = wait_version(v2)
    ver = c.get("/v1/admin/versions", headers=admin, params={"limit": 1}).json()[0]
    print(f"Mapa actualizado a la versión {v3}: {ver['reaches_changed']} tramos y {ver['cells_changed']} celdas "
          f"cambiaron de forma apreciable (la denuncia pesa 0,2 frente a 1 del satélite).")
    print("En el mapa público la denuncia aparece como una celda H3, nunca como punto exacto.")

    title("Panel de decisión")
    show(c.get("/v1/dashboard/summary", headers=autoridad).json())


if __name__ == "__main__":
    main()

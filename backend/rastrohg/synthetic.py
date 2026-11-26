"""Cuenca SINTÉTICA para desarrollo y ensayo de la demo.

Todo lo que crea este módulo lleva is_synthetic = true (y nombres que dicen
"sintética"). Sirve para probar el flujo completo antes de cargar HydroRIVERS, censo
y mediciones reales. `rastrohg purge-synthetic` lo borra todo.

Forma: un río principal de 14 tramos (~5 km c/u) que corre al noreste y 4 tributarios.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text

from .api.security import hash_password
from .db import one, tx
from .ingest.base import build_cells
from .ingest.detections import ingest_features
from .services.measurements import insert_measurements

BASE_ID = 9_000_000
STEP = 0.045                       # ~5 km
A = (-68.25, -15.70)               # nacimiento del río principal
DIR = (0.8, 0.6)                   # hacia el noreste
PERP = (-0.6, 0.8)
TRIBS = [  # (nodo de confluencia, lado, tramos, nombre)
    (3, 1, 5, "Tributario Norte (sintético)"),
    (6, -1, 4, "Tributario Sur (sintético)"),
    (9, 1, 6, "Tributario Este (sintético)"),
    (11, -1, 3, "Tributario Chico (sintético)"),
]
DEMO_PASSWORD = "demo-rastrohg-2026"


def _pt(base, d, k):
    return (base[0] + d[0] * STEP * k, base[1] + d[1] * STEP * k)


def _wiggle(p, i):
    return (p[0] + 0.004 * math.sin(i * 1.7), p[1] + 0.004 * math.cos(i * 1.3))


def basin():
    reaches = []   # dict(id, next_down, coords, name)
    main_nodes = [_wiggle(_pt(A, DIR, i), i) for i in range(15)]
    for i in range(14):
        reaches.append({"id": BASE_ID + i, "nd": BASE_ID + i + 1 if i < 13 else 0,
                        "coords": [main_nodes[i], main_nodes[i + 1]], "name": "Río Principal (sintético)"})
    for t, (j, side, m, name) in enumerate(TRIBS):
        junction = main_nodes[j]
        back = (-DIR[0] * 0.5 + side * PERP[0], -DIR[1] * 0.5 + side * PERP[1])
        norm = math.hypot(*back)
        back = (back[0] / norm, back[1] / norm)
        nodes = [_wiggle(_pt(junction, back, m - k), 100 * t + k) for k in range(m)] + [junction]
        for k in range(m):
            rid = BASE_ID + 100 * (t + 1) + k
            nd = BASE_ID + 100 * (t + 1) + k + 1 if k < m - 1 else BASE_ID + j
            reaches.append({"id": rid, "nd": nd, "coords": [nodes[k], nodes[k + 1]], "name": name})
    # áreas de cuenca y caudal
    by_id = {r["id"]: r for r in reaches}
    ups = {}
    for r in reaches:
        ups.setdefault(r["nd"], []).append(r["id"])

    def upland(rid):
        r = by_id[rid]
        if "up" not in r:
            r["len"] = 111.0 * math.dist(*r["coords"])
            r["up"] = 6.0 * r["len"] + sum(upland(u) for u in ups.get(rid, []))
        return r["up"]
    for r in reaches:
        upland(r["id"])
        r["q"] = 0.04 * r["up"]
    return reaches, main_nodes


def _near(p, dlon, dlat):
    return (p[0] + dlon, p[1] + dlat)


def seed() -> dict:
    reaches, main = basin()
    by_id = {r["id"]: r for r in reaches}
    mid = lambda rid: tuple((a + b) / 2 for a, b in zip(*by_id[rid]["coords"]))  # noqa: E731

    with tx() as conn:
        conn.execute(text("""
            INSERT INTO river_reach (hyriv_id, next_down, length_km, upland_skm, dis_av_cms, ord_stra, name, geom, is_synthetic)
            VALUES (:id, :nd, :len, :up, :q, :o, :name, ST_GeomFromText(:wkt, 4326), true)
            ON CONFLICT (hyriv_id) DO NOTHING"""),
            [{**r, "o": 4 if r["id"] < BASE_ID + 100 else 2,
              "wkt": "LINESTRING(" + ",".join(f"{x} {y}" for x, y in r["coords"]) + ")"} for r in reaches])

        villages = [  # (nombre, tramo, pob, niños<5, mujeres 15-49)
            ("Comunidad A (sintética)", BASE_ID + 4, 620, 90, 150),
            ("Comunidad B (sintética)", BASE_ID + 7, 340, 52, 80),
            ("Comunidad C (sintética)", BASE_ID + 10, 1150, 150, 270),
            ("Comunidad D (sintética)", BASE_ID + 302, 210, 35, 50),
            ("Comunidad E (sintética)", BASE_ID + 13, 480, 60, 115),
            ("Comunidad F (sintética)", BASE_ID + 101, 90, 12, 20),
        ]
        for k, (name, rid, pob, ninos, muj) in enumerate(villages):
            x, y = _near(mid(rid), 0.004, -0.003)
            conn.execute(text("""
                INSERT INTO settlement (name, kind, census_code, poblacion, ninos_u5, mujeres_15_49, municipio, geom, source, is_synthetic)
                VALUES (:n, 'village', :c, :p, :ni, :m, 'Municipio Sintético', ST_SetSRID(ST_MakePoint(:x,:y),4326), 'sintetico', true)
                ON CONFLICT (census_code) DO NOTHING"""),
                {"n": name, "c": f"SYN-{k}", "p": pob, "ni": ninos, "m": muj, "x": x, "y": y})
        for name, rid in (("Centro de Salud A (sintético)", BASE_ID + 4), ("Hospital C (sintético)", BASE_ID + 10)):
            x, y = _near(mid(rid), 0.006, -0.004)
            conn.execute(text("""INSERT INTO health_facility (name, level, phone, geom, source, is_synthetic)
                                 VALUES (:n, '1er nivel', '+591 0000000', ST_SetSRID(ST_MakePoint(:x,:y),4326), 'sintetico', true)"""),
                         {"n": name, "x": x, "y": y})
        for kind, rid in (("toma_agua", BASE_ID + 7), ("toma_agua", BASE_ID + 10), ("zona_pesca", BASE_ID + 10),
                          ("zona_pesca", BASE_ID + 12), ("zona_pesca", BASE_ID + 302)):
            x, y = _near(mid(rid), 0.002, -0.001)
            conn.execute(text("""INSERT INTO exposure_feature (kind, geom, source, is_synthetic)
                                 VALUES (:k, ST_SetSRID(ST_MakePoint(:x,:y),4326), 'sintetico', true)"""),
                         {"k": kind, "x": x, "y": y})

        # Concesión que cubre el sitio del Tributario Norte (el del Sur queda sin concesión)
        cx, cy = mid(BASE_ID + 102)
        conn.execute(text("""INSERT INTO concession (code, holder, status, mineral, geom, source)
            VALUES ('SYN-001', 'Cooperativa Sintética', 'vigente', 'oro',
                    ST_Multi(ST_Expand(ST_SetSRID(ST_MakePoint(:x,:y),4326), 0.02)), 'sintetico')"""), {"x": cx, "y": cy})

        cells = build_cells(conn)

        # Sitios mineros "detectados por satélite" (sintéticos)
        feats = [(_rect(_near(mid(BASE_ID + 102), 0.0015, 0.0015), 0.005, 0.004), date(2024, 7, 1), "syn-amw-1"),
                 (_rect(_near(mid(BASE_ID + 201), 0.0015, 0.0015), 0.006, 0.005), date(2025, 7, 1), "syn-amw-2")]
        sites = ingest_features(conn, feats, "amw", is_synthetic=True)

        lab = one(conn, """INSERT INTO lab (name, accredited) VALUES ('Laboratorio Sintético', true)
                           ON CONFLICT (name) DO UPDATE SET accredited = true RETURNING id""")["id"]
        users = {}
        for role in ("admin", "laboratorio", "promotor", "lider", "autoridad"):
            u = one(conn, """INSERT INTO app_user (email, name, role, org, lab_id, password_hash)
                             VALUES (:e, :n, :r, 'Demo', :l, :p) ON CONFLICT (email) DO NOTHING RETURNING id""",
                    e=f"{role}@demo.rastrohg", n=f"Demo {role}", r=role,
                    l=lab if role == "laboratorio" else None, p=hash_password(DEMO_PASSWORD))
            users[role] = u["id"] if u else None

        def m(matrix, value, unit, rid, dx=0.0005, **kw):
            x, y = _near(mid(rid), dx, 0)
            return {"matrix": matrix, "value": value, "unit": unit, "lat": y, "lon": x,
                    "sampled_on": (date.today() - timedelta(days=200)).isoformat(),
                    "source_type": kw.pop("source_type", "publicado"), "is_synthetic": True,
                    "reference": "SINTÉTICO — reemplazar por estudios publicados", **kw}
        meas = insert_measurements(conn, [
            m("agua", 180, "ng/L", BASE_ID + 103),
            m("agua", 45, "ng/L", BASE_ID + 5),
            m("agua", 6, "ng/L", BASE_ID + 1),
            m("agua", 30, "ng/L", BASE_ID + 9, source_type="kit"),
            m("sedimento", 0.9, "mg/kg", BASE_ID + 103),
            m("sedimento", 0.35, "mg/kg", BASE_ID + 6),
            m("sedimento", 0.07, "mg/kg", BASE_ID + 301),
            m("pez", 1.1, "mg/kg", BASE_ID + 5, fish_species="surubi"),
            m("pez", 0.12, "mg/kg", BASE_ID + 8, fish_species="sabalo"),
            m("pez", 0.55, "mg/kg", BASE_ID + 12, fish_species="dorado"),
        ], users.get("laboratorio"), lab)
    return {"tramos": len(reaches), **cells, "sitios": sites["sitios_nuevos"],
            "mediciones": len(meas["validas"]), "en_revision": meas["en_revision"],
            "usuarios": [f"{r}@demo.rastrohg" for r in users], "password": DEMO_PASSWORD}


def _rect(center, w, h):
    from shapely.geometry import box
    return box(center[0] - w / 2, center[1] - h / 2, center[0] + w / 2, center[1] + h / 2)


def demo_new_mine_geojson() -> dict:
    """Polígono para el paso 1 de la demo: mina nueva en el Tributario Este, aguas
    arriba de la Comunidad C y de la toma de agua."""
    reaches, _ = basin()
    by_id = {r["id"]: r for r in reaches}
    c = tuple((a + b) / 2 for a, b in zip(*by_id[BASE_ID + 301]["coords"]))
    poly = _rect(_near(c, 0.0015, 0.0015), 0.012, 0.009)
    return {"type": "FeatureCollection", "features": [{
        "type": "Feature", "geometry": poly.__geo_interface__,
        "properties": {"id": "syn-amw-demo-1", "detected_on": date.today().isoformat()}}]}


def purge() -> dict:
    with tx() as conn:
        out = {}
        for sql, k in [
            ("DELETE FROM measurement WHERE is_synthetic", "mediciones"),
            ("DELETE FROM report WHERE is_synthetic OR site_id IN (SELECT id FROM mining_site WHERE is_synthetic)", "denuncias"),
            ("DELETE FROM mining_detection WHERE is_synthetic", "detecciones"),
            ("DELETE FROM mining_site WHERE is_synthetic", "sitios"),
            ("UPDATE mining_site SET concession_id = NULL WHERE concession_id IN (SELECT id FROM concession WHERE source = 'sintetico')", "_c"),
            ("DELETE FROM concession WHERE source = 'sintetico'", "concesiones"),
            # referencias a centros sintéticos antes de borrar los centros
            ("DELETE FROM referral WHERE facility_id IN (SELECT id FROM health_facility WHERE is_synthetic)", "derivaciones"),
            ("DELETE FROM health_facility WHERE is_synthetic", "centros"),
            ("DELETE FROM exposure_feature WHERE is_synthetic", "exposicion"),
            ("DELETE FROM health_case WHERE settlement_id IN (SELECT id FROM settlement WHERE is_synthetic)", "casos"),
            ("DELETE FROM hair_campaign WHERE settlement_id IN (SELECT id FROM settlement WHERE is_synthetic)", "campanas"),
            ("DELETE FROM fish_survey WHERE settlement_id IN (SELECT id FROM settlement WHERE is_synthetic)", "encuestas_peces"),
            ("DELETE FROM outreach_event WHERE settlement_id IN (SELECT id FROM settlement WHERE is_synthetic)", "actividades"),
            ("UPDATE app_user SET settlement_id = NULL WHERE settlement_id IN (SELECT id FROM settlement WHERE is_synthetic)", "_u"),
            ("DELETE FROM settlement WHERE is_synthetic", "poblados"),
            ("DELETE FROM reach_estimate WHERE reach_id IN (SELECT hyriv_id FROM river_reach WHERE is_synthetic)", "_e"),
            ("DELETE FROM sampling_suggestion WHERE reach_id IN (SELECT hyriv_id FROM river_reach WHERE is_synthetic)", "_s"),
            ("UPDATE mining_site SET reach_id = NULL, snap_distance_m = NULL WHERE reach_id IN (SELECT hyriv_id FROM river_reach WHERE is_synthetic)", "_r"),
            ("UPDATE measurement SET reach_id = NULL WHERE reach_id IN (SELECT hyriv_id FROM river_reach WHERE is_synthetic)", "_m"),
            ("DELETE FROM river_reach WHERE is_synthetic", "tramos"),
        ]:
            out[k] = conn.execute(text(sql)).rowcount
        out = {k: v for k, v in out.items() if not k.startswith("_")}
        # celdas que ya no tocan ningún río ni poblado
        out["celdas_huerfanas"] = conn.execute(text("""
            DELETE FROM h3_cell c WHERE NOT EXISTS (SELECT 1 FROM reach_cell rc WHERE rc.h3 = c.h3)
              AND NOT EXISTS (SELECT 1 FROM settlement s WHERE s.h3 = c.h3)
              AND NOT EXISTS (SELECT 1 FROM exposure_feature e WHERE e.h3 = c.h3)
              AND NOT EXISTS (SELECT 1 FROM cell_risk r WHERE r.h3 = c.h3)""")).rowcount
        out.update(build_cells(conn))
        # los sitios reales que apuntaban a tramos sintéticos se vuelven a conectar
        ids = [r[0] for r in conn.execute(text("SELECT id FROM mining_site WHERE reach_id IS NULL"))]
        if ids:
            from .ingest.detections import finalize_sites
            finalize_sites(conn, ids)
    return out


def now_minus(hours: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

"""Módulo 6: ficha "Mi comunidad".

La ficha se arma con frases cortas identificadas por clave (p. ej. "ficha.nivel.alto").
Cada frase tiene texto y audio por idioma en la tabla `translation`. Decisión: el audio
en aymara, quechua y guaraní lo graban hablantes locales (y lo validan líderes), frase
por frase, en vez de usar síntesis de voz: la calidad de TTS en esos idiomas no es
confiable para mensajes de salud. Como las frases son plantillas, una grabación sirve
para todas las comunidades y el teléfono las guarda para escucharlas sin internet.
"""
from __future__ import annotations

import math

from sqlalchemy import Connection

from ..db import one, rows
from ..engine.fish import fish_advice
from ..engine.params import load_yaml, params

TEXTOS_ES = {
    "ficha.nivel.alto": "En {comunidad} el riesgo por mercurio es ALTO.",
    "ficha.nivel.medio": "En {comunidad} el riesgo por mercurio es MEDIO.",
    "ficha.nivel.bajo": "En {comunidad} el riesgo por mercurio es BAJO.",
    "ficha.nivel.sin_datos": "Todavía no tenemos información de {comunidad}.",
    "ficha.incierto": "Todavía tenemos pocos datos de esta zona: el nivel puede cambiar cuando lleguen muestras.",
    "ficha.peces.comer": "Puede comer: {peces}.",
    "ficha.peces.limitar": "Coma poco (máximo 1 o 2 veces por semana): {peces}.",
    "ficha.peces.evitar": "Mujeres embarazadas y niños, eviten: {peces}.",
    "ficha.accion.amalgama": "No queme amalgama dentro ni cerca de la casa, ni cerca de niños.",
    "ficha.accion.sintomas": "Si tiene temblores, hormigueo en manos o boca, o pierde el equilibrio, vaya al centro de salud.",
    "ficha.accion.agua": "Para tomar y cocinar, prefiera agua de vertiente o de lluvia antes que agua del río.",
    "ficha.accion.pescado_bueno": "El pescado es buen alimento: prefiera los peces que comen plantas o lodo.",
    "ficha.accion.avisar": "Si ve nuevas dragas o balsas mineras, avise con la app (es anónimo).",
    "ficha.centro_salud": "Centro de salud más cercano: {centro}, a {km} kilómetros.",
}

ACCIONES = {
    "alto": ["ficha.accion.amalgama", "ficha.accion.sintomas", "ficha.accion.agua", "ficha.accion.avisar"],
    "medio": ["ficha.accion.amalgama", "ficha.accion.sintomas", "ficha.accion.pescado_bueno", "ficha.accion.avisar"],
    "bajo": ["ficha.accion.pescado_bueno", "ficha.accion.avisar"],
    "sin_datos": ["ficha.accion.amalgama", "ficha.accion.avisar"],
}


def _phrases(conn: Connection, keys: list[str], lang: str) -> dict[str, dict]:
    tr = {r["key"]: r for r in rows(conn, """
        SELECT key, text, audio_path FROM translation
        WHERE key = ANY(:k) AND lang = :l AND status = 'validada'""", k=keys, l=lang)}
    out = {}
    for k in keys:
        t = tr.get(k)
        out[k] = {"texto": t["text"] if t else TEXTOS_ES[k],
                  "audio_url": f"/media/audio/{t['audio_path']}" if t and t["audio_path"] else None,
                  "traduccion_pendiente": lang != "es" and t is None}
    return out


def community_card(conn: Connection, settlement_id: int, lang: str = "es") -> dict | None:
    cfg = params()
    s = one(conn, """SELECT id, name, h3, poblacion, is_synthetic, ST_Y(geom) AS lat, ST_X(geom) AS lon
                     FROM settlement WHERE id = :id""", id=settlement_id)
    if not s:
        return None
    cell = one(conn, "SELECT * FROM cell_risk_current WHERE h3 = :h", h=s["h3"])
    nivel = cell["risk_class"] if cell else "sin_datos"

    # Pez de referencia: el tramo que manda en la celda o, si no hay, el más cercano.
    rid = (cell or {}).get("drivers", {}).get("pez", {}).get("reach_id") if cell else None
    est = one(conn, "SELECT reach_id, log_mu, log_sd FROM reach_estimate WHERE matrix='pez' AND reach_id=:r", r=rid) if rid else None
    if est is None:
        est = one(conn, """SELECT e.reach_id, e.log_mu, e.log_sd FROM reach_estimate e JOIN river_reach r ON r.hyriv_id = e.reach_id
                           WHERE e.matrix = 'pez' ORDER BY r.geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) LIMIT 1""",
                  lon=s["lon"], lat=s["lat"])
    especies = load_yaml("fish_species.yaml")["especies"]
    peces = fish_advice(est["log_mu"], est["log_sd"], especies, cfg) if est else []

    centro = one(conn, """
        SELECT id, name, phone, level,
               ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) / 1000 AS km
        FROM health_facility ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) LIMIT 1""",
        lon=s["lon"], lat=s["lat"])

    keys = [f"ficha.nivel.{nivel}"]
    if cell and cell["palida"]:
        keys.append("ficha.incierto")
    grupos = {c: [p["nombre"] for p in peces if p["consejo"] == c] for c in ("comer", "limitar", "evitar")}
    keys += [f"ficha.peces.{c}" for c in ("comer", "limitar", "evitar") if grupos[c]]
    keys += ACCIONES[nivel]
    if centro:
        keys.append("ficha.centro_salud")
    ph = _phrases(conn, keys, lang)
    valores = {"comunidad": s["name"], "centro": centro["name"] if centro else "",
               "km": f"{centro['km']:.0f}" if centro else ""}
    frases = []
    for k in keys:
        v = dict(valores)
        if k.startswith("ficha.peces."):
            v["peces"] = ", ".join(grupos[k.rsplit(".", 1)[1]])
        frases.append({"clave": k, "texto": ph[k]["texto"].format(**v), "audio_url": ph[k]["audio_url"],
                       "traduccion_pendiente": ph[k]["traduccion_pendiente"]})

    return {
        "comunidad": {"id": s["id"], "nombre": s["name"], "h3": s["h3"], "poblacion": s["poblacion"],
                      "sintetico": s["is_synthetic"]},
        "idioma": lang,
        "nivel": nivel,
        "confianza": cell["confidence"] if cell else None,
        "palida": cell["palida"] if cell else True,
        "version_mapa": cell["version_id"] if cell else None,
        "frases": frases,
        "peces": peces,
        "centro_salud": centro and {k: (round(v, 1) if k == "km" else v) for k, v in centro.items()},
        "aviso": "Estimación con incertidumbre. Parámetros en revisión con autoridades de salud.",
    }


def triage(protocol: dict, symptoms: list[str], alarm: list[str], exposures: list[str],
           pregnant: bool, age_group: str) -> str:
    if alarm:
        return "urgente"
    pts = {x["codigo"]: x["puntos"] for x in protocol["sintomas"] + protocol["exposicion"]}
    score = sum(pts.get(c, 0) for c in symptoms + exposures)
    reglas = protocol["reglas"]
    if score >= reglas["prioritario_si_puntos_desde"]:
        return "prioritario"
    if reglas["prioritario_si_embarazo_o_menor5_con_sintomas"] and symptoms and (pregnant or age_group == "0-4"):
        return "prioritario"
    return "rutina"


def _finite(x: float) -> float | None:
    return x if x is not None and math.isfinite(x) else None

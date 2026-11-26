"""Módulo 4: carga de resultados (formulario, CSV de laboratorio, kits, publicados).

* Todo se convierte a la unidad canónica de su matriz y se guarda también el original.
* Peso por fuente (params.yaml > confianza_fuente): laboratorio/publicado 1, kit 0,5.
* Se conecta al tramo de río más cercano (≤ 2 km). Si no hay tramo, o si es pez sin
  especie conocida, queda "en_revision" y no entra al modelo hasta que alguien lo revise.
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import date

from sqlalchemy import Connection

from ..db import one
from ..engine.params import load_yaml, params
from ..engine.units import CANONICA, to_canonical
from ..ingest.base import snap_point

CSV_COLUMNS = {
    "matriz": "matrix", "valor": "value", "unidad": "unit", "lat": "lat", "lon": "lon",
    "fecha_muestreo": "sampled_on", "tipo_fuente": "source_type", "metodo": "method",
    "especie_pez": "fish_species", "bajo_ld": "below_dl", "referencia": "reference",
    "especie_hg": "hg_species", "sintetico": "is_synthetic",
    # opcionales
    "estacion_climatica": "season", "tramo_id": "reach_override", "nota": "notes",
    "estacion": "station", "precision_ubicacion": "location_precision",
}
SEASONS = {"humeda": "humeda", "húmeda": "humeda", "lluvia": "humeda", "lluviosa": "humeda", "wet": "humeda",
           "crecida": "humeda", "seca": "seca", "estiaje": "seca", "dry": "seca"}
TRUE = {"si", "sí", "true", "1", "x", "yes"}


def species_groups() -> dict[str, str]:
    return {e["codigo"]: e["grupo"] for e in load_yaml("fish_species.yaml")["especies"]}


def parse_csv(content: bytes) -> list[dict]:
    text = content.decode("utf-8-sig")
    dialect = csv.Sniffer().sniff(text.splitlines()[0], delimiters=",;\t")
    out = []
    for row in csv.DictReader(io.StringIO(text), dialect=dialect):
        item = {CSV_COLUMNS[k.strip().lower()]: (v.strip() if v else None)
                for k, v in row.items() if k and k.strip().lower() in CSV_COLUMNS}
        out.append(item)
    return out


def _clean(item: dict) -> dict:
    it = dict(item)
    it["matrix"] = (it.get("matrix") or "").strip().lower()
    if it["matrix"] not in CANONICA:
        raise ValueError(f"matriz '{it['matrix']}' no válida (agua, sedimento, pez)")
    it["value"] = float(str(it["value"]).replace(",", "."))
    if it["value"] <= 0:
        raise ValueError("el valor debe ser > 0 (si está bajo el límite de detección, ponga el LD y bajo_ld=si)")
    it["lat"], it["lon"] = float(it["lat"]), float(it["lon"])
    it["source_type"] = (it.get("source_type") or "laboratorio").lower()
    if it["source_type"] not in ("laboratorio", "publicado", "kit"):
        raise ValueError("tipo_fuente debe ser laboratorio, publicado o kit")
    it["below_dl"] = str(it.get("below_dl") or "").lower() in TRUE or it.get("below_dl") is True
    it["is_synthetic"] = str(it.get("is_synthetic") or "").lower() in TRUE or it.get("is_synthetic") is True
    it["hg_species"] = (it.get("hg_species") or "total").lower()
    sd = it.get("sampled_on")
    it["sampled_on"] = date.fromisoformat(str(sd)) if sd else None
    it["season"] = SEASONS.get(str(it.get("season") or "").strip().lower())   # otro valor => desconocida
    ro = it.get("reach_override")
    it["reach_override"] = int(ro) if ro not in (None, "") else None
    notes = [f"{k}: {it[k]}" for k in ("station", "location_precision", "notes") if it.get(k)]
    it["notes"] = " | ".join(notes) or None
    return it


def insert_measurements(conn: Connection, items: list[dict], uploaded_by: int | None,
                        lab_id: int | None) -> dict:
    cfg = params()
    groups = species_groups()
    batch = uuid.uuid4()
    ok, errors, revision = [], [], []
    for n, raw in enumerate(items, start=1):
        try:
            it = _clean(raw)
            value = to_canonical(it["matrix"], it["value"], it.get("unit") or CANONICA[it["matrix"]])
        except (ValueError, KeyError, TypeError) as exc:
            errors.append({"fila": n, "error": str(exc)})
            continue
        forced = it["reach_override"] is not None
        if forced:
            r = one(conn, """SELECT hyriv_id, ST_Distance(geom::geography,
                                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS d
                             FROM river_reach WHERE hyriv_id = :r""", r=it["reach_override"], lon=it["lon"], lat=it["lat"])
            if r is None:
                errors.append({"fila": n, "error": f"tramo_id {it['reach_override']} no existe en la red"})
                continue
            reach_id, dist = int(r["hyriv_id"]), float(r["d"])
        else:
            reach_id, dist = snap_point(conn, it["lon"], it["lat"])
        group = groups.get((it.get("fish_species") or "").lower()) if it["matrix"] == "pez" else None
        status = "valido"
        motivo = None
        if reach_id is None:
            status, motivo = "en_revision", "a más de 2 km de un río de la red"
        elif it["matrix"] == "pez" and group is None:
            status, motivo = "en_revision", "especie de pez desconocida (ver config/fish_species.yaml)"
        row = one(conn, """
            INSERT INTO measurement (matrix, value, unit, value_original, unit_original, hg_species, below_dl,
                source_type, weight, lab_id, method, fish_species, fish_group, reference, sampled_on, geom,
                reach_id, snap_distance_m, status, batch_id, uploaded_by, is_synthetic, season, notes, reach_forced)
            VALUES (:matrix, :value, :unit, :vo, :uo, :hgs, :bdl, :st, :w, :lab, :method, :fs, :fg, :ref, :sd,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :reach, :dist, :status, :batch, :by, :syn,
                :season, :notes, :forced)
            RETURNING id""",
            matrix=it["matrix"], value=value, unit=CANONICA[it["matrix"]], vo=it["value"],
            uo=it.get("unit") or CANONICA[it["matrix"]], hgs=it["hg_species"], bdl=it["below_dl"],
            st=it["source_type"], w=cfg["confianza_fuente"][it["source_type"]], lab=lab_id,
            method=it.get("method"), fs=it.get("fish_species"), fg=group, ref=it.get("reference"),
            sd=it["sampled_on"], lon=it["lon"], lat=it["lat"], reach=reach_id, dist=dist, status=status,
            batch=batch, by=uploaded_by, syn=it["is_synthetic"], season=it["season"], notes=it["notes"],
            forced=forced)
        (ok if status == "valido" else revision).append(
            {"fila": n, "id": str(row["id"]), "reach_id": reach_id, **({"motivo": motivo} if motivo else {})})
    return {"lote": str(batch), "validas": ok, "en_revision": revision, "errores": errors}

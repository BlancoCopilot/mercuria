"""Flujo de un aporte: estudio → propuestas (IA o CSV) → revisión → publicación (mapa + datos abiertos)."""
from __future__ import annotations

import csv
import io
import json
import logging
import os
from datetime import date

from sqlalchemy import Connection, text

from ..db import one, rows, tx
from ..services.measurements import TRUE
from ..settings import get_settings
from .extract import RECORD_SCHEMA
from .prepare import parse_fecha, prepare

log = logging.getLogger(__name__)

FIELDS = list(RECORD_SCHEMA["properties"])

# CSV de investigadores: acepta nuestras columnas y alias comunes
CSV_ALIAS = {
    "matriz": "matriz", "matrix": "matriz", "valor": "valor", "value": "valor", "unidad": "unidad", "unit": "unidad",
    "lat": "lat", "latitud": "lat", "lon": "lon", "longitud": "lon", "lng": "lon",
    "utm_este": "utm_este", "utm_norte": "utm_norte", "utm_zona": "utm_zona",
    "fecha": "fecha", "fecha_muestreo": "fecha", "estacion_climatica": "estacion", "temporada": "estacion",
    "metodo": "metodo", "laboratorio": "laboratorio", "lugar": "lugar", "sitio": "lugar", "estacion": "lugar", "rio": "rio",
    "especie": "especie_comun", "especie_pez": "especie_comun", "especie_cientifica": "especie_cientifica",
    "bajo_ld": "bajo_ld", "limite_deteccion": "limite_deteccion", "ld": "limite_deteccion",
    "base": "base", "subtipo": "subtipo", "analito": "analito", "especie_hg": "analito",
    "origen_pez": "origen_pez", "estadistico": "estadistico", "n": "n", "desviacion": "desviacion",
    "minimo": "minimo", "maximo": "maximo",
}


def upload_dir() -> str:
    d = os.path.join(get_settings().upload_dir, "studies")
    os.makedirs(d, exist_ok=True)
    return d


def _blank() -> dict:
    return {k: None for k in FIELDS} | {"estacion": "desconocida", "base": "desconocido", "analito": "hg_total",
                                         "estadistico": "individual", "origen_pez": "no_aplica", "bajo_ld": False,
                                         "cita_textual": "", "confianza": 1.0}


def _num(x):
    if x in (None, ""):
        return None
    try:
        return float(str(x).replace(",", "."))
    except ValueError:
        return None


def parse_study_csv(content: bytes) -> list[dict]:
    t = content.decode("utf-8-sig")
    dialect = csv.Sniffer().sniff(t.splitlines()[0], delimiters=",;\t")
    out = []
    for i, row in enumerate(csv.DictReader(io.StringIO(t), dialect=dialect), start=2):
        f = _blank()
        for k, v in row.items():
            key = CSV_ALIAS.get((k or "").strip().lower())
            if key and v not in (None, ""):
                f[key] = v.strip()
        for k in ("valor", "lat", "lon", "utm_este", "utm_norte", "limite_deteccion", "desviacion", "minimo", "maximo"):
            f[k] = _num(f.get(k))
        f["n"] = int(_num(f["n"])) if _num(f.get("n")) else None
        f["bajo_ld"] = str(f.get("bajo_ld") or "").lower() in TRUE
        f["matriz"] = (f.get("matriz") or "").lower()
        an = str(f.get("analito") or "").lower()
        f["analito"] = "metilmercurio" if "met" in an else "hg_total"
        est = str(f.get("estacion") or "").lower()
        f["estacion"] = "humeda" if est.startswith(("h", "ll", "w", "c")) else "seca" if est.startswith(("s", "e", "d")) else "desconocida"
        if f["matriz"] == "pez" and f["origen_pez"] == "no_aplica":
            f["origen_pez"] = "captura" if f.get("lat") is not None else "desconocido"
        f["cita_textual"] = f"Fila {i} del CSV"
        f["pagina"] = None
        out.append(f)
    return out


def create_study(conn: Connection, meta: dict, filename: str, content: bytes, user_id: int) -> dict:
    kind = "pdf" if filename.lower().endswith(".pdf") else "csv"
    st = one(conn, """
        INSERT INTO study (title, authors, year, doi, url, institution, license, embargo_until, source_kind,
                           pdf_open_access, submitted_by, status)
        VALUES (:title, :authors, :year, :doi, :url, :institution, :license, :embargo, :kind, :oa, :u, 'procesando')
        RETURNING id""", **meta, kind=kind, u=user_id)
    sid = st["id"]
    path = os.path.join(upload_dir(), f"{sid}.{kind}")
    with open(path, "wb") as fh:
        fh.write(content)
    conn.execute(text("UPDATE study SET file_path=:p WHERE id=:id"), {"p": f"studies/{sid}.{kind}", "id": sid})
    if kind == "csv":
        records = parse_study_csv(content)
        _store_records(conn, sid, records)
        conn.execute(text("UPDATE study SET status='en_revision' WHERE id=:id"), {"id": sid})
    return {"id": sid, "kind": kind}


def _dup_key(f: dict) -> tuple:
    return (f.get("matriz"), f.get("subtipo"), f.get("analito"), round(float(f.get("valor") or 0), 6),
            (f.get("lugar") or "").lower().strip(), str(f.get("fecha") or ""))


def _store_records(conn: Connection, sid: int, records: list[dict]) -> int:
    conn.execute(text("DELETE FROM study_record WHERE study_id=:s AND measurement_id IS NULL"), {"s": sid})
    vistos: dict[tuple, int] = {}
    for i, f in enumerate(records, start=1):
        calc = prepare(conn, f)
        calc.pop("_fish")
        k = _dup_key(f)
        if k in vistos:
            calc["problems"] = [*calc["problems"], f"Posible duplicado de la fila {vistos[k]} (mismo valor, lugar y fecha)."]
        else:
            vistos[k] = i
        conn.execute(text("""
            INSERT INTO study_record (study_id, fields, raw, problems, modeled, value_canonical, unit_canonical,
                lat, lon, precision_m, location_source, reach_id, weight)
            VALUES (:s, CAST(:f AS jsonb), CAST(:f AS jsonb), :problems, :modeled, :value_canonical, :unit_canonical,
                :lat, :lon, :precision_m, :location_source, :reach_id, :weight)"""),
            {"s": sid, "f": json.dumps(f, ensure_ascii=False, default=str), **calc})
    return len(records)


def run_extraction(study_id: int) -> dict:
    """Trabajo del worker: PDF → IA → propuestas."""
    from .extract import extract_pdf

    with tx() as conn:
        st = one(conn, "SELECT id, file_path, year FROM study WHERE id=:id", id=study_id)
    path = os.path.join(get_settings().upload_dir, st["file_path"])
    try:
        with open(path, "rb") as fh:
            out = extract_pdf(fh.read(), os.path.basename(path))
    except Exception as e:  # noqa: BLE001
        log.exception("extracción falló")
        with tx() as conn:
            conn.execute(text("UPDATE study SET status='error', error=:e WHERE id=:id"), {"e": str(e)[:500], "id": study_id})
        return {"estado": "error", "error": str(e)}
    meds = out.get("mediciones") or []
    with tx() as conn:
        n = _store_records(conn, study_id, meds)
        conn.execute(text("""
            UPDATE study SET status='en_revision', extraction=CAST(:x AS jsonb), extraction_model=:m,
                summary=COALESCE(summary, :r), warnings=:w, error=NULL,
                authors=COALESCE(NULLIF(authors, ''), :a), year=COALESCE(year, :y), doi=COALESCE(NULLIF(doi, ''), :d),
                institution=COALESCE(NULLIF(institution, ''), :i)
            WHERE id=:id"""),
            {"x": json.dumps(out, ensure_ascii=False), "m": out["_meta"]["modelo"], "r": out.get("resumen"),
             "w": out.get("advertencias") or [], "a": out.get("autores"), "y": out.get("anio"),
             "d": out.get("doi"), "i": out.get("institucion"), "id": study_id})
    return {"estado": "en_revision", "mediciones": n, "paginas": out["_meta"]["paginas_enviadas"]}


def update_record(conn: Connection, rid: int, changes: dict | None, status: str | None, user_id: int) -> dict:
    r = one(conn, "SELECT id, fields, measurement_id FROM study_record WHERE id=:id", id=rid)
    if r["measurement_id"]:
        raise ValueError("Este dato ya está publicado; para corregirlo, contacta a la administración.")
    f = dict(r["fields"])
    if changes:
        for k, v in changes.items():
            if k in FIELDS:
                f[k] = v
        if changes.get("lat") is not None and changes.get("lon") is not None:
            f["_ubicacion"] = "manual"
    calc = prepare(conn, f)
    calc.pop("_fish")
    conn.execute(text("""
        UPDATE study_record SET fields=CAST(:f AS jsonb), status=COALESCE(:st, status), problems=:problems,
            modeled=:modeled, value_canonical=:value_canonical, unit_canonical=:unit_canonical, lat=:lat, lon=:lon,
            precision_m=:precision_m, location_source=:location_source, reach_id=:reach_id, weight=:weight,
            updated_by=:u, updated_at=now()
        WHERE id=:id"""), {"f": json.dumps(f, ensure_ascii=False, default=str), "st": status, "u": user_id, "id": rid, **calc})
    return one(conn, "SELECT * FROM study_record WHERE id=:id", id=rid)


def citation(st: dict) -> str:
    parts = [st.get("authors") or "", f"({st['year']})" if st.get("year") else "", st["title"]]
    c = " ".join(p for p in parts if p).strip()
    if st.get("doi"):
        c += f". doi:{st['doi']}"
    elif st.get("url"):
        c += f". {st['url']}"
    return c


def publish(conn: Connection, sid: int, license_: str | None, embargo: date | None) -> dict:
    """Publica: o queda embargado (hasta la fecha) o los datos aprobados entran al modelo ya."""
    if license_ or embargo is not None:
        conn.execute(text("UPDATE study SET license=COALESCE(:l, license), embargo_until=:e WHERE id=:id"),
                     {"l": license_, "e": embargo, "id": sid})
    st = one(conn, "SELECT * FROM study WHERE id=:id", id=sid)
    aprobados = one(conn, "SELECT count(*) AS n FROM study_record WHERE study_id=:s AND status='aprobado'", s=sid)["n"]
    if not aprobados:
        raise ValueError("Aprueba al menos un dato antes de publicar.")
    if st["embargo_until"] and st["embargo_until"] > date.today():
        conn.execute(text("UPDATE study SET status='embargado' WHERE id=:id"), {"id": sid})
        return {"estado": "embargado", "hasta": str(st["embargo_until"]), "aprobados": aprobados, "al_mapa": 0}
    return _release(conn, st)


def _release(conn: Connection, st: dict) -> dict:
    from .prepare import prepare as prep

    ref = citation(st)
    n = 0
    for r in rows(conn, """SELECT * FROM study_record WHERE study_id=:s AND status='aprobado'
                           AND measurement_id IS NULL""", s=st["id"]):
        if not r["modeled"]:
            continue
        f = r["fields"]
        codigo, grupo = prep(conn, f)["_fish"]
        m = one(conn, """
            INSERT INTO measurement (matrix, value, unit, value_original, unit_original, hg_species, below_dl,
                source_type, weight, method, fish_species, fish_group, reference, sampled_on, geom, reach_id,
                status, is_synthetic, season, notes, study_id, basis, subtype, precision_m)
            VALUES (:matrix, :value, :unit, :vo, :uo, :hgs, :bdl, 'publicado', :w, :method, :fs, :fg, :ref, :sd,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :reach, 'valido', false, :season, :notes, :sid, :basis,
                :subtype, :prec)
            RETURNING id""",
            matrix=f["matriz"], value=r["value_canonical"], unit=r["unit_canonical"], vo=f["valor"], uo=f.get("unidad") or "",
            hgs="metil" if f.get("analito") == "metilmercurio" else "total", bdl=bool(f.get("bajo_ld")), w=r["weight"],
            method=f.get("metodo"), fs=codigo, fg=grupo, ref=ref, sd=parse_fecha(f.get("fecha"), st.get("year")),
            lon=r["lon"], lat=r["lat"], reach=r["reach_id"],
            season=f.get("estacion") if f.get("estacion") in ("seca", "humeda") else None,
            notes=f"pág. {f.get('pagina') or '—'} · «{(f.get('cita_textual') or '')[:180]}» · ubicación: {r['location_source']}",
            sid=st["id"], basis=f.get("base"), subtype=f.get("subtipo"), prec=r["precision_m"])
        conn.execute(text("UPDATE study_record SET measurement_id=:m WHERE id=:id"), {"m": m["id"], "id": r["id"]})
        n += 1
    conn.execute(text("UPDATE study SET status='publicado', published_at=now() WHERE id=:id"), {"id": st["id"]})
    return {"estado": "publicado", "al_mapa": n}


def release_embargoes() -> dict:
    """Cron diario: publica los estudios cuyo embargo ya venció."""
    from ..worker.queue import request_recompute

    out = []
    with tx() as conn:
        for st in rows(conn, "SELECT * FROM study WHERE status='embargado' AND embargo_until <= current_date"):
            out.append({"estudio": st["id"], **_release(conn, st)})
    if any(o["al_mapa"] for o in out):
        request_recompute("medicion", {"embargos_liberados": [o["estudio"] for o in out]})
    return {"liberados": out}


def reprepare(conn: Connection, sid: int) -> int:
    """Recalcula problemas/ubicación de las propuestas (p. ej. tras cambiar reglas o cargar comunidades)."""
    n = 0
    for r in rows(conn, "SELECT id FROM study_record WHERE study_id=:s AND measurement_id IS NULL", s=sid):
        update_record(conn, r["id"], None, None, None)
        n += 1
    return n

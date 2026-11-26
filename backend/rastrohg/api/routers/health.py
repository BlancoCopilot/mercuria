"""Módulo 8: salud y seguimiento (promotores de salud).

Privacidad:
* Sin consentimiento no se guarda nada (validado aquí y con CHECK en la base).
* No se guardan nombre, CI ni fecha de nacimiento: grupo de edad y comunidad bastan.
* Un promotor solo ve sus propios casos.
* Autoridades y mapa solo ven agregados por comunidad con al menos 5 casos.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from ...db import one, rows
from ...engine.params import load_yaml
from ...services.card import triage
from ..deps import DbDep, require
from ..schemas import CampaignIn, CaseIn, HairResultIn, ReferralIn, ReferralOutcome

router = APIRouter(prefix="/v1/health", tags=["salud"])
Promotor = Annotated[dict, Depends(require("promotor"))]
Authority = Annotated[dict, Depends(require("autoridad"))]
K_ANON = 5


def _protocol() -> dict:
    return load_yaml("health_protocol.yaml")


@router.get("/protocol")
def protocol(_: Promotor):
    return _protocol()


@router.post("/cases", status_code=201)
def create_case(body: CaseIn, db: DbDep, user: Promotor):
    p = _protocol()
    known = {x["codigo"] for x in p["sintomas"]} | {x["codigo"] for x in p["senales_alarma"]} | \
            {x["codigo"] for x in p["exposicion"]}
    unknown = set(body.symptoms + body.alarm_signs + body.exposures) - known
    if unknown:
        raise HTTPException(400, f"Códigos desconocidos: {sorted(unknown)}")
    level = triage(p, body.symptoms, body.alarm_signs, body.exposures, body.pregnant, body.age_group)
    row = one(db.conn, """
        INSERT INTO health_case (client_uuid, promotor_id, settlement_id, consent_given, consent_at, age_group, sex,
                                 pregnant, symptoms, alarm_signs, exposures, triage, created_client_at)
        VALUES (:cu, :p, :s, true, :ca, :ag, :sex, :preg, :sy, :al, :ex, :t, :cc)
        ON CONFLICT (client_uuid) DO NOTHING RETURNING id, triage, status""",
        cu=body.client_uuid, p=user["id"], s=body.settlement_id, ca=body.consent_at, ag=body.age_group,
        sex=body.sex, preg=body.pregnant, sy=body.symptoms, al=body.alarm_signs, ex=body.exposures,
        t=level, cc=body.created_client_at)
    if row is None:   # reenvío desde el teléfono: idempotente
        row = one(db.conn, "SELECT id, triage, status FROM health_case WHERE client_uuid=:c AND promotor_id=:p",
                  c=body.client_uuid, p=user["id"])
    centro = one(db.conn, """
        SELECT f.id, f.name, f.phone, f.level,
               round((ST_Distance(f.geom::geography, s.geom::geography)/1000)::numeric, 1) AS km
        FROM health_facility f, settlement s WHERE s.id = :s
        ORDER BY f.geom <-> s.geom LIMIT 1""", s=body.settlement_id)
    return {**row, "protocolo_validado": p["validado"], "centro_sugerido": centro,
            "mensaje": {"urgente": "Derivar HOY al centro de salud.",
                        "prioritario": "Derivar esta semana al centro de salud.",
                        "rutina": "Orientar y programar control."}[level]}


@router.get("/cases")
def my_cases(db: DbDep, user: Promotor, status: str | None = None):
    return rows(db.conn, """
        SELECT c.id, c.settlement_id, s.name AS comunidad, c.age_group, c.triage, c.status, c.symptoms, c.created_at
        FROM health_case c JOIN settlement s ON s.id = c.settlement_id
        WHERE c.promotor_id = :p AND (CAST(:st AS text) IS NULL OR c.status = :st)
        ORDER BY c.created_at DESC""", p=user["id"], st=status)


def _own_case(db: DbDep, case_id: str, user: dict) -> dict:
    c = one(db.conn, "SELECT id, settlement_id FROM health_case WHERE id=CAST(:id AS uuid) AND (promotor_id=:p OR :admin)",
            id=case_id, p=user["id"], admin=user["role"] == "admin")
    if not c:
        raise HTTPException(404, "Caso no encontrado")
    return c


@router.post("/cases/{case_id}/referrals", status_code=201)
def refer(case_id: str, body: ReferralIn, db: DbDep, user: Promotor):
    c = _own_case(db, case_id, user)
    fid = body.facility_id or one(db.conn, """SELECT f.id FROM health_facility f, settlement s WHERE s.id=:s
                                              ORDER BY f.geom <-> s.geom LIMIT 1""", s=c["settlement_id"])["id"]
    ref = one(db.conn, """INSERT INTO referral (case_id, facility_id, reason) VALUES (:c, :f, :r)
                          RETURNING id, facility_id, referred_at""", c=c["id"], f=fid, r=body.reason)
    db.conn.execute(text("UPDATE health_case SET status='derivado' WHERE id=:c"), {"c": c["id"]})
    hoy = date.today()
    rem = [{"c": c["id"], "d": hoy + timedelta(days=d), "k": f"control_{d}d"} for d in _protocol()["recordatorios_dias"]]
    db.conn.execute(text("INSERT INTO followup_reminder (case_id, due_on, kind) VALUES (:c, :d, :k)"), rem)
    return {**ref, "recordatorios": [str(r["d"]) for r in rem]}


@router.patch("/referrals/{ref_id}")
def referral_outcome(ref_id: int, body: ReferralOutcome, db: DbDep, user: Promotor):
    r = one(db.conn, """UPDATE referral rf SET outcome=:o, outcome_at=now() FROM health_case c
                        WHERE rf.id=:id AND c.id=rf.case_id AND (c.promotor_id=:p OR :admin)
                        RETURNING rf.case_id""", o=body.outcome, id=ref_id, p=user["id"], admin=user["role"] == "admin")
    if not r:
        raise HTTPException(404)
    db.conn.execute(text("UPDATE health_case SET status=:s WHERE id=:c"), {"s": body.status, "c": r["case_id"]})
    return {"ok": True}


@router.get("/reminders")
def reminders(db: DbDep, user: Promotor, days_ahead: int = 7):
    return rows(db.conn, """
        SELECT r.id, r.case_id, r.due_on, r.kind, s.name AS comunidad, c.triage
        FROM followup_reminder r JOIN health_case c ON c.id = r.case_id JOIN settlement s ON s.id = c.settlement_id
        WHERE r.done_at IS NULL AND c.promotor_id = :p AND r.due_on <= current_date + :d
        ORDER BY r.due_on""", p=user["id"], d=days_ahead)


@router.post("/reminders/{rid}/done")
def reminder_done(rid: int, db: DbDep, user: Promotor):
    r = one(db.conn, """UPDATE followup_reminder r SET done_at=now() FROM health_case c
                        WHERE r.id=:id AND c.id=r.case_id AND c.promotor_id=:p RETURNING r.id""", id=rid, p=user["id"])
    if not r:
        raise HTTPException(404)
    return {"ok": True}


# --- Campañas de muestreo de cabello ---------------------------------------
@router.post("/campaigns", status_code=201)
def create_campaign(body: CampaignIn, db: DbDep, user: Promotor):
    return one(db.conn, """INSERT INTO hair_campaign (name, settlement_id, planned_on, created_by)
                           VALUES (:n, :s, :d, :u) RETURNING *""", n=body.name, s=body.settlement_id,
               d=body.planned_on, u=user["id"])


@router.get("/campaigns")
def campaigns(db: DbDep, _: Annotated[dict, Depends(require("promotor", "autoridad"))]):
    return rows(db.conn, """SELECT c.*, s.name AS comunidad, (SELECT count(*) FROM hair_result r WHERE r.campaign_id=c.id) AS muestras
                            FROM hair_campaign c JOIN settlement s ON s.id=c.settlement_id ORDER BY planned_on DESC""")


@router.post("/campaigns/{cid}/results", status_code=201)
def add_results(cid: int, items: list[HairResultIn], db: DbDep, _: Promotor):
    if not one(db.conn, "SELECT id FROM hair_campaign WHERE id=:c", c=cid):
        raise HTTPException(404)
    db.conn.execute(text("""INSERT INTO hair_result (campaign_id, case_id, age_group, value_ug_g, lab_id)
                            VALUES (:c, :case, :ag, :v, :lab)"""),
                    [{"c": cid, "case": i.case_id, "ag": i.age_group, "v": i.value_ug_g, "lab": i.lab_id} for i in items])
    db.conn.execute(text("UPDATE hair_campaign SET status='en_curso' WHERE id=:c AND status='planificada'"), {"c": cid})
    return {"agregados": len(items)}


@router.get("/campaigns/{cid}/summary")
def campaign_summary(cid: int, db: DbDep, _: Annotated[dict, Depends(require("promotor", "autoridad"))]):
    cab = _protocol()["cabello"]
    r = one(db.conn, """
        SELECT count(*) AS n, percentile_cont(0.5) WITHIN GROUP (ORDER BY value_ug_g) AS mediana,
               count(*) FILTER (WHERE value_ug_g > :ref) AS sobre_referencia,
               count(*) FILTER (WHERE value_ug_g > :alto) AS altos
        FROM hair_result WHERE campaign_id = :c""", c=cid, ref=cab["referencia_ug_g"], alto=cab["alto_ug_g"])
    if r["n"] < K_ANON:
        return {"n": r["n"], "oculto": f"menos de {K_ANON} muestras: no se publica el resumen"}
    return {**r, "referencia_ug_g": cab["referencia_ug_g"], "alto_ug_g": cab["alto_ug_g"]}


@router.get("/aggregates")
def aggregates(db: DbDep, _: Authority):
    return rows(db.conn, "SELECT * FROM health_aggregate ORDER BY casos DESC")

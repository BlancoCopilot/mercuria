from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from ...db import one
from fastapi import Request

from ..deps import DbDep, client_ip_hash, current_user, rate_limit
from ..schemas import LoginIn, SolicitudCuenta, TokenOut
from ..security import create_token, hash_password, verify_password

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: DbDep):
    rate_limit(f"login:{body.email.lower()}", 10, 900)
    u = one(db.conn, "SELECT id, role, password_hash, active FROM app_user WHERE lower(email)=lower(:e)", e=body.email)
    if not u or not verify_password(body.password, u["password_hash"]):
        raise HTTPException(401, "Correo o contraseña incorrectos")
    if not u["active"]:
        raise HTTPException(403, "Tu cuenta está pendiente de aprobación. Te avisaremos cuando esté activa.")
    return TokenOut(access_token=create_token(u["id"], u["role"]), role=u["role"])


@router.get("/me")
def me(user: Annotated[dict, Depends(current_user)]):
    return user


@router.post("/solicitar-cuenta", status_code=201)
def solicitar_cuenta(body: SolicitudCuenta, db: DbDep, request: Request):
    """Universidades e investigadores piden su cuenta; queda inactiva hasta que un admin la apruebe."""
    rate_limit(f"solicitud:{client_ip_hash(request)}", 5, 3600)
    if one(db.conn, "SELECT 1 AS x FROM app_user WHERE lower(email)=lower(:e)", e=body.email):
        raise HTTPException(409, "Ya existe una cuenta con ese correo.")
    one(db.conn, """INSERT INTO app_user (email, name, role, org, password_hash, active)
                    VALUES (:e, :n, 'investigador', :o, :p, false) RETURNING id""",
        e=body.email.strip(), n=body.name.strip(), o=body.institution.strip(), p=hash_password(body.password))
    return {"ok": True, "mensaje": "Solicitud recibida. Una persona del equipo la revisará y activará tu cuenta."}

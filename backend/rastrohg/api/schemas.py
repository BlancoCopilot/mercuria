from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

Matrix = Literal["agua", "sedimento", "pez"]
Lang = Literal["es", "ay", "qu", "gn"]
AgeGroup = Literal["0-4", "5-14", "15-49", "50+"]


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class UserIn(BaseModel):
    email: str
    name: str
    role: Literal["admin", "laboratorio", "promotor", "lider", "autoridad", "investigador"]
    password: str = Field(min_length=10)
    org: str | None = None
    lab_id: int | None = None
    settlement_id: int | None = None


# --- Dispositivos y sincronización offline ---------------------------------
class DeviceIn(BaseModel):
    platform: Literal["android", "ios", "web"] = "android"
    lang: Lang = "es"


class DeviceOut(BaseModel):
    device_id: UUID
    device_token: str = Field(description="Se muestra UNA sola vez. Guárdelo en el teléfono.")


class DeviceUpdate(BaseModel):
    push_token: str | None = Field(default=None, description="ExponentPushToken[...]")
    lang: Lang | None = None
    subscribe_settlements: list[int] = []
    subscribe_h3: list[str] = []
    subscribe_point: tuple[float, float] | None = Field(default=None, description="(lat, lon)")


class ReportIn(BaseModel):
    client_uuid: UUID
    kind: Literal["mineria", "agua_turbia", "peces_muertos", "salud", "otro"]
    description: str | None = Field(default=None, max_length=1000)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    area_ha: float | None = Field(default=None, gt=0, le=500)
    created_client_at: datetime


class FishSurveyIn(BaseModel):
    client_uuid: UUID
    settlement_id: int | None = None
    lat: float
    lon: float
    comidas_semana: float = Field(ge=0, le=30)
    especies: list[str] = []
    created_client_at: datetime


class SyncIn(BaseModel):
    since_version: int = 0
    reports: list[ReportIn] = []
    fish_surveys: list[FishSurveyIn] = []


# --- Mediciones -------------------------------------------------------------
class MeasurementIn(BaseModel):
    matrix: Matrix
    value: float = Field(gt=0)
    unit: str
    lat: float
    lon: float
    sampled_on: date | None = None
    source_type: Literal["laboratorio", "publicado", "kit"] = "laboratorio"
    method: str | None = None
    fish_species: str | None = None
    below_dl: bool = False
    reference: str | None = None
    hg_species: Literal["total", "metil"] = "total"
    is_synthetic: bool = False
    season: Literal["seca", "humeda"] | None = None
    reach_override: int | None = Field(default=None, description="hyriv_id si el punto está en un arroyo junto a un río grande")
    notes: str | None = None


class MeasurementReview(BaseModel):
    status: Literal["valido", "en_revision", "rechazado"]


# --- Denuncias / traducciones ----------------------------------------------
class ReportReview(BaseModel):
    decision: Literal["validada", "rechazada"]


class TranslationIn(BaseModel):
    key: str
    lang: Lang
    text: str


# --- Salud ------------------------------------------------------------------
class CaseIn(BaseModel):
    client_uuid: UUID
    settlement_id: int
    consent_given: Literal[True] = Field(description="Sin consentimiento informado no se registra")
    consent_at: datetime
    age_group: AgeGroup
    sex: Literal["f", "m", "otro"] | None = None
    pregnant: bool = False
    symptoms: list[str] = []
    alarm_signs: list[str] = []
    exposures: list[str] = []
    created_client_at: datetime


class ReferralIn(BaseModel):
    facility_id: int | None = Field(default=None, description="Si se omite: el más cercano a la comunidad")
    reason: str | None = None


class ReferralOutcome(BaseModel):
    outcome: str
    status: Literal["atendido", "seguimiento", "cerrado"] = "atendido"


class CampaignIn(BaseModel):
    name: str
    settlement_id: int
    planned_on: date


class HairResultIn(BaseModel):
    age_group: AgeGroup
    value_ug_g: float = Field(ge=0)
    case_id: UUID | None = None
    lab_id: int | None = None


# --- Admin ------------------------------------------------------------------
class DetectionsIn(BaseModel):
    source: Literal["amw", "mapbiomas", "manual"] = "manual"
    is_synthetic: bool = False
    geojson: dict[str, Any] = Field(description="FeatureCollection de polígonos; properties.detected_on opcional")


# --- Chatbot RAG -------------------------------------------------------------
Tema = Literal["peces", "salud", "mineria", "agua", "normas", "historia", "relaves", "retorta"]


class ChatTurn(BaseModel):
    rol: Literal["usuario", "asistente"]
    texto: str = Field(max_length=2000)


class ChatIn(BaseModel):
    pregunta: str = Field(min_length=2, max_length=1000)
    historial: list[ChatTurn] = Field(default=[], max_length=12, description="turnos anteriores (opcional)")
    tema: Tema | None = Field(default=None, description="limita la búsqueda a un tema")
    lat: float | None = Field(default=None, ge=-90, le=90, description="ubicación compartida (opcional)")
    lon: float | None = Field(default=None, ge=-180, le=180)
    comunidad_id: int | None = Field(default=None, description="en vez de lat/lon: la comunidad elegida en la app")


class ChatSource(BaseModel):
    n: int
    tipo: Literal["pdf", "faq", "mapa", "web"]
    archivo: str
    titulo: str
    pagina: int | None
    tema: str | None
    fragmento: str
    score: float
    url: str | None = None


class VozIn(BaseModel):
    sdp: str = Field(min_length=20, max_length=20000, description="oferta SDP del navegador")
    historial: list[ChatTurn] = Field(default=[], max_length=12, description="chat de texto previo (opcional)")
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    comunidad_id: int | None = None


class VozBuscarIn(BaseModel):
    pregunta: str = Field(min_length=2, max_length=1000)
    tema: Tema | None = None


class ChatOut(BaseModel):
    respuesta: str
    fuentes: list[ChatSource]
    modelo: str | None
    latencia_ms: int | None = None
    sin_modelo: bool = False
    error: str | None = None
    zona: dict[str, Any] | None = Field(default=None, description="comunidad, nivel de riesgo y centro de salud usados")


# --- Aportes de investigación ----------------------------------------------
class SolicitudCuenta(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    email: str = Field(min_length=5, max_length=200)
    institution: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=10, max_length=200)
    motivo: str | None = Field(default=None, max_length=1000)


class RecordUpdate(BaseModel):
    fields: dict | None = None
    status: Literal["propuesto", "aprobado", "rechazado"] | None = None


class PublishIn(BaseModel):
    license: Literal["CC-BY-4.0", "CC0-1.0", "CC-BY-SA-4.0"] = "CC-BY-4.0"
    embargo_until: date | None = None

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://rastrohg:rastrohg@localhost:5432/rastrohg"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "cambiar-en-produccion"
    jwt_hours: int = 12

    # Cuenca piloto: minlon,minlat,maxlon,maxlat (por defecto Tipuani–Mapiri–Kaká, La Paz)
    pilot_bbox: str = "-68.8,-15.9,-67.3,-14.3"
    upload_dir: str = "/data/uploads"
    tiles_dir: str = "/data/tiles"

    expo_push_url: str = "https://exp.host/--/api/v2/push/send"
    push_enabled: bool = False          # en la demo local se deja en false (solo outbox)

    # Fuentes programadas (URL o ruta local a GeoJSON/GPKG)
    amw_url: str = ""
    mapbiomas_url: str = ""
    # Google Earth Engine (proyecto de Cloud registrado en Earth Engine)
    ee_project: str = ""                          # EE_PROJECT en .env
    ee_service_account_key: str = ""   # ruta a JSON de cuenta de servicio (opcional; si no, usa `earthengine authenticate`)

    overpass_url: str = "https://overpass-api.de/api/interpreter"
    http_user_agent: str = "RastroHg/0.1 (hackathon Gold for Good)"

    # Chatbot RAG
    openai_api_key: str = ""                      # sin clave, /v1/chat responde solo con preguntas frecuentes y fragmentos
    rag_model: str = "gpt-5.4-mini"
    rag_reasoning_effort: str = "low"             # minimal | low | medium | high; "" si el modelo no razona (gpt-4.1...)
    rag_top_k: int = 6
    rag_embed_model: str = "text-embedding-3-small"   # 1536 dim (ver db/init/02_rag.sql)
    rag_vision_model: str = ""                    # describe las figuras de los PDFs; "" = rag_model
    rag_images_max_per_doc: int = 40              # tope de figuras por PDF (costo)
    research_model: str = ""                      # extracción de PDFs de investigación; "" = rag_model
    research_max_pdf_mb: int = 40
    research_reasoning_effort: str = "low"        # "medium" tardó 4 min y devolvió JSON duplicado en pruebas
    chat_per_ip_hour: int = 30
    # Cabecera con la IP real de quien llama, puesta por un proxy de confianza. Detrás del túnel de
    # Cloudflare: "cf-connecting-ip" (sin esto, todos comparten la IP del túnel y los límites "por
    # persona" son en realidad globales). Vacío = X-Forwarded-For / IP directa (desarrollo local).
    ip_header: str = ""
    chat_web_search: bool = True                  # si los documentos no responden, el modelo busca en internet

    # Voz en tiempo real (GPT-Live por WebRTC; el modelo de texto hace la búsqueda en documentos e internet)
    live_model: str = "gpt-live-1.1"
    live_voice: str = "luciernaga"                # voces en español: luciernaga, destello (MX); calandria, compas, hornero (AR)
    live_backend_model: str = ""                  # "" = rag_model
    live_idle_timeout_s: int = 20                 # tras este silencio la sesión pasa a espera (más barata)
    live_max_minutes: int = 5                     # el navegador corta la llamada a los N minutos
    live_per_ip_hour: int = 15
    live_global_per_hour: int = 60                # tope para toda la app (la clave de OpenAI es una sola)

    # Límites anti-abuso
    reports_per_device_hour: int = 20
    device_registrations_per_ip_hour: int = 10
    max_photo_mb: int = 8

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        a, b, c, d = (float(x) for x in self.pilot_bbox.split(","))
        return a, b, c, d


@lru_cache
def get_settings() -> Settings:
    return Settings()

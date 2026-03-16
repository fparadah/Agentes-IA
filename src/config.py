"""
Configuracion centralizada del sistema.
Lee todas las variables de entorno en un solo lugar.

Uso:
    from src.config import config
    if config.whatsapp_enabled: ...
    print(config.clinic_name)
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    # ------------------------------------------------------------------
    # Anthropic (Claude)
    # ------------------------------------------------------------------
    anthropic_api_key: str = ""

    # ------------------------------------------------------------------
    # WhatsApp Business — Meta Cloud API
    # Obtener en: Meta Business Manager → WhatsApp → API Setup
    # ------------------------------------------------------------------
    whatsapp_access_token: str = ""      # Token de acceso permanente
    whatsapp_phone_number_id: str = ""   # ID del numero (no el numero en si)
    whatsapp_webhook_verify_token: str = ""  # Token secreto para verificar webhook

    # Activar envio real de mensajes (false = modo simulacion)
    whatsapp_enabled: bool = False

    # ------------------------------------------------------------------
    # Aplicacion
    # ------------------------------------------------------------------
    app_env: str = "development"         # development | production
    clinic_name: str = "Centro Clinico"
    timezone: str = "America/Santiago"
    database_path: str = "data/clinica.db"

    # ------------------------------------------------------------------
    # Scheduler (confirmaciones proactivas)
    # ------------------------------------------------------------------
    scheduler_enabled: bool = False
    scheduler_hora_confirmacion: int = 10   # 10:00 AM
    scheduler_hora_recordatorio: int = 14  # 14:00 PM (si no responde)

    # ------------------------------------------------------------------
    # Conector de agenda (Mydoc)
    # ------------------------------------------------------------------
    conector_modo: str = "local"   # local | mydoc | export
    mydoc_api_url: str = ""
    mydoc_api_token: str = ""
    mydoc_clinic_id: str = ""

    # ------------------------------------------------------------------
    # Propiedades utiles
    # ------------------------------------------------------------------

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    def validate(self) -> list[str]:
        """
        Valida la configuracion y retorna lista de advertencias.
        No lanza excepciones — el sistema puede correr en modo simulacion.
        """
        advertencias = []

        if not self.anthropic_api_key:
            advertencias.append(
                "ANTHROPIC_API_KEY no configurada — el agente conversacional no funcionara"
            )

        if self.whatsapp_enabled:
            if not self.whatsapp_access_token:
                advertencias.append("WHATSAPP_ACCESS_TOKEN requerida cuando WHATSAPP_ENABLED=true")
            if not self.whatsapp_phone_number_id:
                advertencias.append("WHATSAPP_PHONE_NUMBER_ID requerida cuando WHATSAPP_ENABLED=true")
            if not self.whatsapp_webhook_verify_token:
                advertencias.append("WHATSAPP_WEBHOOK_VERIFY_TOKEN requerida cuando WHATSAPP_ENABLED=true")

        if self.conector_modo == "mydoc":
            if not self.mydoc_api_url or not self.mydoc_api_token:
                advertencias.append("MYDOC_API_URL y MYDOC_API_TOKEN requeridas cuando CONECTOR_MODO=mydoc")

        return advertencias


def _bool(valor: str) -> bool:
    return valor.strip().lower() in ("1", "true", "yes", "si", "sí")


def cargar_config() -> Config:
    """
    Carga la configuracion desde variables de entorno.
    Si existe un archivo .env en el directorio raiz, lo carga primero.
    """
    # Cargar .env si existe (para desarrollo local)
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
        except ImportError:
            pass  # python-dotenv es opcional

    return Config(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        whatsapp_access_token=os.environ.get("WHATSAPP_ACCESS_TOKEN", ""),
        whatsapp_phone_number_id=os.environ.get("WHATSAPP_PHONE_NUMBER_ID", ""),
        whatsapp_webhook_verify_token=os.environ.get("WHATSAPP_WEBHOOK_VERIFY_TOKEN", ""),
        whatsapp_enabled=_bool(os.environ.get("WHATSAPP_ENABLED", "false")),
        app_env=os.environ.get("APP_ENV", "development"),
        clinic_name=os.environ.get("CLINIC_NAME", "Centro Clinico"),
        timezone=os.environ.get("TIMEZONE", "America/Santiago"),
        database_path=os.environ.get("DATABASE_PATH", "data/clinica.db"),
        scheduler_enabled=_bool(os.environ.get("SCHEDULER_ENABLED", "false")),
        scheduler_hora_confirmacion=int(os.environ.get("SCHEDULER_HORA_CONFIRMACION", "10")),
        scheduler_hora_recordatorio=int(os.environ.get("SCHEDULER_HORA_RECORDATORIO", "14")),
        conector_modo=os.environ.get("CONECTOR_MODO", "local"),
        mydoc_api_url=os.environ.get("MYDOC_API_URL", ""),
        mydoc_api_token=os.environ.get("MYDOC_API_TOKEN", ""),
        mydoc_clinic_id=os.environ.get("MYDOC_CLINIC_ID", ""),
    )


# Instancia global — importar desde aqui en el resto del codigo
config = cargar_config()

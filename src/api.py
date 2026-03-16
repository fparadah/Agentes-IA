"""
Servidor FastAPI — punto de entrada de produccion.

Expone los endpoints necesarios para:
  - Recibir mensajes de pacientes desde WhatsApp (webhook Meta)
  - Verificar el webhook durante el setup inicial
  - Health check para monitoreo del servidor

El scheduler de confirmaciones proactivas corre dentro del mismo proceso
usando APScheduler con timezone America/Santiago.

Iniciar servidor:
  uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload  # desarrollo
  uvicorn src.api:app --host 0.0.0.0 --port 8000 --workers 1  # produccion

Variables de entorno requeridas (.env):
  ANTHROPIC_API_KEY
  WHATSAPP_ACCESS_TOKEN
  WHATSAPP_PHONE_NUMBER_ID
  WHATSAPP_WEBHOOK_VERIFY_TOKEN
  WHATSAPP_ENABLED=true  (false en desarrollo)
  SCHEDULER_ENABLED=true  (false en desarrollo)
"""

import hashlib
import hmac
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from src import database as db
from src.config import config
from src import whatsapp
from src.webhook import ManejadorWhatsApp
from src.scheduler import procesar_citas_del_dia_siguiente

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scheduler APScheduler
# ---------------------------------------------------------------------------

_scheduler = None


def _iniciar_scheduler() -> None:
    global _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        _scheduler = BackgroundScheduler(timezone=config.timezone)

        # Job 1: Confirmaciones del dia siguiente (ej: 10:00 AM)
        _scheduler.add_job(
            _job_confirmaciones,
            CronTrigger(hour=config.scheduler_hora_confirmacion, minute=0),
            id="confirmaciones_diarias",
            name="Confirmaciones del dia siguiente",
            replace_existing=True,
        )

        # Job 2: Recordatorio para los que no respondieron (ej: 14:00 PM)
        _scheduler.add_job(
            _job_recordatorios,
            CronTrigger(hour=config.scheduler_hora_recordatorio, minute=0),
            id="recordatorios_diarios",
            name="Recordatorios a pacientes sin respuesta",
            replace_existing=True,
        )

        _scheduler.start()
        logger.info(
            "Scheduler iniciado — confirmaciones %02d:00, recordatorios %02d:00 (%s)",
            config.scheduler_hora_confirmacion,
            config.scheduler_hora_recordatorio,
            config.timezone,
        )
    except ImportError:
        logger.warning("APScheduler no instalado — scheduler desactivado")


def _job_confirmaciones() -> None:
    """Envia WhatsApp a todos los pacientes con cita agendada para manana."""
    logger.info("[Scheduler] Iniciando job de confirmaciones diarias")
    try:
        stats = procesar_citas_del_dia_siguiente()
        logger.info(
            "[Scheduler] Confirmaciones enviadas: %d/%d",
            stats.get("mensajes_enviados", 0),
            stats.get("pendientes", 0),
        )
    except Exception as e:
        logger.error("[Scheduler] Error en job de confirmaciones: %s", str(e))


def _job_recordatorios() -> None:
    """
    Segundo recordatorio para pacientes que no respondieron el mensaje de la manana.
    Por ahora registra en log; se implementa en la siguiente iteracion.
    """
    logger.info("[Scheduler] Job de recordatorios — pendiente de implementar")


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    db.inicializar_db()
    logger.info("Base de datos inicializada")

    advertencias = config.validate()
    for adv in advertencias:
        logger.warning("Config: %s", adv)

    if config.scheduler_enabled:
        _iniciar_scheduler()
    else:
        logger.info("Scheduler desactivado (SCHEDULER_ENABLED=false)")

    logger.info(
        "Rosita lista — entorno: %s | WhatsApp: %s | Scheduler: %s",
        config.app_env,
        "ON" if config.whatsapp_enabled else "SIMULADO",
        "ON" if config.scheduler_enabled else "OFF",
    )

    yield  # La aplicacion corre aqui

    # Shutdown
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler detenido")


# ---------------------------------------------------------------------------
# Aplicacion FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Rosita — Agenda Clinica",
    description="Agente de confirmacion de citas via WhatsApp",
    version="1.0.0",
    lifespan=lifespan,
)

# Singleton del manejador para que las sesiones persistan entre requests
_manejador = ManejadorWhatsApp(usar_agente=True)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """Health check para monitoreo del servidor."""
    return {
        "status": "ok",
        "agente": "Rosita",
        "entorno": config.app_env,
        "whatsapp": "activo" if config.whatsapp_enabled else "simulado",
        "scheduler": "activo" if config.scheduler_enabled else "inactivo",
        "hora_servidor": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }


@app.get("/webhook")
async def verificar_webhook(request: Request):
    """
    Verificacion del webhook de Meta WhatsApp Cloud API.
    Meta llama a este endpoint durante la configuracion inicial del webhook.

    Meta envia:
      ?hub.mode=subscribe
      &hub.challenge=CHALLENGE_CODE
      &hub.verify_token=TU_TOKEN_SECRETO
    """
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    challenge = params.get("hub.challenge", "")
    verify_token = params.get("hub.verify_token", "")

    if mode == "subscribe" and verify_token == config.whatsapp_webhook_verify_token:
        logger.info("Webhook de Meta verificado correctamente")
        return PlainTextResponse(content=challenge)

    logger.warning("Intento de verificacion de webhook fallido — token incorrecto")
    return Response(status_code=403)


@app.post("/webhook")
async def recibir_mensaje_whatsapp(request: Request):
    """
    Recibe mensajes entrantes de pacientes desde Meta WhatsApp Cloud API.

    Meta envia un POST cada vez que un paciente escribe al numero de la clinica.
    El sistema debe responder con HTTP 200 en menos de 20 segundos.
    """
    body_bytes = await request.body()

    # Verificar firma HMAC en produccion (seguridad: confirma que viene de Meta)
    if config.is_production:
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not _verificar_firma_meta(body_bytes, signature):
            logger.warning("Firma de webhook invalida — request rechazado")
            return Response(status_code=403)

    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"status": "invalid_json"}, status_code=400)

    # Extraer mensaje del payload de Meta
    mensaje_info = _parsear_payload_meta(data)
    if not mensaje_info:
        # Puede ser una notificacion de estado (delivery, read) — ignorar
        return JSONResponse({"status": "ok", "tipo": "no_message"})

    telefono, texto, whatsapp_msg_id = mensaje_info
    logger.info("Mensaje recibido de %s: '%s'", telefono, texto[:50])

    # Procesar mensaje con el manejador
    resultado = _manejador.procesar_mensaje(
        telefono=telefono,
        texto=texto,
    )

    # Enviar respuesta al paciente via WhatsApp
    respuesta_texto = resultado.get("respuesta", "")
    if respuesta_texto:
        envio = whatsapp.enviar_mensaje_texto(telefono, respuesta_texto)
        if not envio.get("exito"):
            logger.error("Error al enviar respuesta a %s: %s", telefono, envio.get("error"))

    return JSONResponse({"status": "ok", "accion": resultado.get("accion")})


# ---------------------------------------------------------------------------
# Endpoint de administracion (solo para uso interno / recepcion)
# ---------------------------------------------------------------------------

@app.post("/admin/scheduler/run")
async def ejecutar_scheduler_manual(request: Request):
    """
    Ejecuta el scheduler manualmente (para pruebas o ejecucion fuera de horario).
    Solo disponible en desarrollo o con token de admin.
    """
    if config.is_production:
        # En produccion, proteger con token basico
        auth = request.headers.get("X-Admin-Token", "")
        if auth != config.whatsapp_webhook_verify_token:
            return Response(status_code=403)

    from datetime import timedelta
    fecha = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    stats = procesar_citas_del_dia_siguiente(fecha_objetivo=fecha)
    return JSONResponse({"status": "ok", "stats": stats})


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def _parsear_payload_meta(data: dict) -> tuple[str, str, str] | None:
    """
    Extrae (telefono, texto, message_id) del payload JSON de Meta.
    Retorna None si no hay mensaje de texto (puede ser notificacion de estado).

    Estructura del payload de Meta:
    {
      "entry": [{
        "changes": [{
          "value": {
            "messages": [{
              "from": "56922334455",
              "id": "wamid.xxx",
              "type": "text",
              "text": {"body": "SI"}
            }]
          }
        }]
      }]
    }
    """
    try:
        entry = data["entry"][0]["changes"][0]["value"]
    except (KeyError, IndexError):
        return None

    messages = entry.get("messages", [])
    if not messages:
        return None

    mensaje = messages[0]
    tipo = mensaje.get("type", "")

    if tipo != "text":
        # Mensaje de imagen, audio, etc. — no procesamos por ahora
        logger.info("Tipo de mensaje no soportado: %s", tipo)
        return None

    telefono = "+" + mensaje.get("from", "")
    texto = mensaje.get("text", {}).get("body", "").strip()
    msg_id = mensaje.get("id", "")

    if not telefono or not texto:
        return None

    return telefono, texto, msg_id


def _verificar_firma_meta(body: bytes, signature: str) -> bool:
    """
    Verifica la firma HMAC-SHA256 que Meta incluye en cada webhook.
    Garantiza que el request viene realmente de Meta y no de terceros.

    Meta calcula: sha256=HMAC(app_secret, body)
    En nuestro caso usamos el webhook_verify_token como secreto compartido.
    """
    if not signature.startswith("sha256="):
        return False

    firma_recibida = signature[7:]  # quitar "sha256="
    firma_esperada = hmac.new(
        config.whatsapp_webhook_verify_token.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(firma_esperada, firma_recibida)

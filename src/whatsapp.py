"""
Cliente de WhatsApp Business — Meta Cloud API.

Envia mensajes a pacientes via la API oficial de Meta (Graph API).
No requiere Twilio ni intermediarios — usa directamente las credenciales
del Meta Business Manager.

Documentacion Meta:
  https://developers.facebook.com/docs/whatsapp/cloud-api/messages

Variables de entorno necesarias (cuando WHATSAPP_ENABLED=true):
  WHATSAPP_ACCESS_TOKEN      — token permanente de Meta Business Manager
  WHATSAPP_PHONE_NUMBER_ID   — ID del numero de WhatsApp Business

En modo simulacion (WHATSAPP_ENABLED=false), los mensajes se registran
en el log pero no se envian realmente.
"""

import json
import logging
from typing import Optional

import httpx

from src.config import config

logger = logging.getLogger(__name__)

# URL base de la Graph API de Meta
META_API_VERSION = "v19.0"
META_BASE_URL = f"https://graph.facebook.com/{META_API_VERSION}"


def _normalizar_telefono(telefono: str) -> str:
    """
    Convierte el telefono al formato que espera Meta (solo digitos, sin +).
    Ej: "+56922334455" → "56922334455"
    """
    return telefono.lstrip("+").replace(" ", "").replace("-", "")


def enviar_mensaje_texto(telefono: str, mensaje: str) -> dict:
    """
    Envia un mensaje de texto libre al paciente.

    Usar solo dentro de la ventana de 24 horas de conversacion activa
    (cuando el paciente escribio primero). Para mensajes proactivos
    (el sistema inicia) usar enviar_template().

    Args:
        telefono: numero del paciente con codigo de pais (ej: +56922334455)
        mensaje: texto del mensaje

    Returns:
        dict con {"exito": bool, "message_id": str, "error": str}
    """
    if not config.whatsapp_enabled:
        # Modo simulacion: registrar en log sin enviar
        logger.info(
            "[SIMULADO] WhatsApp → %s: %s",
            telefono,
            mensaje[:80] + ("..." if len(mensaje) > 80 else ""),
        )
        print(f"\n  📱 [WhatsApp SIMULADO] Para: {telefono}")
        print(f"     Mensaje: {mensaje}\n")
        return {"exito": True, "simulado": True, "message_id": "sim-000"}

    if not config.whatsapp_access_token or not config.whatsapp_phone_number_id:
        logger.error("WhatsApp no configurado: faltan credenciales Meta")
        return {"exito": False, "error": "Credenciales de WhatsApp no configuradas"}

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": _normalizar_telefono(telefono),
        "type": "text",
        "text": {"preview_url": False, "body": mensaje},
    }

    return _llamar_api(payload)


def enviar_template(
    telefono: str,
    template_name: str,
    variables: list[str],
    idioma: str = "es",
) -> dict:
    """
    Envia un template de mensaje aprobado por Meta.

    Usar para mensajes PROACTIVOS (el sistema inicia la conversacion,
    como el recordatorio del dia anterior). Requiere template pre-aprobado
    en Meta Business Manager → Plantillas de mensajes.

    Args:
        telefono: numero del paciente con codigo de pais
        template_name: nombre del template en Meta (ej: "confirmacion_cita")
        variables: lista de valores para {{1}}, {{2}}, etc. del template
        idioma: codigo de idioma del template (default "es")

    Returns:
        dict con {"exito": bool, "message_id": str, "error": str}

    Ejemplo de template en Meta Business Manager:
        Nombre: confirmacion_cita
        Cuerpo: "Hola {{1}}! Tienes cita el {{2}} a las {{3}} con {{4}}.
                 Responde SI para confirmar o NO para cancelar."
        Variables: [nombre, fecha, hora, medico]
    """
    if not config.whatsapp_enabled:
        logger.info(
            "[SIMULADO] WhatsApp Template → %s: %s(%s)",
            telefono, template_name, variables,
        )
        print(f"\n  📱 [WhatsApp Template SIMULADO] Para: {telefono}")
        print(f"     Template: {template_name}")
        print(f"     Variables: {variables}\n")
        return {"exito": True, "simulado": True, "message_id": "sim-tpl-000"}

    if not config.whatsapp_access_token or not config.whatsapp_phone_number_id:
        return {"exito": False, "error": "Credenciales de WhatsApp no configuradas"}

    parametros = [
        {"type": "text", "text": str(v)} for v in variables
    ]

    payload = {
        "messaging_product": "whatsapp",
        "to": _normalizar_telefono(telefono),
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": idioma},
            "components": [
                {
                    "type": "body",
                    "parameters": parametros,
                }
            ],
        },
    }

    return _llamar_api(payload)


def _llamar_api(payload: dict) -> dict:
    """
    Realiza la llamada HTTP a la Graph API de Meta.
    Maneja errores de red y errores de la API.
    """
    url = f"{META_BASE_URL}/{config.whatsapp_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {config.whatsapp_access_token}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            data = response.json()
            message_id = data.get("messages", [{}])[0].get("id", "")
            logger.info("WhatsApp enviado OK. message_id=%s", message_id)
            return {"exito": True, "message_id": message_id}

        # Error de la API de Meta
        error_data = response.json()
        error_msg = error_data.get("error", {}).get("message", response.text)
        logger.error("Error Meta API %d: %s", response.status_code, error_msg)
        return {"exito": False, "error": error_msg, "status_code": response.status_code}

    except httpx.TimeoutException:
        logger.error("Timeout al llamar Meta WhatsApp API para %s", payload.get("to"))
        return {"exito": False, "error": "Timeout al conectar con WhatsApp API"}

    except httpx.RequestError as e:
        logger.error("Error de red al llamar Meta WhatsApp API: %s", str(e))
        return {"exito": False, "error": f"Error de red: {str(e)}"}

"""
Herramientas (tools) que el agente IA puede invocar para gestionar citas.
Cada funcion retorna un dict con resultado + mensaje legible para el agente.
"""

from datetime import datetime
from typing import Any, Optional

from src import database as db
from src.models import EstadoCita, TipoContacto


def _fmt_cita(cita_id: str) -> dict:
    """Helper: carga y serializa una cita con datos de paciente y medico."""
    cita = db.obtener_cita(cita_id)
    if not cita:
        return {"error": f"No se encontro la cita con ID {cita_id}"}

    paciente = db.obtener_paciente(cita.paciente_id)
    medico = db.obtener_medico(cita.medico_id)

    return {
        "cita_id": cita.id,
        "estado": cita.estado.value,
        "fecha_hora": cita.fecha_hora_display,
        "fecha": cita.fecha,
        "hora": cita.hora,
        "motivo": cita.motivo,
        "notas": cita.notas,
        "paciente": paciente.nombre_completo if paciente else "Desconocido",
        "paciente_telefono": paciente.telefono if paciente else None,
        "medico": medico.nombre_completo if medico else "Desconocido",
        "especialidad": medico.especialidad if medico else None,
        "duracion_min": cita.duracion_min,
    }


# ---------------------------------------------------------------------------
# Herramientas de consulta
# ---------------------------------------------------------------------------

def herramienta_buscar_citas_paciente(nombre_o_telefono: str) -> dict[str, Any]:
    """
    Busca todas las citas de un paciente por su nombre o telefono.
    Retorna citas activas (agendadas y confirmadas).
    """
    pacientes = []

    # Intentar por telefono primero
    p = db.buscar_paciente_por_telefono(nombre_o_telefono)
    if p:
        pacientes = [p]
    else:
        pacientes = db.buscar_paciente_por_nombre(nombre_o_telefono)

    if not pacientes:
        return {
            "encontrado": False,
            "total": 0,
            "mensaje": f"No se encontro ningun paciente con '{nombre_o_telefono}'.",
            "citas": [],
        }

    resultado = []
    for paciente in pacientes:
        citas = db.obtener_citas_paciente(paciente.id)
        citas_activas = [
            c for c in citas
            if c.estado in (EstadoCita.AGENDADO, EstadoCita.CONFIRMADO)
        ]
        for cita in citas_activas:
            medico = db.obtener_medico(cita.medico_id)
            resultado.append({
                "cita_id": cita.id,
                "paciente": paciente.nombre_completo,
                "paciente_telefono": paciente.telefono,
                "estado": cita.estado.value,
                "fecha_hora": cita.fecha_hora_display,
                "fecha": cita.fecha,
                "hora": cita.hora,
                "medico": medico.nombre_completo if medico else "Desconocido",
                "motivo": cita.motivo,
            })

    return {
        "encontrado": True,
        "total": len(resultado),
        "citas": resultado,
    }


def herramienta_obtener_detalle_cita(cita_id: str) -> dict[str, Any]:
    """Obtiene todos los detalles de una cita especifica."""
    return _fmt_cita(cita_id)


def herramienta_listar_citas_del_dia(fecha: Optional[str] = None) -> dict[str, Any]:
    """
    Lista todas las citas de un dia. Si no se indica fecha, usa hoy.
    fecha: formato YYYY-MM-DD
    """
    if not fecha:
        fecha = datetime.now().strftime("%Y-%m-%d")

    citas = db.obtener_citas_por_fecha(fecha)
    if not citas:
        return {
            "fecha": fecha,
            "total": 0,
            "mensaje": f"No hay citas para el {fecha}.",
            "citas": [],
        }

    resultado = []
    for cita in citas:
        paciente = db.obtener_paciente(cita.paciente_id)
        medico = db.obtener_medico(cita.medico_id)
        resultado.append({
            "cita_id": cita.id,
            "hora": cita.hora,
            "estado": cita.estado.value,
            "paciente": paciente.nombre_completo if paciente else "Desconocido",
            "medico": medico.nombre_completo if medico else "Desconocido",
            "motivo": cita.motivo,
        })

    return {
        "fecha": fecha,
        "total": len(resultado),
        "citas": resultado,
    }


def herramienta_listar_citas_pendientes() -> dict[str, Any]:
    """Lista todas las citas en estado 'agendado' que aun no han sido confirmadas."""
    citas = db.obtener_citas_por_estado(EstadoCita.AGENDADO)
    if not citas:
        return {
            "total": 0,
            "mensaje": "No hay citas pendientes de confirmacion.",
            "citas": [],
        }

    resultado = []
    for cita in citas:
        paciente = db.obtener_paciente(cita.paciente_id)
        medico = db.obtener_medico(cita.medico_id)
        resultado.append({
            "cita_id": cita.id,
            "fecha_hora": cita.fecha_hora_display,
            "fecha": cita.fecha,
            "hora": cita.hora,
            "paciente": paciente.nombre_completo if paciente else "Desconocido",
            "paciente_telefono": paciente.telefono if paciente else None,
            "medico": medico.nombre_completo if medico else "Desconocido",
            "motivo": cita.motivo,
        })

    return {
        "total": len(resultado),
        "citas": resultado,
    }


# ---------------------------------------------------------------------------
# Herramientas de accion
# ---------------------------------------------------------------------------

def herramienta_confirmar_cita(cita_id: str) -> dict[str, Any]:
    """
    Cambia el estado de una cita de 'agendado' a 'confirmado'.
    """
    cita = db.obtener_cita(cita_id)
    if not cita:
        return {"exito": False, "mensaje": f"No se encontro la cita {cita_id}."}

    if cita.estado == EstadoCita.CONFIRMADO:
        return {"exito": False, "mensaje": "La cita ya estaba confirmada."}

    if cita.estado != EstadoCita.AGENDADO:
        return {
            "exito": False,
            "mensaje": f"No se puede confirmar una cita en estado '{cita.estado.value}'.",
        }

    cita_actualizada = db.confirmar_cita(cita_id)
    return {
        "exito": True,
        "mensaje": "Cita confirmada correctamente.",
        "cita": _fmt_cita(cita_id),
    }


def herramienta_cancelar_cita(cita_id: str, motivo: Optional[str] = None) -> dict[str, Any]:
    """
    Cancela una cita. Se puede indicar el motivo de cancelacion.
    """
    cita = db.obtener_cita(cita_id)
    if not cita:
        return {"exito": False, "mensaje": f"No se encontro la cita {cita_id}."}

    if cita.estado in (EstadoCita.CANCELADO, EstadoCita.COMPLETADO):
        return {
            "exito": False,
            "mensaje": f"La cita ya esta en estado '{cita.estado.value}' y no se puede cancelar.",
        }

    db.cancelar_cita(cita_id, motivo)
    return {
        "exito": True,
        "mensaje": "Cita cancelada correctamente.",
        "cita": _fmt_cita(cita_id),
    }


def herramienta_reagendar_cita(
    cita_id: str, nueva_fecha: str, nueva_hora: str
) -> dict[str, Any]:
    """
    Reagenda una cita a una nueva fecha y hora.
    nueva_fecha: formato YYYY-MM-DD
    nueva_hora: formato HH:MM
    Retorna la nueva cita creada.
    """
    # Validar formato de fecha
    try:
        datetime.strptime(nueva_fecha, "%Y-%m-%d")
        datetime.strptime(nueva_hora, "%H:%M")
    except ValueError:
        return {
            "exito": False,
            "mensaje": "Formato de fecha u hora invalido. Usar YYYY-MM-DD y HH:MM.",
        }

    cita = db.obtener_cita(cita_id)
    if not cita:
        return {"exito": False, "mensaje": f"No se encontro la cita {cita_id}."}

    if cita.estado in (EstadoCita.CANCELADO, EstadoCita.COMPLETADO):
        return {
            "exito": False,
            "mensaje": f"No se puede reagendar una cita en estado '{cita.estado.value}'.",
        }

    nueva_cita = db.reagendar_cita(cita_id, nueva_fecha, nueva_hora)
    if not nueva_cita:
        return {"exito": False, "mensaje": "Error al reagendar la cita."}

    return {
        "exito": True,
        "mensaje": "Cita reagendada correctamente. Se creo una nueva cita.",
        "cita_anterior_id": cita_id,
        "nueva_cita": _fmt_cita(nueva_cita.id),
    }


def herramienta_enviar_mensaje_paciente(
    cita_id: str,
    mensaje: str,
    canal: str = "whatsapp",
) -> dict[str, Any]:
    """
    Simula el envio de un mensaje al paciente asociado a la cita.
    En el MVP real, aqui se conectara con WhatsApp Business API, Twilio, etc.
    canal: 'whatsapp' | 'sms' | 'email' | 'telefono'
    """
    cita = db.obtener_cita(cita_id)
    if not cita:
        return {"exito": False, "mensaje": f"No se encontro la cita {cita_id}."}

    paciente = db.obtener_paciente(cita.paciente_id)
    if not paciente:
        return {"exito": False, "mensaje": "No se encontro el paciente."}

    try:
        tipo_canal = TipoContacto(canal)
    except ValueError:
        tipo_canal = TipoContacto.WHATSAPP

    log = db.registrar_mensaje(
        cita_id=cita_id,
        paciente_id=paciente.id,
        canal=tipo_canal,
        mensaje=mensaje,
    )

    return {
        "exito": True,
        "mensaje_id": log.id,
        "destinatario": paciente.nombre_completo,
        "canal": tipo_canal.value,
        "contacto": paciente.telefono,
        "mensaje_enviado": mensaje,
        "nota": "[SIMULADO] En produccion, este mensaje se enviaria via API de mensajeria.",
    }


def herramienta_registrar_respuesta_paciente(
    cita_id: str, respuesta: str
) -> dict[str, Any]:
    """
    Registra la respuesta del paciente en el log. Usado para simular
    la recepcion de mensajes del paciente durante las pruebas.
    """
    cita = db.obtener_cita(cita_id)
    if not cita:
        return {"exito": False, "mensaje": f"No se encontro la cita {cita_id}."}

    paciente = db.obtener_paciente(cita.paciente_id)
    if not paciente:
        return {"exito": False, "mensaje": "No se encontro el paciente."}

    log = db.registrar_mensaje(
        cita_id=cita_id,
        paciente_id=paciente.id,
        canal=paciente.canal_preferido,
        mensaje=f"[RESPUESTA PACIENTE] {respuesta}",
        respuesta=respuesta,
    )

    return {
        "exito": True,
        "mensaje": "Respuesta del paciente registrada.",
        "paciente": paciente.nombre_completo,
        "respuesta": respuesta,
    }


# ---------------------------------------------------------------------------
# Schema de herramientas para la API de Anthropic
# ---------------------------------------------------------------------------

HERRAMIENTAS_SCHEMA = [
    {
        "name": "buscar_citas_paciente",
        "description": "Busca todas las citas activas de un paciente por su nombre o numero de telefono. Usar cuando el paciente se identifica o cuando el operador quiere ver las citas de alguien.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre_o_telefono": {
                    "type": "string",
                    "description": "Nombre del paciente (o parte del nombre) o su numero de telefono.",
                }
            },
            "required": ["nombre_o_telefono"],
        },
    },
    {
        "name": "obtener_detalle_cita",
        "description": "Obtiene los detalles completos de una cita especifica por su ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cita_id": {
                    "type": "string",
                    "description": "ID unico de la cita.",
                }
            },
            "required": ["cita_id"],
        },
    },
    {
        "name": "listar_citas_del_dia",
        "description": "Lista todas las citas de un dia especifico. Si no se indica fecha, lista las de hoy.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fecha": {
                    "type": "string",
                    "description": "Fecha en formato YYYY-MM-DD. Si no se indica, usa la fecha de hoy.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "listar_citas_pendientes",
        "description": "Lista todas las citas en estado 'agendado' que aun no han sido confirmadas por el paciente.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "confirmar_cita",
        "description": "Cambia el estado de una cita de 'agendado' a 'confirmado'. Usar cuando el paciente confirma que asistira.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cita_id": {
                    "type": "string",
                    "description": "ID de la cita a confirmar.",
                }
            },
            "required": ["cita_id"],
        },
    },
    {
        "name": "cancelar_cita",
        "description": "Cancela una cita existente. Usar cuando el paciente indica que no podra asistir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cita_id": {
                    "type": "string",
                    "description": "ID de la cita a cancelar.",
                },
                "motivo": {
                    "type": "string",
                    "description": "Motivo de la cancelacion (opcional).",
                },
            },
            "required": ["cita_id"],
        },
    },
    {
        "name": "reagendar_cita",
        "description": "Cambia la fecha y hora de una cita. Marca la cita original como reagendada y crea una nueva cita con el nuevo horario.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cita_id": {
                    "type": "string",
                    "description": "ID de la cita a reagendar.",
                },
                "nueva_fecha": {
                    "type": "string",
                    "description": "Nueva fecha en formato YYYY-MM-DD.",
                },
                "nueva_hora": {
                    "type": "string",
                    "description": "Nueva hora en formato HH:MM.",
                },
            },
            "required": ["cita_id", "nueva_fecha", "nueva_hora"],
        },
    },
    {
        "name": "enviar_mensaje_paciente",
        "description": "Envia (simula) un mensaje al paciente para notificarle sobre su cita. En pruebas, muestra el mensaje en pantalla. En produccion, enviara via WhatsApp o SMS.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cita_id": {
                    "type": "string",
                    "description": "ID de la cita relacionada.",
                },
                "mensaje": {
                    "type": "string",
                    "description": "Texto del mensaje para el paciente. Debe ser en lenguaje cercano y claro.",
                },
                "canal": {
                    "type": "string",
                    "enum": ["whatsapp", "sms", "email", "telefono"],
                    "description": "Canal de comunicacion a usar. Por defecto: whatsapp.",
                },
            },
            "required": ["cita_id", "mensaje"],
        },
    },
    {
        "name": "registrar_respuesta_paciente",
        "description": "Registra la respuesta que dio el paciente. Usar en modo de prueba para simular que el paciente respondio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cita_id": {
                    "type": "string",
                    "description": "ID de la cita relacionada.",
                },
                "respuesta": {
                    "type": "string",
                    "description": "Texto de la respuesta del paciente.",
                },
            },
            "required": ["cita_id", "respuesta"],
        },
    },
]


# Mapa de nombre -> funcion para despachar llamadas del agente
MAPA_HERRAMIENTAS = {
    "buscar_citas_paciente": lambda args: herramienta_buscar_citas_paciente(
        args["nombre_o_telefono"]
    ),
    "obtener_detalle_cita": lambda args: herramienta_obtener_detalle_cita(
        args["cita_id"]
    ),
    "listar_citas_del_dia": lambda args: herramienta_listar_citas_del_dia(
        args.get("fecha")
    ),
    "listar_citas_pendientes": lambda args: herramienta_listar_citas_pendientes(),
    "confirmar_cita": lambda args: herramienta_confirmar_cita(args["cita_id"]),
    "cancelar_cita": lambda args: herramienta_cancelar_cita(
        args["cita_id"], args.get("motivo")
    ),
    "reagendar_cita": lambda args: herramienta_reagendar_cita(
        args["cita_id"], args["nueva_fecha"], args["nueva_hora"]
    ),
    "enviar_mensaje_paciente": lambda args: herramienta_enviar_mensaje_paciente(
        args["cita_id"], args["mensaje"], args.get("canal", "whatsapp")
    ),
    "registrar_respuesta_paciente": lambda args: herramienta_registrar_respuesta_paciente(
        args["cita_id"], args["respuesta"]
    ),
}

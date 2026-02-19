"""
Modelos de datos del sistema de agenda clinica.
Representa las entidades principales: Paciente, Medico, Cita.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class EstadoCita(str, Enum):
    AGENDADO = "agendado"
    CONFIRMADO = "confirmado"
    CANCELADO = "cancelado"
    REAGENDADO = "reagendado"
    COMPLETADO = "completado"
    NO_ASISTIO = "no_asistio"


class TipoContacto(str, Enum):
    TELEFONO = "telefono"
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    SMS = "sms"


@dataclass
class Paciente:
    id: str
    nombre: str
    apellido: str
    telefono: str
    email: Optional[str] = None
    fecha_nacimiento: Optional[str] = None
    rut: Optional[str] = None
    canal_preferido: TipoContacto = TipoContacto.WHATSAPP

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} {self.apellido}"


@dataclass
class Medico:
    id: str
    nombre: str
    apellido: str
    especialidad: str
    telefono: Optional[str] = None

    @property
    def nombre_completo(self) -> str:
        return f"Dr(a). {self.nombre} {self.apellido}"


@dataclass
class Cita:
    id: str
    paciente_id: str
    medico_id: str
    fecha: str           # formato: YYYY-MM-DD
    hora: str            # formato: HH:MM
    duracion_min: int    # duracion en minutos
    estado: EstadoCita
    motivo: str
    notas: Optional[str] = None
    fecha_confirmacion: Optional[str] = None
    fecha_cancelacion: Optional[str] = None
    cita_original_id: Optional[str] = None  # si es reagendamiento

    @property
    def fecha_hora_display(self) -> str:
        """Formato legible para mostrar al paciente."""
        try:
            dt = datetime.strptime(f"{self.fecha} {self.hora}", "%Y-%m-%d %H:%M")
            dias = ["lunes", "martes", "miercoles", "jueves",
                    "viernes", "sabado", "domingo"]
            meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                     "julio", "agosto", "septiembre", "octubre", "noviembre",
                     "diciembre"]
            dia_semana = dias[dt.weekday()]
            return f"{dia_semana} {dt.day} de {meses[dt.month - 1]} a las {self.hora}"
        except ValueError:
            return f"{self.fecha} a las {self.hora}"


@dataclass
class MensajeLog:
    """Registro de mensajes enviados a pacientes."""
    id: str
    cita_id: str
    paciente_id: str
    canal: TipoContacto
    mensaje: str
    timestamp: str
    estado_envio: str = "simulado"  # simulado | enviado | fallido
    respuesta_paciente: Optional[str] = None

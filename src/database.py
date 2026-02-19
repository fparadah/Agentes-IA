"""
Base de datos simulada para pruebas del sistema de agenda clinica.
Usa SQLite como almacenamiento local. En el MVP real, esto se reemplaza
por el conector al sistema de registro clinico existente.
"""

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.models import Cita, EstadoCita, MensajeLog, Medico, Paciente, TipoContacto

DB_PATH = Path(__file__).parent.parent / "data" / "clinica.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def inicializar_db() -> None:
    """Crea las tablas si no existen."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS pacientes (
                id TEXT PRIMARY KEY,
                nombre TEXT NOT NULL,
                apellido TEXT NOT NULL,
                telefono TEXT NOT NULL,
                email TEXT,
                fecha_nacimiento TEXT,
                rut TEXT,
                canal_preferido TEXT DEFAULT 'whatsapp'
            );

            CREATE TABLE IF NOT EXISTS medicos (
                id TEXT PRIMARY KEY,
                nombre TEXT NOT NULL,
                apellido TEXT NOT NULL,
                especialidad TEXT NOT NULL,
                telefono TEXT
            );

            CREATE TABLE IF NOT EXISTS citas (
                id TEXT PRIMARY KEY,
                paciente_id TEXT NOT NULL,
                medico_id TEXT NOT NULL,
                fecha TEXT NOT NULL,
                hora TEXT NOT NULL,
                duracion_min INTEGER NOT NULL DEFAULT 30,
                estado TEXT NOT NULL DEFAULT 'agendado',
                motivo TEXT NOT NULL,
                notas TEXT,
                fecha_confirmacion TEXT,
                fecha_cancelacion TEXT,
                cita_original_id TEXT,
                FOREIGN KEY (paciente_id) REFERENCES pacientes(id),
                FOREIGN KEY (medico_id) REFERENCES medicos(id)
            );

            CREATE TABLE IF NOT EXISTS mensajes_log (
                id TEXT PRIMARY KEY,
                cita_id TEXT NOT NULL,
                paciente_id TEXT NOT NULL,
                canal TEXT NOT NULL,
                mensaje TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                estado_envio TEXT DEFAULT 'simulado',
                respuesta_paciente TEXT
            );
        """)


# ---------------------------------------------------------------------------
# Pacientes
# ---------------------------------------------------------------------------

def crear_paciente(p: Paciente) -> Paciente:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO pacientes
               (id, nombre, apellido, telefono, email, fecha_nacimiento, rut, canal_preferido)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (p.id, p.nombre, p.apellido, p.telefono, p.email,
             p.fecha_nacimiento, p.rut, p.canal_preferido.value),
        )
    return p


def obtener_paciente(paciente_id: str) -> Optional[Paciente]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM pacientes WHERE id = ?", (paciente_id,)
        ).fetchone()
    return _row_a_paciente(row) if row else None


def buscar_paciente_por_telefono(telefono: str) -> Optional[Paciente]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM pacientes WHERE telefono = ?", (telefono,)
        ).fetchone()
    return _row_a_paciente(row) if row else None


def buscar_paciente_por_nombre(nombre: str) -> list[Paciente]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM pacientes WHERE nombre LIKE ? OR apellido LIKE ?",
            (f"%{nombre}%", f"%{nombre}%"),
        ).fetchall()
    return [_row_a_paciente(r) for r in rows]


def listar_pacientes() -> list[Paciente]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM pacientes ORDER BY apellido").fetchall()
    return [_row_a_paciente(r) for r in rows]


# ---------------------------------------------------------------------------
# Medicos
# ---------------------------------------------------------------------------

def crear_medico(m: Medico) -> Medico:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO medicos (id, nombre, apellido, especialidad, telefono)
               VALUES (?, ?, ?, ?, ?)""",
            (m.id, m.nombre, m.apellido, m.especialidad, m.telefono),
        )
    return m


def obtener_medico(medico_id: str) -> Optional[Medico]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM medicos WHERE id = ?", (medico_id,)
        ).fetchone()
    return _row_a_medico(row) if row else None


def listar_medicos() -> list[Medico]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM medicos ORDER BY apellido").fetchall()
    return [_row_a_medico(r) for r in rows]


# ---------------------------------------------------------------------------
# Citas
# ---------------------------------------------------------------------------

def crear_cita(c: Cita) -> Cita:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO citas
               (id, paciente_id, medico_id, fecha, hora, duracion_min, estado,
                motivo, notas, fecha_confirmacion, fecha_cancelacion, cita_original_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (c.id, c.paciente_id, c.medico_id, c.fecha, c.hora, c.duracion_min,
             c.estado.value, c.motivo, c.notas, c.fecha_confirmacion,
             c.fecha_cancelacion, c.cita_original_id),
        )
    return c


def obtener_cita(cita_id: str) -> Optional[Cita]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM citas WHERE id = ?", (cita_id,)
        ).fetchone()
    return _row_a_cita(row) if row else None


def obtener_citas_paciente(paciente_id: str) -> list[Cita]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM citas WHERE paciente_id = ? ORDER BY fecha, hora",
            (paciente_id,),
        ).fetchall()
    return [_row_a_cita(r) for r in rows]


def obtener_citas_por_fecha(fecha: str) -> list[Cita]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM citas WHERE fecha = ? ORDER BY hora",
            (fecha,),
        ).fetchall()
    return [_row_a_cita(r) for r in rows]


def obtener_citas_por_estado(estado: EstadoCita) -> list[Cita]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM citas WHERE estado = ? ORDER BY fecha, hora",
            (estado.value,),
        ).fetchall()
    return [_row_a_cita(r) for r in rows]


def confirmar_cita(cita_id: str) -> Optional[Cita]:
    ahora = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute(
            """UPDATE citas SET estado = ?, fecha_confirmacion = ?
               WHERE id = ? AND estado = 'agendado'""",
            (EstadoCita.CONFIRMADO.value, ahora, cita_id),
        )
    return obtener_cita(cita_id)


def cancelar_cita(cita_id: str, motivo_cancelacion: Optional[str] = None) -> Optional[Cita]:
    ahora = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute(
            """UPDATE citas SET estado = ?, fecha_cancelacion = ?, notas = ?
               WHERE id = ? AND estado NOT IN ('cancelado', 'completado')""",
            (EstadoCita.CANCELADO.value, ahora, motivo_cancelacion, cita_id),
        )
    return obtener_cita(cita_id)


def reagendar_cita(cita_id: str, nueva_fecha: str, nueva_hora: str) -> Optional[Cita]:
    """
    Marca la cita original como reagendada y crea una nueva cita.
    Retorna la nueva cita creada.
    """
    cita_original = obtener_cita(cita_id)
    if not cita_original:
        return None

    ahora = datetime.now().isoformat()
    nueva_id = str(uuid.uuid4())[:8]

    with get_connection() as conn:
        # Marcar la original como reagendada
        conn.execute(
            "UPDATE citas SET estado = ?, fecha_cancelacion = ? WHERE id = ?",
            (EstadoCita.REAGENDADO.value, ahora, cita_id),
        )
        # Crear nueva cita
        conn.execute(
            """INSERT INTO citas
               (id, paciente_id, medico_id, fecha, hora, duracion_min, estado,
                motivo, notas, cita_original_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (nueva_id, cita_original.paciente_id, cita_original.medico_id,
             nueva_fecha, nueva_hora, cita_original.duracion_min,
             EstadoCita.AGENDADO.value, cita_original.motivo,
             cita_original.notas, cita_id),
        )
    return obtener_cita(nueva_id)


def listar_todas_citas() -> list[Cita]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM citas ORDER BY fecha, hora"
        ).fetchall()
    return [_row_a_cita(r) for r in rows]


# ---------------------------------------------------------------------------
# Mensajes log
# ---------------------------------------------------------------------------

def registrar_mensaje(
    cita_id: str,
    paciente_id: str,
    canal: TipoContacto,
    mensaje: str,
    respuesta: Optional[str] = None,
) -> MensajeLog:
    msg = MensajeLog(
        id=str(uuid.uuid4())[:8],
        cita_id=cita_id,
        paciente_id=paciente_id,
        canal=canal,
        mensaje=mensaje,
        timestamp=datetime.now().isoformat(),
        respuesta_paciente=respuesta,
    )
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO mensajes_log
               (id, cita_id, paciente_id, canal, mensaje, timestamp,
                estado_envio, respuesta_paciente)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (msg.id, msg.cita_id, msg.paciente_id, msg.canal.value,
             msg.mensaje, msg.timestamp, msg.estado_envio,
             msg.respuesta_paciente),
        )
    return msg


def obtener_mensajes_cita(cita_id: str) -> list[MensajeLog]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM mensajes_log WHERE cita_id = ? ORDER BY timestamp",
            (cita_id,),
        ).fetchall()
    return [_row_a_mensaje(r) for r in rows]


# ---------------------------------------------------------------------------
# Conversores internos
# ---------------------------------------------------------------------------

def _row_a_paciente(row: sqlite3.Row) -> Paciente:
    return Paciente(
        id=row["id"],
        nombre=row["nombre"],
        apellido=row["apellido"],
        telefono=row["telefono"],
        email=row["email"],
        fecha_nacimiento=row["fecha_nacimiento"],
        rut=row["rut"],
        canal_preferido=TipoContacto(row["canal_preferido"]),
    )


def _row_a_medico(row: sqlite3.Row) -> Medico:
    return Medico(
        id=row["id"],
        nombre=row["nombre"],
        apellido=row["apellido"],
        especialidad=row["especialidad"],
        telefono=row["telefono"],
    )


def _row_a_cita(row: sqlite3.Row) -> Cita:
    return Cita(
        id=row["id"],
        paciente_id=row["paciente_id"],
        medico_id=row["medico_id"],
        fecha=row["fecha"],
        hora=row["hora"],
        duracion_min=row["duracion_min"],
        estado=EstadoCita(row["estado"]),
        motivo=row["motivo"],
        notas=row["notas"],
        fecha_confirmacion=row["fecha_confirmacion"],
        fecha_cancelacion=row["fecha_cancelacion"],
        cita_original_id=row["cita_original_id"],
    )


def _row_a_mensaje(row: sqlite3.Row) -> MensajeLog:
    return MensajeLog(
        id=row["id"],
        cita_id=row["cita_id"],
        paciente_id=row["paciente_id"],
        canal=TipoContacto(row["canal"]),
        mensaje=row["mensaje"],
        timestamp=row["timestamp"],
        estado_envio=row["estado_envio"],
        respuesta_paciente=row["respuesta_paciente"],
    )

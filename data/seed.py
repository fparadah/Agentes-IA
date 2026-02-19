"""
Datos de prueba para el sistema de agenda clinica.
Carga pacientes, medicos y citas de ejemplo en la base de datos.
Ejecutar: python -m data.seed
"""

import uuid
from datetime import datetime, timedelta

from src import database as db
from src.models import Cita, EstadoCita, Medico, Paciente, TipoContacto


def generar_id() -> str:
    return str(uuid.uuid4())[:8]


def cargar_datos_prueba() -> None:
    db.inicializar_db()

    print("Cargando datos de prueba...")

    # ------------------------------------------------------------------
    # Medicos
    # ------------------------------------------------------------------
    medicos = [
        Medico(
            id="med001",
            nombre="Carolina",
            apellido="Vargas",
            especialidad="Medicina General",
            telefono="+56912345678",
        ),
        Medico(
            id="med002",
            nombre="Roberto",
            apellido="Soto",
            especialidad="Traumatologia",
            telefono="+56987654321",
        ),
        Medico(
            id="med003",
            nombre="Ana",
            apellido="Muñoz",
            especialidad="Nutricion",
            telefono="+56911223344",
        ),
    ]

    for medico in medicos:
        try:
            db.crear_medico(medico)
            print(f"  Medico: {medico.nombre_completo} ({medico.especialidad})")
        except Exception:
            print(f"  Medico ya existe: {medico.nombre_completo}")

    # ------------------------------------------------------------------
    # Pacientes
    # ------------------------------------------------------------------
    pacientes = [
        Paciente(
            id="pac001",
            nombre="Maria",
            apellido="Gonzalez",
            telefono="+56922334455",
            email="maria.gonzalez@email.com",
            rut="12.345.678-9",
            canal_preferido=TipoContacto.WHATSAPP,
        ),
        Paciente(
            id="pac002",
            nombre="Juan",
            apellido="Perez",
            telefono="+56933445566",
            email="juan.perez@email.com",
            rut="11.222.333-4",
            canal_preferido=TipoContacto.WHATSAPP,
        ),
        Paciente(
            id="pac003",
            nombre="Sofia",
            apellido="Torres",
            telefono="+56944556677",
            email="sofia.torres@email.com",
            rut="15.678.901-2",
            canal_preferido=TipoContacto.SMS,
        ),
        Paciente(
            id="pac004",
            nombre="Carlos",
            apellido="Ramirez",
            telefono="+56955667788",
            email="carlos.ramirez@email.com",
            rut="10.111.222-3",
            canal_preferido=TipoContacto.WHATSAPP,
        ),
        Paciente(
            id="pac005",
            nombre="Valentina",
            apellido="Lopez",
            telefono="+56966778899",
            email="valentina.lopez@email.com",
            rut="16.789.012-3",
            canal_preferido=TipoContacto.WHATSAPP,
        ),
    ]

    for paciente in pacientes:
        try:
            db.crear_paciente(paciente)
            print(f"  Paciente: {paciente.nombre_completo} ({paciente.telefono})")
        except Exception:
            print(f"  Paciente ya existe: {paciente.nombre_completo}")

    # ------------------------------------------------------------------
    # Citas (fechas relativas a hoy para que siempre sean relevantes)
    # ------------------------------------------------------------------
    hoy = datetime.now()
    manana = hoy + timedelta(days=1)
    pasado = hoy + timedelta(days=2)
    semana = hoy + timedelta(days=7)

    def fmt(dt: datetime) -> str:
        return dt.strftime("%Y-%m-%d")

    citas = [
        # Citas para hoy
        Cita(
            id="cita001",
            paciente_id="pac001",
            medico_id="med001",
            fecha=fmt(hoy),
            hora="09:00",
            duracion_min=30,
            estado=EstadoCita.AGENDADO,
            motivo="Control general",
        ),
        Cita(
            id="cita002",
            paciente_id="pac002",
            medico_id="med001",
            fecha=fmt(hoy),
            hora="10:30",
            duracion_min=30,
            estado=EstadoCita.CONFIRMADO,
            motivo="Revision resultado examenes",
            fecha_confirmacion=hoy.isoformat(),
        ),
        Cita(
            id="cita003",
            paciente_id="pac003",
            medico_id="med002",
            fecha=fmt(hoy),
            hora="11:00",
            duracion_min=45,
            estado=EstadoCita.AGENDADO,
            motivo="Dolor rodilla",
        ),
        # Citas para manana
        Cita(
            id="cita004",
            paciente_id="pac004",
            medico_id="med001",
            fecha=fmt(manana),
            hora="09:30",
            duracion_min=30,
            estado=EstadoCita.AGENDADO,
            motivo="Chequeo anual",
        ),
        Cita(
            id="cita005",
            paciente_id="pac005",
            medico_id="med003",
            fecha=fmt(manana),
            hora="10:00",
            duracion_min=60,
            estado=EstadoCita.AGENDADO,
            motivo="Primera consulta nutricion",
        ),
        Cita(
            id="cita006",
            paciente_id="pac001",
            medico_id="med003",
            fecha=fmt(pasado),
            hora="14:00",
            duracion_min=60,
            estado=EstadoCita.AGENDADO,
            motivo="Seguimiento dieta",
        ),
        Cita(
            id="cita007",
            paciente_id="pac002",
            medico_id="med002",
            fecha=fmt(semana),
            hora="15:30",
            duracion_min=45,
            estado=EstadoCita.AGENDADO,
            motivo="Post operatorio rodilla",
        ),
    ]

    for cita in citas:
        try:
            db.crear_cita(cita)
            paciente = db.obtener_paciente(cita.paciente_id)
            medico = db.obtener_medico(cita.medico_id)
            nombre_p = paciente.nombre_completo if paciente else cita.paciente_id
            nombre_m = medico.nombre_completo if medico else cita.medico_id
            print(f"  Cita: [{cita.id}] {nombre_p} con {nombre_m} - {cita.fecha} {cita.hora} ({cita.estado.value})")
        except Exception:
            print(f"  Cita ya existe: {cita.id}")

    print("\nDatos de prueba cargados correctamente.")
    print("\nResumen:")
    print(f"  Medicos:   {len(medicos)}")
    print(f"  Pacientes: {len(pacientes)}")
    print(f"  Citas:     {len(citas)}")
    print(f"\nIDs de citas disponibles para pruebas:")
    for cita in citas:
        paciente = db.obtener_paciente(cita.paciente_id)
        print(f"  {cita.id} -> {paciente.nombre_completo if paciente else '?'} el {cita.fecha} {cita.hora} [{cita.estado.value}]")


if __name__ == "__main__":
    cargar_datos_prueba()

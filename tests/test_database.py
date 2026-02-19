"""
Tests para la capa de base de datos.
Ejecutar: python -m pytest tests/ -v
"""

import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Usar DB en memoria / temporal para tests
import os
os.environ.setdefault("CLINIC_TEST_MODE", "1")

from src import database as db
from src.database import DB_PATH
from src.models import Cita, EstadoCita, Medico, Paciente, TipoContacto


@pytest.fixture(autouse=True)
def db_limpia(tmp_path, monkeypatch):
    """Cada test usa una base de datos fresca en directorio temporal."""
    db_temp = tmp_path / "test_clinica.db"
    monkeypatch.setattr(db, "DB_PATH", db_temp)
    db.inicializar_db()
    yield
    if db_temp.exists():
        db_temp.unlink()


def paciente_ejemplo(pid: str = "p001") -> Paciente:
    return Paciente(
        id=pid,
        nombre="Ana",
        apellido="Test",
        telefono=f"+569{pid}",
        canal_preferido=TipoContacto.WHATSAPP,
    )


def medico_ejemplo(mid: str = "m001") -> Medico:
    return Medico(
        id=mid,
        nombre="Carlos",
        apellido="Doctor",
        especialidad="General",
    )


def cita_ejemplo(cid: str = "c001", pid: str = "p001", mid: str = "m001") -> Cita:
    fecha = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    return Cita(
        id=cid,
        paciente_id=pid,
        medico_id=mid,
        fecha=fecha,
        hora="10:00",
        duracion_min=30,
        estado=EstadoCita.AGENDADO,
        motivo="Control",
    )


# ---------------------------------------------------------------------------
# Tests de Pacientes
# ---------------------------------------------------------------------------

class TestPacientes:
    def test_crear_y_obtener_paciente(self):
        p = paciente_ejemplo()
        db.crear_paciente(p)
        obtenido = db.obtener_paciente("p001")
        assert obtenido is not None
        assert obtenido.nombre == "Ana"
        assert obtenido.apellido == "Test"

    def test_buscar_por_telefono(self):
        p = paciente_ejemplo()
        db.crear_paciente(p)
        encontrado = db.buscar_paciente_por_telefono(p.telefono)
        assert encontrado is not None
        assert encontrado.id == p.id

    def test_buscar_por_nombre(self):
        db.crear_paciente(paciente_ejemplo("p001"))
        db.crear_paciente(paciente_ejemplo("p002"))
        resultados = db.buscar_paciente_por_nombre("Ana")
        assert len(resultados) == 2

    def test_obtener_paciente_inexistente(self):
        resultado = db.obtener_paciente("no-existe")
        assert resultado is None

    def test_listar_pacientes(self):
        db.crear_paciente(paciente_ejemplo("p001"))
        db.crear_paciente(paciente_ejemplo("p002"))
        lista = db.listar_pacientes()
        assert len(lista) == 2


# ---------------------------------------------------------------------------
# Tests de Medicos
# ---------------------------------------------------------------------------

class TestMedicos:
    def test_crear_y_obtener_medico(self):
        m = medico_ejemplo()
        db.crear_medico(m)
        obtenido = db.obtener_medico("m001")
        assert obtenido is not None
        assert obtenido.especialidad == "General"

    def test_listar_medicos(self):
        db.crear_medico(medico_ejemplo("m001"))
        db.crear_medico(medico_ejemplo("m002"))
        lista = db.listar_medicos()
        assert len(lista) == 2


# ---------------------------------------------------------------------------
# Tests de Citas
# ---------------------------------------------------------------------------

class TestCitas:
    def _setup(self):
        db.crear_paciente(paciente_ejemplo())
        db.crear_medico(medico_ejemplo())

    def test_crear_cita(self):
        self._setup()
        c = cita_ejemplo()
        db.crear_cita(c)
        obtenida = db.obtener_cita("c001")
        assert obtenida is not None
        assert obtenida.estado == EstadoCita.AGENDADO
        assert obtenida.motivo == "Control"

    def test_confirmar_cita(self):
        self._setup()
        db.crear_cita(cita_ejemplo())
        cita = db.confirmar_cita("c001")
        assert cita is not None
        assert cita.estado == EstadoCita.CONFIRMADO
        assert cita.fecha_confirmacion is not None

    def test_confirmar_cita_ya_confirmada(self):
        """Confirmar dos veces no rompe nada, solo el primer cambio tiene efecto."""
        self._setup()
        db.crear_cita(cita_ejemplo())
        db.confirmar_cita("c001")
        cita = db.confirmar_cita("c001")
        # La cita sigue confirmada, no hay error
        assert cita.estado == EstadoCita.CONFIRMADO

    def test_cancelar_cita(self):
        self._setup()
        db.crear_cita(cita_ejemplo())
        cita = db.cancelar_cita("c001", "No puede asistir")
        assert cita is not None
        assert cita.estado == EstadoCita.CANCELADO
        assert cita.fecha_cancelacion is not None

    def test_reagendar_cita(self):
        self._setup()
        db.crear_cita(cita_ejemplo())
        nueva_fecha = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        nueva_cita = db.reagendar_cita("c001", nueva_fecha, "15:00")
        assert nueva_cita is not None
        assert nueva_cita.fecha == nueva_fecha
        assert nueva_cita.hora == "15:00"
        assert nueva_cita.estado == EstadoCita.AGENDADO
        assert nueva_cita.cita_original_id == "c001"

        # La cita original debe estar marcada como reagendada
        original = db.obtener_cita("c001")
        assert original.estado == EstadoCita.REAGENDADO

    def test_obtener_citas_paciente(self):
        self._setup()
        db.crear_cita(cita_ejemplo("c001"))
        fecha2 = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        c2 = Cita("c002", "p001", "m001", fecha2, "11:00", 30, EstadoCita.AGENDADO, "Seguimiento")
        db.crear_cita(c2)
        citas = db.obtener_citas_paciente("p001")
        assert len(citas) == 2

    def test_obtener_citas_por_estado(self):
        self._setup()
        db.crear_cita(cita_ejemplo("c001"))
        db.confirmar_cita("c001")
        db.crear_cita(cita_ejemplo("c002"))

        agendadas = db.obtener_citas_por_estado(EstadoCita.AGENDADO)
        confirmadas = db.obtener_citas_por_estado(EstadoCita.CONFIRMADO)
        assert len(agendadas) == 1
        assert len(confirmadas) == 1

    def test_obtener_citas_por_fecha(self):
        self._setup()
        hoy = datetime.now().strftime("%Y-%m-%d")
        c = Cita("c001", "p001", "m001", hoy, "09:00", 30, EstadoCita.AGENDADO, "Hoy")
        db.crear_cita(c)
        citas = db.obtener_citas_por_fecha(hoy)
        assert len(citas) == 1
        assert citas[0].id == "c001"


# ---------------------------------------------------------------------------
# Tests de Mensajes Log
# ---------------------------------------------------------------------------

class TestMensajes:
    def test_registrar_mensaje(self):
        db.crear_paciente(paciente_ejemplo())
        db.crear_medico(medico_ejemplo())
        db.crear_cita(cita_ejemplo())
        log = db.registrar_mensaje(
            cita_id="c001",
            paciente_id="p001",
            canal=TipoContacto.WHATSAPP,
            mensaje="Hola! Confirmamos tu cita.",
        )
        assert log.id is not None
        assert log.estado_envio == "simulado"

    def test_obtener_mensajes_cita(self):
        db.crear_paciente(paciente_ejemplo())
        db.crear_medico(medico_ejemplo())
        db.crear_cita(cita_ejemplo())
        db.registrar_mensaje("c001", "p001", TipoContacto.WHATSAPP, "Mensaje 1")
        db.registrar_mensaje("c001", "p001", TipoContacto.WHATSAPP, "Mensaje 2")
        mensajes = db.obtener_mensajes_cita("c001")
        assert len(mensajes) == 2

"""
Tests para las herramientas del agente.
Ejecutar: python -m pytest tests/ -v
"""

from datetime import datetime, timedelta

import pytest

from src import database as db
from src.models import Cita, EstadoCita, Medico, Paciente, TipoContacto
from src.tools import (
    herramienta_buscar_citas_paciente,
    herramienta_cancelar_cita,
    herramienta_confirmar_cita,
    herramienta_enviar_mensaje_paciente,
    herramienta_listar_citas_del_dia,
    herramienta_listar_citas_pendientes,
    herramienta_obtener_detalle_cita,
    herramienta_reagendar_cita,
    herramienta_registrar_respuesta_paciente,
)


@pytest.fixture(autouse=True)
def db_con_datos(tmp_path, monkeypatch):
    """Prepara una DB temporal con datos para cada test."""
    db_temp = tmp_path / "test_tools.db"
    monkeypatch.setattr(db, "DB_PATH", db_temp)
    db.inicializar_db()

    # Paciente
    db.crear_paciente(Paciente(
        id="p01", nombre="Laura", apellido="Gomez",
        telefono="+56911111111", canal_preferido=TipoContacto.WHATSAPP,
    ))
    # Medico
    db.crear_medico(Medico(
        id="m01", nombre="Pedro", apellido="Medina", especialidad="General"
    ))
    # Cita agendada
    manana = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    db.crear_cita(Cita(
        id="ct01", paciente_id="p01", medico_id="m01",
        fecha=manana, hora="10:00", duracion_min=30,
        estado=EstadoCita.AGENDADO, motivo="Control",
    ))
    yield
    if db_temp.exists():
        db_temp.unlink()


# ---------------------------------------------------------------------------
# Tests de herramientas de consulta
# ---------------------------------------------------------------------------

class TestBuscarCitas:
    def test_buscar_por_nombre(self):
        res = herramienta_buscar_citas_paciente("Laura")
        assert res["encontrado"] is True
        assert res["total"] == 1

    def test_buscar_por_telefono(self):
        res = herramienta_buscar_citas_paciente("+56911111111")
        assert res["encontrado"] is True
        assert res["total"] == 1

    def test_buscar_inexistente(self):
        res = herramienta_buscar_citas_paciente("NoExiste")
        assert res["encontrado"] is False
        assert res["total"] == 0

    def test_buscar_excluye_canceladas(self):
        db.cancelar_cita("ct01")
        res = herramienta_buscar_citas_paciente("Laura")
        assert res["total"] == 0  # cancelada no aparece


class TestDetalleCita:
    def test_detalle_existente(self):
        res = herramienta_obtener_detalle_cita("ct01")
        assert res["cita_id"] == "ct01"
        assert res["paciente"] == "Laura Gomez"
        assert res["medico"] == "Dr(a). Pedro Medina"
        assert "error" not in res

    def test_detalle_inexistente(self):
        res = herramienta_obtener_detalle_cita("no-existe")
        assert "error" in res


class TestListarCitas:
    def test_listar_del_dia_sin_citas(self):
        res = herramienta_listar_citas_del_dia("2000-01-01")
        assert res["total"] == 0

    def test_listar_pendientes(self):
        res = herramienta_listar_citas_pendientes()
        assert res["total"] == 1

    def test_listar_pendientes_vacio_tras_confirmar(self):
        db.confirmar_cita("ct01")
        res = herramienta_listar_citas_pendientes()
        assert res["total"] == 0


# ---------------------------------------------------------------------------
# Tests de herramientas de accion
# ---------------------------------------------------------------------------

class TestConfirmarCita:
    def test_confirmar_exitoso(self):
        res = herramienta_confirmar_cita("ct01")
        assert res["exito"] is True
        cita = db.obtener_cita("ct01")
        assert cita.estado == EstadoCita.CONFIRMADO

    def test_confirmar_ya_confirmada(self):
        db.confirmar_cita("ct01")
        res = herramienta_confirmar_cita("ct01")
        assert res["exito"] is False

    def test_confirmar_inexistente(self):
        res = herramienta_confirmar_cita("no-existe")
        assert res["exito"] is False


class TestCancelarCita:
    def test_cancelar_exitoso(self):
        res = herramienta_cancelar_cita("ct01", "No puede asistir")
        assert res["exito"] is True
        cita = db.obtener_cita("ct01")
        assert cita.estado == EstadoCita.CANCELADO

    def test_cancelar_ya_cancelada(self):
        db.cancelar_cita("ct01")
        res = herramienta_cancelar_cita("ct01")
        assert res["exito"] is False

    def test_cancelar_inexistente(self):
        res = herramienta_cancelar_cita("no-existe")
        assert res["exito"] is False


class TestReagendarCita:
    def test_reagendar_exitoso(self):
        nueva_fecha = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        res = herramienta_reagendar_cita("ct01", nueva_fecha, "14:30")
        assert res["exito"] is True
        nueva = res["nueva_cita"]
        assert nueva["fecha"] == nueva_fecha
        assert nueva["hora"] == "14:30"

    def test_reagendar_formato_invalido(self):
        res = herramienta_reagendar_cita("ct01", "25/12/2025", "10h00")
        assert res["exito"] is False

    def test_reagendar_cita_cancelada(self):
        db.cancelar_cita("ct01")
        nueva_fecha = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        res = herramienta_reagendar_cita("ct01", nueva_fecha, "14:00")
        assert res["exito"] is False

    def test_reagendar_inexistente(self):
        res = herramienta_reagendar_cita("no-existe", "2025-12-25", "10:00")
        assert res["exito"] is False


class TestEnviarMensaje:
    def test_enviar_mensaje_simulado(self):
        res = herramienta_enviar_mensaje_paciente(
            "ct01", "Hola Laura! Recordamos tu cita manana.", "whatsapp"
        )
        assert res["exito"] is True
        assert res["destinatario"] == "Laura Gomez"
        assert "SIMULADO" in res["nota"]

    def test_enviar_a_cita_inexistente(self):
        res = herramienta_enviar_mensaje_paciente("no-existe", "Hola")
        assert res["exito"] is False


class TestRegistrarRespuesta:
    def test_registrar_respuesta(self):
        res = herramienta_registrar_respuesta_paciente("ct01", "Si, confirmo")
        assert res["exito"] is True
        assert res["paciente"] == "Laura Gomez"

    def test_registrar_respuesta_cita_inexistente(self):
        res = herramienta_registrar_respuesta_paciente("no-existe", "Si")
        assert res["exito"] is False

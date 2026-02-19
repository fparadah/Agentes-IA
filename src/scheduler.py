"""
Scheduler de confirmaciones proactivas.

Simula el trabajo que hara el proceso automatico que se ejecuta
cada dia (ej: a las 10:00 AM) y contacta a los pacientes con cita
al dia siguiente para que confirmen su asistencia.

Flujo:
  1. Consulta la agenda del dia siguiente (hoy = Mydoc, ahora = SQLite)
  2. Para cada cita en estado "agendado":
     a. Envia mensaje WhatsApp al paciente
     b. Registra el envio en el log
  3. Las respuestas de los pacientes llegan via webhook (ver webhook.py)
  4. Si no responden en X horas -> segunda notificacion o libera el slot

Ejecutar manualmente para pruebas:
  python -m src.scheduler
  python -m src.scheduler --fecha 2026-02-20
"""

import argparse
from datetime import datetime, timedelta
from typing import Optional

from src import database as db
from src.models import Cita, EstadoCita, Paciente, Medico
from src.tools import herramienta_enviar_mensaje_paciente


# Configuracion del scheduler
HORAS_ESPERA_RESPUESTA = 4   # horas antes de enviar recordatorio
HORAS_LIMITE_CONFIRMACION = 8  # horas limite para confirmar (o se libera el slot)


def generar_mensaje_confirmacion(
    paciente: Paciente,
    cita: Cita,
    medico: Medico,
) -> str:
    """
    Genera el mensaje de confirmacion para enviar al paciente.
    En produccion, esto deberia ser un Template Message aprobado por Meta.
    """
    return (
        f"Hola {paciente.nombre}! 👋\n\n"
        f"Te recordamos que tienes una cita agendada para *manana*:\n\n"
        f"📅 {cita.fecha_hora_display.capitalize()}\n"
        f"👨‍⚕️ {medico.nombre_completo}\n"
        f"🏥 Motivo: {cita.motivo}\n\n"
        f"Por favor confirma tu asistencia respondiendo:\n"
        f"✅ *SI* para confirmar\n"
        f"❌ *NO* si no puedes asistir\n"
        f"🔄 *CAMBIAR* si necesitas otro horario\n\n"
        f"ID de tu cita: {cita.id}"
    )


def generar_mensaje_recordatorio(
    paciente: Paciente,
    cita: Cita,
    medico: Medico,
) -> str:
    """Segundo mensaje si no responde al primero."""
    return (
        f"Hola {paciente.nombre}, aun no hemos recibido tu confirmacion "
        f"para la cita de manana con {medico.nombre_completo} "
        f"a las {cita.hora}. "
        f"Si no confirmamos dentro de poco, el cupo podria quedar disponible "
        f"para otro paciente. Responde SI para confirmar o NO para cancelar. "
        f"Gracias!"
    )


def procesar_citas_del_dia_siguiente(
    fecha_objetivo: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """
    Proceso principal del scheduler.

    Args:
        fecha_objetivo: fecha a procesar (YYYY-MM-DD). Si None, usa manana.
        dry_run: si True, muestra lo que haria pero no ejecuta nada.

    Returns:
        dict con estadisticas del proceso.
    """
    if not fecha_objetivo:
        fecha_objetivo = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"\n{'='*60}")
    print(f"  SCHEDULER DE CONFIRMACIONES")
    print(f"  Procesando citas para: {fecha_objetivo}")
    print(f"  Modo: {'DRY RUN (sin envios)' if dry_run else 'REAL'}")
    print(f"{'='*60}\n")

    # 1. Obtener citas del dia siguiente en estado "agendado"
    citas = db.obtener_citas_por_fecha(fecha_objetivo)
    citas_pendientes = [c for c in citas if c.estado == EstadoCita.AGENDADO]

    print(f"  Citas encontradas para {fecha_objetivo}: {len(citas)}")
    print(f"  Pendientes de confirmar: {len(citas_pendientes)}")
    print(f"  Ya confirmadas: {len([c for c in citas if c.estado == EstadoCita.CONFIRMADO])}")
    print()

    if not citas_pendientes:
        print("  No hay citas pendientes. El scheduler no tiene trabajo hoy.")
        return {
            "fecha": fecha_objetivo,
            "total_citas": len(citas),
            "pendientes": 0,
            "mensajes_enviados": 0,
            "errores": 0,
        }

    enviados = 0
    errores = 0

    for cita in citas_pendientes:
        paciente = db.obtener_paciente(cita.paciente_id)
        medico = db.obtener_medico(cita.medico_id)

        if not paciente or not medico:
            print(f"  [ERROR] Cita {cita.id}: paciente o medico no encontrado")
            errores += 1
            continue

        mensaje = generar_mensaje_confirmacion(paciente, cita, medico)

        print(f"  Cita [{cita.id}] -> {paciente.nombre_completo} ({paciente.telefono})")

        if dry_run:
            print(f"  [DRY RUN] Mensaje que se enviaria:")
            for linea in mensaje.split("\n"):
                print(f"    {linea}")
            print()
        else:
            resultado = herramienta_enviar_mensaje_paciente(
                cita_id=cita.id,
                mensaje=mensaje,
                canal=paciente.canal_preferido.value,
            )
            if resultado.get("exito"):
                print(f"    OK - Mensaje enviado via {resultado['canal']}")
                enviados += 1
            else:
                print(f"    ERROR - {resultado.get('mensaje', 'Error desconocido')}")
                errores += 1

    print(f"\n{'='*60}")
    print(f"  Resultado: {enviados} enviados, {errores} errores")
    print(f"{'='*60}")

    return {
        "fecha": fecha_objetivo,
        "total_citas": len(citas),
        "pendientes": len(citas_pendientes),
        "mensajes_enviados": enviados,
        "errores": errores,
    }


def simular_respuestas_pacientes(fecha_objetivo: Optional[str] = None) -> None:
    """
    Simula las respuestas de los pacientes para pruebas.
    En produccion, esto llega via webhook de WhatsApp.

    Simula que:
    - 70% de pacientes confirman con SI
    - 20% no responden (timeout)
    - 10% cancelan o piden cambio
    """
    import random

    if not fecha_objetivo:
        fecha_objetivo = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    citas = db.obtener_citas_por_fecha(fecha_objetivo)
    citas_pendientes = [c for c in citas if c.estado == EstadoCita.AGENDADO]

    print(f"\n  Simulando respuestas de {len(citas_pendientes)} pacientes...\n")

    for cita in citas_pendientes:
        paciente = db.obtener_paciente(cita.paciente_id)
        if not paciente:
            continue

        # Simular respuesta aleatoria
        respuesta_random = random.random()

        if respuesta_random < 0.70:
            # Confirma
            respuesta = "SI"
            db.confirmar_cita(cita.id)
            db.registrar_mensaje(
                cita_id=cita.id,
                paciente_id=paciente.id,
                canal=paciente.canal_preferido,
                mensaje=f"[RESPUESTA PACIENTE] {respuesta}",
                respuesta=respuesta,
            )
            print(f"  [{cita.id}] {paciente.nombre_completo}: CONFIRMO")

        elif respuesta_random < 0.90:
            # No responde (se manejaria con timeout)
            print(f"  [{cita.id}] {paciente.nombre_completo}: SIN RESPUESTA (timeout)")

        else:
            # Cancela
            respuesta = "NO, no puedo asistir"
            db.cancelar_cita(cita.id, "Paciente cancelo via WhatsApp")
            db.registrar_mensaje(
                cita_id=cita.id,
                paciente_id=paciente.id,
                canal=paciente.canal_preferido,
                mensaje=f"[RESPUESTA PACIENTE] {respuesta}",
                respuesta=respuesta,
            )
            print(f"  [{cita.id}] {paciente.nombre_completo}: CANCELO")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scheduler de confirmaciones de citas")
    parser.add_argument("--fecha", help="Fecha a procesar (YYYY-MM-DD). Default: manana")
    parser.add_argument("--dry-run", action="store_true", help="Solo muestra, no envia")
    parser.add_argument("--simular", action="store_true", help="Simula respuestas de pacientes")
    args = parser.parse_args()

    db.inicializar_db()

    stats = procesar_citas_del_dia_siguiente(
        fecha_objetivo=args.fecha,
        dry_run=args.dry_run,
    )

    if args.simular and not args.dry_run:
        simular_respuestas_pacientes(fecha_objetivo=args.fecha)
        print("\n  Estado final de citas:")
        fecha = args.fecha or (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        for cita in db.obtener_citas_por_fecha(fecha):
            paciente = db.obtener_paciente(cita.paciente_id)
            nombre = paciente.nombre_completo if paciente else "?"
            print(f"  [{cita.id}] {nombre}: {cita.estado.value.upper()}")

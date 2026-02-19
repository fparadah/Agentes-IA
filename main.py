"""
Interfaz CLI para probar el agente de agenda clinica.

Modos de uso:
  python main.py              -> Chat interactivo con el agente
  python main.py --seed       -> Carga datos de prueba y sale
  python main.py --listar     -> Muestra todas las citas en la DB
  python main.py --escenario  -> Ejecuta escenarios de prueba automaticos
  python main.py --debug      -> Chat interactivo con debug activado
"""

import argparse
import json
import os
import sys
from datetime import datetime

from src import database as db
from src.models import EstadoCita


# ---------------------------------------------------------------------------
# Helpers de visualizacion
# ---------------------------------------------------------------------------

def separador(char: str = "─", ancho: int = 60) -> str:
    return char * ancho


def encabezado(titulo: str) -> None:
    print(f"\n{separador('═')}")
    print(f"  {titulo}")
    print(f"{separador('═')}\n")


def imprimir_cita(cita_data: dict) -> None:
    print(f"  ID:        {cita_data.get('cita_id', '?')}")
    print(f"  Estado:    {cita_data.get('estado', '?').upper()}")
    print(f"  Paciente:  {cita_data.get('paciente', '?')}")
    print(f"  Medico:    {cita_data.get('medico', '?')}")
    print(f"  Fecha:     {cita_data.get('fecha_hora', cita_data.get('fecha', '?'))}")
    print(f"  Motivo:    {cita_data.get('motivo', '?')}")


def mostrar_herramientas_usadas(herramientas: list[dict]) -> None:
    if not herramientas:
        return
    print(f"\n  {separador('-', 40)}")
    print(f"  [Acciones realizadas: {len(herramientas)}]")
    for h in herramientas:
        resultado = h.get("resultado", {})
        exito = resultado.get("exito", resultado.get("encontrado", True))
        icono = "OK" if exito else "!!"
        print(f"  [{icono}] {h['herramienta']}")
    print(f"  {separador('-', 40)}")


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------

def cmd_seed() -> None:
    """Inicializa la DB con datos de prueba."""
    db.inicializar_db()
    from data.seed import cargar_datos_prueba
    cargar_datos_prueba()


def cmd_listar() -> None:
    """Muestra todas las citas en la base de datos."""
    db.inicializar_db()
    encabezado("CITAS EN EL SISTEMA")

    citas = db.listar_todas_citas()
    if not citas:
        print("  No hay citas registradas. Ejecuta: python main.py --seed")
        return

    estados_orden = {
        EstadoCita.AGENDADO: 0,
        EstadoCita.CONFIRMADO: 1,
        EstadoCita.REAGENDADO: 2,
        EstadoCita.CANCELADO: 3,
        EstadoCita.COMPLETADO: 4,
    }

    for cita in citas:
        paciente = db.obtener_paciente(cita.paciente_id)
        medico = db.obtener_medico(cita.medico_id)
        estado_label = cita.estado.value.upper().ljust(12)
        nombre_p = paciente.nombre_completo if paciente else "?"
        nombre_m = medico.nombre_completo if medico else "?"
        tel = paciente.telefono if paciente else ""

        print(f"  [{cita.id}] {estado_label} | {cita.fecha} {cita.hora} | {nombre_p} ({tel}) | {nombre_m}")

    print(f"\n  Total: {len(citas)} citas")


def cmd_escenarios() -> None:
    """
    Ejecuta escenarios de prueba automaticos SIN el agente IA.
    Prueba directamente las funciones de la base de datos.
    """
    encabezado("ESCENARIOS DE PRUEBA AUTOMATICOS")

    # Asegurarse de que hay datos
    db.inicializar_db()
    citas = db.listar_todas_citas()
    if not citas:
        print("  Primero carga datos: python main.py --seed")
        return

    cita_agendada = next((c for c in citas if c.estado == EstadoCita.AGENDADO), None)
    if not cita_agendada:
        print("  No hay citas en estado 'agendado' para probar.")
        return

    print(f"  Usando cita de prueba: {cita_agendada.id}\n")

    # Escenario 1: Confirmar cita
    print(f"{separador('-')}")
    print("ESCENARIO 1: Confirmar una cita")
    print(separador('-'))
    from src.tools import (
        herramienta_confirmar_cita,
        herramienta_enviar_mensaje_paciente,
        herramienta_cancelar_cita,
        herramienta_reagendar_cita,
        herramienta_buscar_citas_paciente,
    )

    resultado = herramienta_confirmar_cita(cita_agendada.id)
    print(f"  Resultado: {resultado}")

    # Escenario 2: Enviar mensaje al paciente
    print(f"\n{separador('-')}")
    print("ESCENARIO 2: Enviar mensaje de confirmacion")
    print(separador('-'))
    cita_det = db.obtener_cita(cita_agendada.id)
    paciente = db.obtener_paciente(cita_det.paciente_id) if cita_det else None
    medico = db.obtener_medico(cita_det.medico_id) if cita_det else None

    if paciente and medico and cita_det:
        mensaje = (
            f"Hola {paciente.nombre}! Te confirmamos tu cita con {medico.nombre_completo} "
            f"el {cita_det.fecha_hora_display}. "
            f"Si necesitas cambiar algo, avisanos con tiempo. Nos vemos pronto!"
        )
        resultado = herramienta_enviar_mensaje_paciente(cita_agendada.id, mensaje)
        print(f"  Para: {resultado.get('destinatario')}")
        print(f"  Via:  {resultado.get('canal')}")
        print(f"  Msg:  {resultado.get('mensaje_enviado')}")

    # Escenario 3: Buscar citas de un paciente
    print(f"\n{separador('-')}")
    print("ESCENARIO 3: Buscar citas por nombre")
    print(separador('-'))
    resultado = herramienta_buscar_citas_paciente("Maria")
    print(f"  Encontradas: {resultado.get('total')} citas")
    for c in resultado.get("citas", []):
        print(f"  - [{c['cita_id']}] {c['fecha_hora']} ({c['estado']})")

    # Escenario 4: Reagendar
    print(f"\n{separador('-')}")
    print("ESCENARIO 4: Reagendar una cita")
    print(separador('-'))
    # Buscar otra cita agendada
    otra_cita = next(
        (c for c in db.listar_todas_citas()
         if c.estado == EstadoCita.AGENDADO and c.id != cita_agendada.id),
        None
    )
    if otra_cita:
        from datetime import timedelta
        nueva_fecha = (
            datetime.strptime(otra_cita.fecha, "%Y-%m-%d") + timedelta(days=3)
        ).strftime("%Y-%m-%d")
        resultado = herramienta_reagendar_cita(otra_cita.id, nueva_fecha, "11:00")
        print(f"  Cita original {otra_cita.id} -> reagendada")
        if resultado.get("exito"):
            nueva = resultado.get("nueva_cita", {})
            print(f"  Nueva cita: [{nueva.get('cita_id')}] {nueva.get('fecha_hora')}")
    else:
        print("  No hay mas citas agendadas para probar reagendamiento.")

    print(f"\n{separador('═')}")
    print("  Todos los escenarios completados.")
    print(separador('═'))


def cmd_chat(debug: bool = False) -> None:
    """Modo chat interactivo con el agente."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("\nERROR: No se encontro ANTHROPIC_API_KEY en las variables de entorno.")
        print("Configura tu API key:")
        print("  export ANTHROPIC_API_KEY='tu-api-key-aqui'")
        print("\nO copia el archivo .env.example a .env y completa los valores.")
        sys.exit(1)

    db.inicializar_db()
    citas = db.listar_todas_citas()
    if not citas:
        print("\nNo hay datos en la base de datos.")
        print("Carga datos de prueba primero: python main.py --seed\n")

    from src.agent import AgenteAgenda
    agente = AgenteAgenda(api_key=api_key, modo_debug=debug)

    encabezado("SISTEMA DE AGENDA CLINICA - MODO CHAT")
    print("  Comandos especiales:")
    print("    /salir     -> Terminar sesion")
    print("    /nuevo     -> Nueva conversacion (limpia historial)")
    print("    /listar    -> Ver todas las citas")
    print("    /historial -> Ver historial de la conversacion")
    print()
    print("  Ejemplos de prueba:")
    print("    'Cuales son las citas pendientes de confirmar?'")
    print("    'Busca las citas de Maria Gonzalez'")
    print("    'Confirma la cita cita001'")
    print("    'Cancela la cita cita003'")
    print("    'Reagenda la cita cita004 para pasado manana a las 15:00'")
    print()

    while True:
        try:
            entrada = input("Tú: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nCerrando sesion. Hasta luego!")
            break

        if not entrada:
            continue

        if entrada.lower() == "/salir":
            print("Hasta luego!")
            break

        if entrada.lower() == "/nuevo":
            agente.limpiar_historial()
            print("[Conversacion reiniciada]\n")
            continue

        if entrada.lower() == "/listar":
            cmd_listar()
            continue

        if entrada.lower() == "/historial":
            historial = agente.exportar_historial()
            print(f"\n[Historial: {len(historial)} mensajes]\n")
            for i, msg in enumerate(historial):
                rol = msg.get("role", "?").upper()
                contenido = msg.get("content", "")
                if isinstance(contenido, str):
                    print(f"  [{i}] {rol}: {contenido[:100]}...")
                elif isinstance(contenido, list):
                    for bloque in contenido:
                        if isinstance(bloque, dict):
                            tipo = bloque.get("type", "?")
                            print(f"  [{i}] {rol} [{tipo}]")
            print()
            continue

        # Enviar al agente
        try:
            print("\nValeria: ", end="", flush=True)
            respuesta, herramientas = agente.responder(entrada)
            print(respuesta)
            mostrar_herramientas_usadas(herramientas)
            print()
        except anthropic.AuthenticationError:
            print("\nERROR: API key invalida. Verifica tu ANTHROPIC_API_KEY.")
        except anthropic.RateLimitError:
            print("\nERROR: Limite de rate alcanzado. Espera un momento.")
        except Exception as e:
            print(f"\nERROR: {e}")
            if debug:
                import traceback
                traceback.print_exc()


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sistema de Agenda Clinica - Herramienta de pruebas"
    )
    parser.add_argument("--seed", action="store_true", help="Carga datos de prueba")
    parser.add_argument("--listar", action="store_true", help="Lista todas las citas")
    parser.add_argument("--escenario", action="store_true", help="Ejecuta escenarios de prueba")
    parser.add_argument("--debug", action="store_true", help="Activa modo debug en el chat")
    args = parser.parse_args()

    if args.seed:
        cmd_seed()
    elif args.listar:
        cmd_listar()
    elif args.escenario:
        cmd_escenarios()
    else:
        # Importar aqui para el bloque de error en cmd_chat
        try:
            import anthropic
        except ImportError:
            print("ERROR: Libreria 'anthropic' no instalada.")
            print("Ejecuta: pip install -r requirements.txt")
            sys.exit(1)
        cmd_chat(debug=args.debug)


if __name__ == "__main__":
    main()

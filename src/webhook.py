"""
Manejador de mensajes entrantes de WhatsApp.

Simula el webhook que en produccion recibiria los mensajes
de los pacientes desde WhatsApp Business API.

Dos tipos de mensajes entrantes:
  A) Respuestas a confirmaciones (SI / NO / CAMBIAR)
  B) Conversaciones nuevas (el paciente escribe sin contexto previo)

En produccion, este modulo sera un endpoint HTTP (FastAPI/Flask)
que Meta llamara cada vez que un paciente escribe al numero de WhatsApp.

Ejecutar simulacion:
  python -m src.webhook
"""

import json
import re
from datetime import datetime
from typing import Optional

from src import database as db
from src.models import EstadoCita, TipoContacto
from src.tools import herramienta_enviar_mensaje_paciente


# ---------------------------------------------------------------------------
# Parser de respuestas simples (confirmacion/cancelacion)
# ---------------------------------------------------------------------------

RESPUESTAS_CONFIRMAR = {"si", "sí", "si!", "sí!", "confirmo", "confirmado", "ok", "dale", "claro", "voy"}
RESPUESTAS_CANCELAR = {"no", "no puedo", "cancela", "cancelar", "no voy"}
RESPUESTAS_CAMBIAR = {"cambiar", "cambio", "reagendar", "reagenda", "otro dia", "otro horario"}


def clasificar_respuesta(texto: str) -> str:
    """
    Clasifica el texto de un mensaje en: confirmar | cancelar | cambiar | libre
    """
    texto_norm = texto.lower().strip().rstrip("!.?,")

    if texto_norm in RESPUESTAS_CONFIRMAR:
        return "confirmar"
    if texto_norm in RESPUESTAS_CANCELAR:
        return "cancelar"
    if texto_norm in RESPUESTAS_CAMBIAR:
        return "cambiar"

    # Buscar patrones parciales
    if re.search(r"\bsi\b|\bsí\b|confirm|asist", texto_norm):
        return "confirmar"
    if re.search(r"\bno\b|cancel|no puedo|no voy", texto_norm):
        return "cancelar"
    if re.search(r"cambiar|reagendar|otro dia|otro horario|diferente", texto_norm):
        return "cambiar"

    return "libre"  # Mensaje libre -> va al agente conversacional


# ---------------------------------------------------------------------------
# Manejador de mensajes entrantes
# ---------------------------------------------------------------------------

class ManejadorWhatsApp:
    """
    Procesa mensajes entrantes de pacientes.

    En produccion:
    - Recibe el payload JSON de Meta WhatsApp Cloud API
    - Identifica al paciente por numero de telefono
    - Si es respuesta a confirmacion: procesa directamente
    - Si es mensaje libre: pasa al agente conversacional
    """

    def __init__(self, usar_agente: bool = True):
        self.usar_agente = usar_agente
        self._agente = None  # lazy init

    def _get_agente(self):
        if self._agente is None:
            import os
            from src.agent import AgenteAgenda
            self._agente = AgenteAgenda(
                api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
                modo_debug=False,
            )
        return self._agente

    def procesar_mensaje(
        self,
        telefono: str,
        texto: str,
        timestamp: Optional[str] = None,
    ) -> dict:
        """
        Punto de entrada principal. Procesa un mensaje de un numero de telefono.

        Args:
            telefono: numero del paciente (ej: +56922334455)
            texto: texto del mensaje
            timestamp: cuando llego el mensaje

        Returns:
            dict con la respuesta a enviar al paciente y acciones realizadas
        """
        if not timestamp:
            timestamp = datetime.now().isoformat()

        print(f"\n  [WEBHOOK] Mensaje de {telefono}: '{texto}'")

        # 1. Identificar al paciente
        paciente = db.buscar_paciente_por_telefono(telefono)

        if not paciente:
            # Paciente desconocido
            respuesta = (
                "Hola! Soy el asistente del centro clinico. "
                "No encontramos tu numero en nuestro sistema. "
                "Si eres paciente nuestro, contactanos al telefono de recepcion. "
                "Gracias!"
            )
            return {
                "accion": "paciente_no_encontrado",
                "telefono": telefono,
                "respuesta": respuesta,
            }

        # 2. Buscar si hay una cita pendiente de confirmacion
        citas_activas = [
            c for c in db.obtener_citas_paciente(paciente.id)
            if c.estado == EstadoCita.AGENDADO
        ]

        # 3. Clasificar el tipo de mensaje
        tipo = clasificar_respuesta(texto)
        print(f"  [WEBHOOK] Tipo de respuesta: {tipo} | Paciente: {paciente.nombre_completo}")

        # 4. Manejar segun tipo
        if tipo == "confirmar" and citas_activas:
            return self._manejar_confirmacion(paciente, citas_activas[0])

        if tipo == "cancelar" and citas_activas:
            return self._manejar_cancelacion(paciente, citas_activas[0])

        if tipo == "cambiar" and citas_activas:
            return self._manejar_solicitud_cambio(paciente, citas_activas[0])

        # 5. Mensaje libre: pasar al agente conversacional
        return self._manejar_conversacion_libre(paciente, texto, citas_activas)

    def _manejar_confirmacion(self, paciente, cita) -> dict:
        """Paciente confirma su cita."""
        db.confirmar_cita(cita.id)
        medico = db.obtener_medico(cita.medico_id)
        nombre_medico = medico.nombre_completo if medico else "el medico"

        respuesta = (
            f"Perfecto {paciente.nombre}! Quedaste confirmado/a para tu cita "
            f"con {nombre_medico} el {cita.fecha_hora_display}. "
            f"Recuerda llegar 10 minutos antes. Nos vemos!"
        )

        herramienta_enviar_mensaje_paciente(cita.id, respuesta)
        db.registrar_mensaje(
            cita_id=cita.id,
            paciente_id=paciente.id,
            canal=TipoContacto.WHATSAPP,
            mensaje=f"[RESPUESTA PACIENTE] SI - confirmo",
            respuesta="SI",
        )

        return {
            "accion": "cita_confirmada",
            "cita_id": cita.id,
            "paciente": paciente.nombre_completo,
            "respuesta": respuesta,
        }

    def _manejar_cancelacion(self, paciente, cita) -> dict:
        """Paciente cancela su cita."""
        db.cancelar_cita(cita.id, "Paciente cancelo via WhatsApp")
        medico = db.obtener_medico(cita.medico_id)
        nombre_medico = medico.nombre_completo if medico else "el medico"

        respuesta = (
            f"Entendido {paciente.nombre}, cancelamos tu cita con "
            f"{nombre_medico} del {cita.fecha_hora_display}. "
            f"Si quieres reagendar para otro dia, puedes escribirnos cuando quieras. "
            f"Cuídate!"
        )

        herramienta_enviar_mensaje_paciente(cita.id, respuesta)
        db.registrar_mensaje(
            cita_id=cita.id,
            paciente_id=paciente.id,
            canal=TipoContacto.WHATSAPP,
            mensaje=f"[RESPUESTA PACIENTE] NO - cancela",
            respuesta="NO",
        )

        return {
            "accion": "cita_cancelada",
            "cita_id": cita.id,
            "paciente": paciente.nombre_completo,
            "respuesta": respuesta,
        }

    def _manejar_solicitud_cambio(self, paciente, cita) -> dict:
        """Paciente quiere cambiar su cita -> pasa al agente."""
        medico = db.obtener_medico(cita.medico_id)
        nombre_medico = medico.nombre_completo if medico else "el medico"

        respuesta_inicial = (
            f"Claro {paciente.nombre}! Te ayudo a cambiar tu cita con "
            f"{nombre_medico} del {cita.fecha_hora_display}. "
            f"Que dia te acomoda mejor?"
        )

        # En produccion: iniciar sesion de conversacion con el agente
        herramienta_enviar_mensaje_paciente(cita.id, respuesta_inicial)

        return {
            "accion": "solicitud_reagendamiento",
            "cita_id": cita.id,
            "paciente": paciente.nombre_completo,
            "respuesta": respuesta_inicial,
            "nota": "Paciente en flujo de reagendamiento - requiere conversacion con agente",
        }

    def _manejar_conversacion_libre(self, paciente, texto, citas_activas) -> dict:
        """
        Mensaje libre o paciente nuevo. Pasa al agente conversacional.
        En produccion, mantendria sesion por numero de telefono.
        """
        if not self.usar_agente:
            # Modo sin agente (para pruebas de webhook sin API key)
            if citas_activas:
                cita = citas_activas[0]
                medico = db.obtener_medico(cita.medico_id)
                respuesta = (
                    f"Hola {paciente.nombre}! Tienes una cita agendada con "
                    f"{medico.nombre_completo if medico else 'el medico'} "
                    f"el {cita.fecha_hora_display}. "
                    f"Responde SI para confirmar, NO para cancelar, o CAMBIAR si necesitas otro horario."
                )
            else:
                respuesta = (
                    f"Hola {paciente.nombre}! No encontramos citas activas para ti. "
                    f"Si quieres agendar una hora, escribenos y te ayudamos."
                )
            return {
                "accion": "mensaje_libre_sin_agente",
                "paciente": paciente.nombre_completo,
                "respuesta": respuesta,
            }

        # Usar agente conversacional (requiere ANTHROPIC_API_KEY)
        try:
            agente = self._get_agente()
            contexto = f"[Paciente: {paciente.nombre_completo}, Tel: {paciente.telefono}]\n{texto}"
            respuesta, herramientas = agente.responder(contexto)

            if citas_activas:
                herramienta_enviar_mensaje_paciente(citas_activas[0].id, respuesta)

            return {
                "accion": "respuesta_agente",
                "paciente": paciente.nombre_completo,
                "respuesta": respuesta,
                "herramientas_usadas": len(herramientas),
            }
        except Exception as e:
            respuesta = (
                f"Hola {paciente.nombre}! En este momento no podemos procesar tu mensaje. "
                f"Por favor llama a recepcion o intentalo mas tarde. Disculpa las molestias!"
            )
            return {
                "accion": "error_agente",
                "error": str(e),
                "respuesta": respuesta,
            }


# ---------------------------------------------------------------------------
# Simulacion de mensajes entrantes para pruebas
# ---------------------------------------------------------------------------

def simular_conversacion_entrante() -> None:
    """
    Simula una serie de mensajes de pacientes para probar el webhook.
    """
    db.inicializar_db()
    manejador = ManejadorWhatsApp(usar_agente=False)

    print("\n" + "="*60)
    print("  SIMULACION DE MENSAJES ENTRANTES (WhatsApp)")
    print("="*60)

    # Escenario 1: Paciente confirma
    print("\n--- Escenario 1: Paciente confirma su cita ---")
    resultado = manejador.procesar_mensaje(
        telefono="+56922334455",  # Maria Gonzalez
        texto="Si, confirmo",
    )
    print(f"  Accion: {resultado['accion']}")
    print(f"  Respuesta: {resultado['respuesta']}")

    # Escenario 2: Paciente cancela
    print("\n--- Escenario 2: Paciente cancela su cita ---")
    resultado = manejador.procesar_mensaje(
        telefono="+56944556677",  # Sofia Torres
        texto="No, no voy a poder ir",
    )
    print(f"  Accion: {resultado['accion']}")
    print(f"  Respuesta: {resultado['respuesta']}")

    # Escenario 3: Paciente quiere cambiar
    print("\n--- Escenario 3: Paciente quiere reagendar ---")
    resultado = manejador.procesar_mensaje(
        telefono="+56955667788",  # Carlos Ramirez
        texto="Quiero cambiar mi hora",
    )
    print(f"  Accion: {resultado['accion']}")
    print(f"  Respuesta: {resultado['respuesta']}")

    # Escenario 4: Numero desconocido
    print("\n--- Escenario 4: Numero desconocido ---")
    resultado = manejador.procesar_mensaje(
        telefono="+56999999999",
        texto="Hola",
    )
    print(f"  Accion: {resultado['accion']}")
    print(f"  Respuesta: {resultado['respuesta']}")

    # Escenario 5: Mensaje libre de paciente conocido
    print("\n--- Escenario 5: Mensaje libre de paciente con cita ---")
    resultado = manejador.procesar_mensaje(
        telefono="+56933445566",  # Juan Perez
        texto="Hola, cuando es mi proxima cita?",
    )
    print(f"  Accion: {resultado['accion']}")
    print(f"  Respuesta: {resultado['respuesta']}")

    print("\n" + "="*60)
    print("  Simulacion completada")
    print("="*60)


if __name__ == "__main__":
    simular_conversacion_entrante()

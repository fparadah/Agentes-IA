"""
Manejador de mensajes entrantes de WhatsApp.

Procesa mensajes de pacientes desde WhatsApp Business API (Meta Cloud API).
Clasifica la intencion del mensaje y ejecuta la accion correspondiente.

Dos tipos de mensajes entrantes:
  A) Respuestas a confirmaciones (SI / NO / CAMBIAR)
  B) Conversaciones nuevas — pasa al agente Rosita

En produccion, este modulo es llamado por src/api.py (FastAPI).

Ejecutar simulacion:
  python -m src.webhook
"""

import os
import re
from datetime import datetime, timedelta
from typing import Optional

from src import database as db
from src.models import EstadoCita, TipoContacto
from src.tools import herramienta_enviar_mensaje_paciente

# Minutos sin actividad para expirar la sesion de conversacion
SESSION_TTL_MINUTOS = 30

# ---------------------------------------------------------------------------
# Clasificador de intenciones
# ---------------------------------------------------------------------------

# Keywords expandidos con expresiones chilenas comunes
RESPUESTAS_CONFIRMAR = {
    "si", "sí", "si!", "sí!", "confirmo", "confirmado", "ok", "dale",
    "claro", "voy", "ya", "oks", "sip", "yap", "okey", "de acuerdo",
    "ahi estare", "ahí estaré", "ahi voy", "ahí voy", "por supuesto",
    "por su puesto", "con gusto", "va", "ya pues", "perfecto",
}
RESPUESTAS_CANCELAR = {
    "no", "no puedo", "cancela", "cancelar", "no voy", "nop",
    "nope", "negativo", "no voy a poder", "no puedo ir",
    "imposible", "no me es posible",
}
RESPUESTAS_CAMBIAR = {
    "cambiar", "cambio", "reagendar", "reagenda", "otro dia", "otro horario",
    "cambiar hora", "cambiar fecha", "mover", "posponer", "postergar",
    "otro momento", "diferente dia", "diferente fecha",
}


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

    Mantiene una sesion de conversacion por numero de telefono (TTL: 30 min)
    para que el contexto de la conversacion persista entre mensajes.

    Uso en produccion: instanciar UNA SOLA VEZ a nivel de aplicacion
    (no por request) para que el diccionario de sesiones persista.

    Ejemplo en api.py:
        manejador = ManejadorWhatsApp()   # modulo-level singleton
    """

    def __init__(self, usar_agente: bool = True):
        self.usar_agente = usar_agente
        # Sesiones por telefono: {telefono: (AgenteAgenda, ultimo_uso)}
        self._sesiones: dict[str, tuple] = {}

    def _get_agente(self, telefono: str):
        """
        Obtiene o crea la sesion del agente para un numero de telefono.
        Limpia automaticamente sesiones inactivas por mas de SESSION_TTL_MINUTOS.
        """
        ahora = datetime.now()

        # Limpiar sesiones expiradas
        expiradas = [
            tel for tel, (_, ultimo_uso) in self._sesiones.items()
            if ahora - ultimo_uso > timedelta(minutes=SESSION_TTL_MINUTOS)
        ]
        for tel in expiradas:
            del self._sesiones[tel]

        # Crear nueva sesion o reutilizar existente
        if telefono not in self._sesiones:
            from src.agent import AgenteAgenda
            agente = AgenteAgenda(
                api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
                modo_debug=False,
            )
            self._sesiones[telefono] = (agente, ahora)
        else:
            agente, _ = self._sesiones[telefono]
            self._sesiones[telefono] = (agente, ahora)  # renovar timestamp

        return agente

    def limpiar_sesion(self, telefono: str) -> None:
        """Elimina la sesion de un paciente (ej: al confirmar o cancelar)."""
        self._sesiones.pop(telefono, None)

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
        return self._manejar_conversacion_libre(paciente, texto, citas_activas, telefono)

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
            mensaje="[RESPUESTA PACIENTE] SI - confirmo",
            respuesta="SI",
        )
        # La cita quedó resuelta: limpiar sesión para liberar memoria
        self.limpiar_sesion(paciente.telefono)

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
            mensaje="[RESPUESTA PACIENTE] NO - cancela",
            respuesta="NO",
        )
        self.limpiar_sesion(paciente.telefono)

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

    def _manejar_conversacion_libre(self, paciente, texto, citas_activas, telefono: str = "") -> dict:
        """
        Mensaje libre. Pasa al agente Rosita con sesion por telefono.
        Si no hay API key disponible, responde con informacion basica.
        """
        if not self.usar_agente or not os.environ.get("ANTHROPIC_API_KEY"):
            if citas_activas:
                cita = citas_activas[0]
                medico = db.obtener_medico(cita.medico_id)
                respuesta = (
                    f"Hola {paciente.nombre}! Tienes una cita con "
                    f"{medico.nombre_completo if medico else 'tu medico'} "
                    f"el {cita.fecha_hora_display}. "
                    f"Responde SI para confirmar, NO para cancelar, "
                    f"o CAMBIAR si necesitas otro horario."
                )
            else:
                respuesta = (
                    f"Hola {paciente.nombre}! No encontramos citas activas para ti. "
                    f"Escríbenos o llama a recepcion para agendar una hora."
                )
            return {
                "accion": "mensaje_libre_sin_agente",
                "paciente": paciente.nombre_completo,
                "respuesta": respuesta,
            }

        # Usar agente Rosita con sesion persistente por telefono
        try:
            agente = self._get_agente(telefono or paciente.telefono)
            # Dar contexto del paciente si es el primer mensaje de la sesion
            if len(agente.historial) == 0 and citas_activas:
                cita = citas_activas[0]
                medico = db.obtener_medico(cita.medico_id)
                contexto_inicial = (
                    f"[CONTEXTO INTERNO - no mostrar al paciente] "
                    f"El paciente es {paciente.nombre_completo}, telefono {paciente.telefono}. "
                    f"Tiene una cita proxima: [{cita.id}] con {medico.nombre_completo if medico else 'medico'} "
                    f"el {cita.fecha_hora_display}, estado: {cita.estado.value}."
                )
                agente.historial.append({"role": "user", "content": contexto_inicial})
                agente.historial.append({
                    "role": "assistant",
                    "content": "Entendido, tengo el contexto del paciente."
                })

            respuesta, herramientas = agente.responder(texto)

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
                f"Hola {paciente.nombre}! En este momento no puedo procesar tu mensaje. "
                f"Por favor llama a recepcion. Disculpa las molestias!"
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

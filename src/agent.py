"""
Agente conversacional para gestion de citas clinicas.
Usa la API de Anthropic (Claude) con tool use para ejecutar acciones
sobre la base de datos de citas.
"""

import json
import os
from datetime import datetime
from typing import Optional

import anthropic

from src.tools import HERRAMIENTAS_SCHEMA, MAPA_HERRAMIENTAS


def _build_system_prompt() -> str:
    """
    Construye el system prompt con la fecha/hora actual.
    Se llama en cada request para que Rosita siempre tenga la hora correcta.
    """
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    return f"""Eres el asistente virtual de agenda del centro clinico.
Tu nombre es "Rosita" y trabajas ayudando a los pacientes y al equipo de recepcion
a gestionar sus citas medicas.

FECHA Y HORA ACTUAL: {ahora}

TU PERSONALIDAD:
- Eres amable, cercana y empatica
- Hablas de forma simple y clara, sin tecnicismos
- Siempre te presentas cuando es el primer mensaje
- Usas un tono informal pero respetuoso (puedes usar "usted" o "tu" segun el contexto)
- Eres eficiente: vas al grano pero sin ser fria
- Cuando escribas para WhatsApp, usa mensajes cortos (maximo 3 oraciones)

LO QUE PUEDES HACER:
1. Buscar las citas de un paciente por nombre o telefono
2. Ver los detalles de una cita especifica
3. Confirmar una cita (cambiar estado de "agendado" a "confirmado")
4. Cancelar una cita
5. Reagendar una cita a una nueva fecha y hora
6. Enviar mensajes de notificacion a los pacientes
7. Listar las citas del dia o las pendientes de confirmacion

COMO MANEJAR LAS SOLICITUDES:
- Cuando alguien quiera confirmar, preguntar los datos necesarios para encontrar la cita
- Antes de cancelar o reagendar, SIEMPRE confirma con el usuario que es la cita correcta
- Cuando confirmes una cita, envia siempre un mensaje de confirmacion al paciente
- Cuando canceles, ofrece reagendar
- Cuando reagendes, envia notificacion con la nueva fecha

FORMATO DE MENSAJES PARA PACIENTES:
- Usa lenguaje cercano y simple
- Incluye siempre: nombre del paciente, fecha y hora, medico, y el proximo paso
- Ejemplo de confirmacion: "Hola [Nombre]! Te confirmamos tu cita con [Dr./Dra.] el [dia] a las [hora]. Si tienes alguna duda, escribenos."
- Ejemplo de cancelacion: "Hola [Nombre], hemos cancelado tu cita del [dia]. Si quieres reagendar, avisanos cuando quieras."

CUANDO USES HERRAMIENTAS:
- Explica brevemente lo que estas haciendo
- Si no encuentras una cita, pide mas informacion antes de rendirte
- Siempre muestra el ID de la cita cuando hagas cambios (es util para rastrear)
"""


class AgenteAgenda:
    """
    Agente conversacional que gestiona citas clinicas usando Claude + tool use.
    """

    def __init__(self, api_key: Optional[str] = None, modo_debug: bool = False):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.cliente = anthropic.Anthropic(api_key=self.api_key)
        self.historial: list[dict] = []
        self.modo_debug = modo_debug
        self.modelo = "claude-opus-4-6"

    def _ejecutar_herramienta(self, nombre: str, argumentos: dict) -> str:
        """Ejecuta una herramienta y retorna el resultado como JSON string."""
        if nombre not in MAPA_HERRAMIENTAS:
            return json.dumps({"error": f"Herramienta '{nombre}' no encontrada."})

        try:
            resultado = MAPA_HERRAMIENTAS[nombre](argumentos)
            return json.dumps(resultado, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": f"Error al ejecutar '{nombre}': {str(e)}"})

    def responder(self, mensaje_usuario: str) -> tuple[str, list[dict]]:
        """
        Procesa un mensaje del usuario y retorna la respuesta del agente
        junto con las herramientas ejecutadas durante el proceso.

        Retorna: (respuesta_texto, lista_de_herramientas_usadas)
        """
        self.historial.append({"role": "user", "content": mensaje_usuario})
        herramientas_usadas = []

        # System prompt con fecha/hora actual calculada en cada request
        system_prompt = _build_system_prompt()

        while True:
            respuesta = self.cliente.messages.create(
                model=self.modelo,
                max_tokens=2048,
                system=system_prompt,
                tools=HERRAMIENTAS_SCHEMA,
                messages=self.historial,
            )

            if self.modo_debug:
                print(f"\n[DEBUG] stop_reason: {respuesta.stop_reason}")

            # Si no hay mas tool calls, terminamos
            if respuesta.stop_reason == "end_turn":
                texto_respuesta = ""
                for bloque in respuesta.content:
                    if hasattr(bloque, "text"):
                        texto_respuesta += bloque.text

                self.historial.append({
                    "role": "assistant",
                    "content": respuesta.content,
                })
                return texto_respuesta, herramientas_usadas

            # Procesar tool_use blocks
            if respuesta.stop_reason == "tool_use":
                # Agregar respuesta del asistente (con tool calls) al historial
                self.historial.append({
                    "role": "assistant",
                    "content": respuesta.content,
                })

                # Ejecutar cada herramienta solicitada
                resultados_herramientas = []
                for bloque in respuesta.content:
                    if bloque.type == "tool_use":
                        if self.modo_debug:
                            print(f"\n[DEBUG] Herramienta: {bloque.name}")
                            print(f"[DEBUG] Argumentos: {json.dumps(bloque.input, ensure_ascii=False)}")

                        resultado = self._ejecutar_herramienta(bloque.name, bloque.input)

                        if self.modo_debug:
                            print(f"[DEBUG] Resultado: {resultado[:200]}...")

                        herramientas_usadas.append({
                            "herramienta": bloque.name,
                            "argumentos": bloque.input,
                            "resultado": json.loads(resultado),
                        })

                        resultados_herramientas.append({
                            "type": "tool_result",
                            "tool_use_id": bloque.id,
                            "content": resultado,
                        })

                # Agregar resultados al historial
                self.historial.append({
                    "role": "user",
                    "content": resultados_herramientas,
                })
                # Continuar el loop para que el agente procese los resultados

    def limpiar_historial(self) -> None:
        """Reinicia la conversacion."""
        self.historial = []

    def exportar_historial(self) -> list[dict]:
        """Retorna el historial de la conversacion para inspeccion."""
        return self.historial.copy()

"""
Conector para Mydoc (mydoc.cl) - Sistema de registro clinico.

ESTADO ACTUAL: Stub / Investigacion pendiente.

Este modulo es el puente entre nuestro agente y Mydoc.
Define la interfaz que necesitamos, independiente de como se implemente.

== OPCIONES DE INTEGRACION (de mejor a peor) ==

OPCION A: API REST oficial de Mydoc
  - Contactar a soporte de Mydoc y preguntar si tienen API para integraciones
  - Pedir documentacion, credenciales de desarrollador
  - Esta es la opcion ideal

OPCION B: Exportacion periodica (sin API)
  - Mydoc tiene exportacion a Excel/CSV de la agenda
  - Automatizar la descarga diaria del archivo
  - Importar al sistema local
  - Limitacion: no es en tiempo real, solo sirve para el flujo del dia siguiente

OPCION C: Acceso directo a base de datos
  - Solo si Mydoc esta instalado localmente (no SaaS)
  - Requiere acceso a la DB (MySQL, PostgreSQL, etc.)
  - Riesgoso: puede romperse con actualizaciones de Mydoc

OPCION D: Web scraping / automatizacion de navegador
  - Usar Playwright o Selenium para interactuar con la interfaz web de Mydoc
  - Fragil: se rompe con cambios de UI
  - Usar solo como ultimo recurso

== PREGUNTAS CLAVE PARA RESPONDER ==

1. Mydoc es SaaS (cloud) o esta instalado en el centro?
2. Tienen soporte tecnico o desarrolladores contactables?
3. Hay opcion de exportar la agenda desde el panel?
4. Como se autentican los usuarios? (usuario/contrasena, OAuth, SSO?)
5. Que datos necesitamos leer: solo agenda o tambien datos del paciente?
6. Necesitamos ESCRIBIR en Mydoc (actualizar estado) o solo leer?

Para preguntar a Mydoc:
  - Email soporte: (buscar en mydoc.cl/contacto)
  - Pregunta clave: "Tienen API REST o algun mecanismo de integracion
    para conectar sistemas externos de notificacion?"

"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional

from src.models import Cita, EstadoCita, Medico, Paciente


# ---------------------------------------------------------------------------
# Interfaz abstracta del conector
# ---------------------------------------------------------------------------

class ConectorAgenda(ABC):
    """
    Interfaz que debe cumplir cualquier conector de agenda.
    Esto permite cambiar el backend (Mydoc, SQLite, otro) sin
    tocar el resto del sistema.
    """

    @abstractmethod
    def obtener_citas_fecha(self, fecha: str) -> list[Cita]:
        """Retorna todas las citas de una fecha (YYYY-MM-DD)."""
        ...

    @abstractmethod
    def obtener_citas_paciente(self, paciente_id: str) -> list[Cita]:
        """Retorna todas las citas activas de un paciente."""
        ...

    @abstractmethod
    def confirmar_cita(self, cita_id: str) -> bool:
        """Marca una cita como confirmada. Retorna True si fue exitoso."""
        ...

    @abstractmethod
    def cancelar_cita(self, cita_id: str, motivo: Optional[str] = None) -> bool:
        """Cancela una cita. Retorna True si fue exitoso."""
        ...

    @abstractmethod
    def buscar_paciente_por_telefono(self, telefono: str) -> Optional[Paciente]:
        """Busca un paciente por su numero de telefono."""
        ...


# ---------------------------------------------------------------------------
# Implementacion local (SQLite) - para pruebas
# ---------------------------------------------------------------------------

class ConectorLocal(ConectorAgenda):
    """
    Implementacion usando la base de datos SQLite local.
    Es la implementacion actual para pruebas.
    """

    def obtener_citas_fecha(self, fecha: str) -> list[Cita]:
        from src import database as db
        return db.obtener_citas_por_fecha(fecha)

    def obtener_citas_paciente(self, paciente_id: str) -> list[Cita]:
        from src import database as db
        return [
            c for c in db.obtener_citas_paciente(paciente_id)
            if c.estado in (EstadoCita.AGENDADO, EstadoCita.CONFIRMADO)
        ]

    def confirmar_cita(self, cita_id: str) -> bool:
        from src import database as db
        cita = db.confirmar_cita(cita_id)
        return cita is not None and cita.estado == EstadoCita.CONFIRMADO

    def cancelar_cita(self, cita_id: str, motivo: Optional[str] = None) -> bool:
        from src import database as db
        cita = db.cancelar_cita(cita_id, motivo)
        return cita is not None and cita.estado == EstadoCita.CANCELADO

    def buscar_paciente_por_telefono(self, telefono: str) -> Optional[Paciente]:
        from src import database as db
        return db.buscar_paciente_por_telefono(telefono)


# ---------------------------------------------------------------------------
# Stub de conector Mydoc (a implementar cuando tengamos acceso)
# ---------------------------------------------------------------------------

class ConectorMydocREST(ConectorAgenda):
    """
    Conector para la API REST de Mydoc.
    PENDIENTE: implementar cuando tengamos credenciales y documentacion.

    Variables de entorno necesarias:
      MYDOC_API_URL    = https://api.mydoc.cl/v1  (o similar)
      MYDOC_API_TOKEN  = tu-token-de-acceso
      MYDOC_CLINIC_ID  = id-de-tu-centro
    """

    def __init__(self, base_url: str, token: str, clinic_id: str):
        self.base_url = base_url
        self.token = token
        self.clinic_id = clinic_id
        # En produccion: import httpx o requests
        raise NotImplementedError(
            "ConectorMydocREST no implementado aun. "
            "Primero confirmar si Mydoc tiene API REST disponible."
        )

    def obtener_citas_fecha(self, fecha: str) -> list[Cita]:
        # GET /agenda?fecha=YYYY-MM-DD&clinica_id=X
        raise NotImplementedError

    def obtener_citas_paciente(self, paciente_id: str) -> list[Cita]:
        # GET /pacientes/{id}/citas
        raise NotImplementedError

    def confirmar_cita(self, cita_id: str) -> bool:
        # PATCH /citas/{id} {"estado": "confirmado"}
        raise NotImplementedError

    def cancelar_cita(self, cita_id: str, motivo: Optional[str] = None) -> bool:
        # DELETE /citas/{id} o PATCH /citas/{id} {"estado": "cancelado"}
        raise NotImplementedError

    def buscar_paciente_por_telefono(self, telefono: str) -> Optional[Paciente]:
        # GET /pacientes?telefono=XXXXXXXXX
        raise NotImplementedError


class ConectorMydocExport(ConectorAgenda):
    """
    Conector basado en exportacion de archivos de Mydoc (Plan B).
    Mydoc exporta la agenda a Excel/CSV que se importa diariamente.

    Flujo:
      1. Mydoc exporta agenda del dia siguiente a las 9 PM
      2. El archivo se descarga automaticamente (o manualmente)
      3. Este conector lo lee y lo importa a la DB local
      4. El scheduler trabaja sobre la DB local

    PENDIENTE: confirmar si Mydoc tiene exportacion automatizada o solo manual.
    """

    def __init__(self, directorio_exportaciones: str = "data/exportaciones"):
        self.directorio = directorio_exportaciones

    def importar_desde_excel(self, ruta_archivo: str) -> int:
        """
        Importa citas desde un archivo Excel exportado por Mydoc.
        Retorna el numero de citas importadas.
        PENDIENTE: implementar una vez que tengamos el formato del export de Mydoc.
        """
        raise NotImplementedError(
            "Implementar segun el formato de exportacion de Mydoc. "
            "Ejecutar una exportacion de prueba y analizar el formato del archivo."
        )

    def obtener_citas_fecha(self, fecha: str) -> list[Cita]:
        from src import database as db
        return db.obtener_citas_por_fecha(fecha)

    def obtener_citas_paciente(self, paciente_id: str) -> list[Cita]:
        from src import database as db
        return db.obtener_citas_paciente(paciente_id)

    def confirmar_cita(self, cita_id: str) -> bool:
        # En este modo: actualiza DB local + alerta a recepcion para actualizar Mydoc manualmente
        from src import database as db
        cita = db.confirmar_cita(cita_id)
        return cita is not None

    def cancelar_cita(self, cita_id: str, motivo: Optional[str] = None) -> bool:
        from src import database as db
        cita = db.cancelar_cita(cita_id, motivo)
        return cita is not None

    def buscar_paciente_por_telefono(self, telefono: str) -> Optional[Paciente]:
        from src import database as db
        return db.buscar_paciente_por_telefono(telefono)


# ---------------------------------------------------------------------------
# Factory: selecciona el conector segun configuracion
# ---------------------------------------------------------------------------

def crear_conector(modo: str = "local") -> ConectorAgenda:
    """
    Crea y retorna el conector apropiado segun el entorno.

    modo:
      "local"   -> SQLite local (pruebas)
      "mydoc"   -> API REST de Mydoc (MVP conectado)
      "export"  -> Exportacion de archivos (plan B)
    """
    if modo == "local":
        return ConectorLocal()
    if modo == "mydoc":
        import os
        return ConectorMydocREST(
            base_url=os.environ["MYDOC_API_URL"],
            token=os.environ["MYDOC_API_TOKEN"],
            clinic_id=os.environ["MYDOC_CLINIC_ID"],
        )
    if modo == "export":
        return ConectorMydocExport()
    raise ValueError(f"Modo de conector desconocido: {modo}")


# ---------------------------------------------------------------------------
# Checklist de investigacion (imprimible)
# ---------------------------------------------------------------------------

CHECKLIST_INVESTIGACION = """
╔══════════════════════════════════════════════════════════════════╗
║         CHECKLIST: INTEGRACION CON MYDOC                        ║
╚══════════════════════════════════════════════════════════════════╝

Para avanzar al MVP conectado, necesitamos responder estas preguntas:

[ ] 1. TIPO DE INSTALACION
      Mydoc es SaaS (cloud en mydoc.cl) o instalado en servidor propio?
      -> Esto determina si podemos acceder a la DB directamente

[ ] 2. API REST
      Contactar soporte Mydoc: tienen API para desarrolladores?
      Preguntar: endpoint, autenticacion, endpoints de agenda
      Email/web: https://www.mydoc.cl/web/

[ ] 3. EXPORTACION DE DATOS
      Desde el panel de Mydoc, hay opcion de exportar la agenda?
      En que formato? (Excel, CSV, PDF?)
      Es automatizable o solo manual?

[ ] 4. DATOS NECESARIOS (lo que necesitamos leer de Mydoc)
      - Lista de citas por fecha (con nombre paciente, telefono, medico, hora)
      - Estado de cada cita
      - Datos de contacto del paciente (telefono, email)

[ ] 5. ESCRITURA EN MYDOC (lo que necesitamos actualizar)
      - Cambiar estado de cita: agendado -> confirmado
      - Cancelar una cita
      - Crear nueva cita (para reagendamiento)

[ ] 6. AUTENTICACION
      Como se autentican los usuarios en Mydoc?
      Hay usuario/contrasena de tipo "integracion" o "API"?

[ ] 7. NUMERO DE WHATSAPP BUSINESS
      Ya tienen numero de WhatsApp Business registrado?
      Si no: registrar en business.whatsapp.com
      Proveedor recomendado para Chile: Twilio o Infobip

[ ] 8. TEMPLATES DE WHATSAPP
      Para enviar mensajes proactivos (el sistema llama al paciente)
      necesitamos templates aprobados por Meta.
      Ejemplo de template a crear:
        "Hola {{nombre}}, te recordamos tu cita con {{medico}}
         el {{fecha}} a las {{hora}}. Responde SI para confirmar
         o NO para cancelar."

══════════════════════════════════════════════════════════════════
ACCION INMEDIATA: Contactar soporte de Mydoc para preguntar por API
══════════════════════════════════════════════════════════════════
"""


if __name__ == "__main__":
    print(CHECKLIST_INVESTIGACION)

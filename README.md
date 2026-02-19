# Sistema de Agenda Clinica - Agente IA

Agente conversacional para gestionar citas de un centro clinico.
Permite confirmar, cancelar y reagendar citas, comunicandose con los pacientes
en lenguaje simple y cercano.

## Estado actual: Fase 1 - Prototipo con datos simulados

```
[FASE 1] Prototipo local    ← ESTAMOS AQUI
[FASE 2] MVP conectado      (siguiente paso)
[FASE 3] Produccion         (futuro)
```

---

## Instalacion rapida

```bash
# 1. Clonar el repositorio
git clone <url-del-repo>
cd Agentes-IA

# 2. Crear entorno virtual e instalar dependencias
python -m venv venv
source venv/bin/activate       # Linux/Mac
# venv\Scripts\activate        # Windows

pip install -r requirements.txt

# 3. Configurar API key de Anthropic
cp .env.example .env
# Editar .env y agregar tu ANTHROPIC_API_KEY

# 4. Cargar datos de prueba
python main.py --seed

# 5. Iniciar el chat con el agente
export ANTHROPIC_API_KEY="tu-api-key-aqui"
python main.py
```

---

## Comandos disponibles

| Comando | Descripcion |
|---|---|
| `python main.py` | Chat interactivo con el agente |
| `python main.py --seed` | Carga datos de prueba en la DB |
| `python main.py --listar` | Muestra todas las citas |
| `python main.py --escenario` | Pruebas automaticas sin IA |
| `python main.py --debug` | Chat con logs internos visibles |
| `python -m pytest tests/ -v` | Ejecuta todos los tests |

---

## Ejemplos de conversacion con el agente

```
Tú: Cuales son las citas pendientes de confirmar?
Valeria: Hola! Tengo 3 citas pendientes de confirmacion...

Tú: Busca las citas de Maria Gonzalez
Valeria: Encontre 2 citas para Maria Gonzalez...

Tú: Confirma la cita cita001 y avisale al paciente
Valeria: Listo! Confirme la cita de Maria con la Dra. Vargas...
         [Simule el envio de mensaje via WhatsApp]

Tú: Cancela la cita cita003, el paciente no puede ir
Valeria: Entendido, cancele la cita de Sofia Torres...
         Quieres que la reagende para otro dia?

Tú: Reagenda la cita cita004 para el proximo lunes a las 15:00
Valeria: Perfecto, reagende la cita de Carlos Ramirez...
```

---

## Arquitectura del prototipo

```
main.py                  <- CLI de pruebas
src/
  models.py              <- Entidades: Paciente, Medico, Cita
  database.py            <- CRUD sobre SQLite (mock del sistema clinico)
  tools.py               <- Herramientas que usa el agente (tool use)
  agent.py               <- Agente conversacional (Claude API)
data/
  seed.py                <- Datos de prueba
  clinica.db             <- Base de datos SQLite (generada al ejecutar)
tests/
  test_database.py       <- Tests de la capa de datos
  test_tools.py          <- Tests de las herramientas del agente
```

---

## Herramientas disponibles para el agente

El agente puede ejecutar estas acciones automaticamente durante la conversacion:

| Herramienta | Descripcion |
|---|---|
| `buscar_citas_paciente` | Busca por nombre o telefono |
| `obtener_detalle_cita` | Detalles completos de una cita |
| `listar_citas_del_dia` | Agenda del dia |
| `listar_citas_pendientes` | Citas sin confirmar |
| `confirmar_cita` | Cambia estado a "confirmado" |
| `cancelar_cita` | Cancela una cita |
| `reagendar_cita` | Cambia fecha/hora |
| `enviar_mensaje_paciente` | Simula envio de mensaje |
| `registrar_respuesta_paciente` | Registra respuesta del paciente |

---

## Hoja de ruta hacia el MVP

### Lo que falta para conectar al sistema real

1. **Conector al sistema clinico existente**
   - Reemplazar `src/database.py` por un cliente HTTP al API del sistema
   - O un conector ODBC/SQL si hay acceso directo a la DB

2. **Canal de mensajeria real**
   - WhatsApp Business API (Meta o via Twilio)
   - SMS como alternativa
   - Configurar en `.env` (ver `.env.example`)

3. **Interfaz de entrada de mensajes**
   - Webhook para recibir mensajes de WhatsApp
   - Panel web simple para recepcionistas

4. **Autenticacion y seguridad**
   - Verificacion de identidad del paciente
   - Logs de auditoria

### Preguntas clave para el MVP
- Que sistema de registro clinico usa el centro? (Medisoft, Rayen, etc.)
- Tiene API disponible o solo acceso a DB?
- Que canal prefieren los pacientes? (WhatsApp es lo mas comun en Chile)
- Quien inicia el contacto, el sistema o el paciente?

---

## Tests

```bash
# Todos los tests
python -m pytest tests/ -v

# Con reporte de cobertura
python -m pytest tests/ -v --cov=src --cov-report=term-missing

# Solo tests de DB
python -m pytest tests/test_database.py -v

# Solo tests de herramientas
python -m pytest tests/test_tools.py -v
```

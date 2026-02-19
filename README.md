# Sistema de Agenda Clinica - Agente IA

Agente conversacional para gestionar citas de un centro clinico.
Comunica en lenguaje cercano y simple con los pacientes via WhatsApp.

---

## Arquitectura del sistema (vision completa)

```
╔══════════════════ FLUJO A: PROACTIVO (sistema llama al paciente) ═══════════╗
║                                                                              ║
║  [Scheduler diario]                                                          ║
║    10:00 AM → Consulta Mydoc para citas del día siguiente                   ║
║             → Por cada cita "agendado":                                     ║
║               → Envía WhatsApp al paciente                                  ║
║               → "Confirma tu cita para mañana con Dr. X a las 10:00"       ║
║                                                                              ║
║  [Paciente responde]                                                         ║
║    SI  → webhook.py confirma cita en Mydoc                                  ║
║    NO  → webhook.py cancela + slot queda libre en Mydoc                     ║
║    Sin respuesta → 2do recordatorio a las 4 horas                           ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════ FLUJO B: REACTIVO (paciente escribe primero) ══════════════╗
║                                                                              ║
║  [Paciente escribe al WhatsApp del centro]                                   ║
║    → webhook.py identifica paciente por número                              ║
║    → Si tiene cita pendiente: ofrece confirmar/cancelar/reagendar           ║
║    → Si mensaje libre: pasa al agente conversacional (Claude)               ║
║      → Agente puede: ver citas, confirmar, cancelar, reagendar              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## Estado actual: Fase 1 - Prototipo local

```
[FASE 1] Prototipo local (datos simulados)    ← ESTAMOS AQUÍ
[FASE 2] MVP conectado (Mydoc + WhatsApp)     (próximo)
[FASE 3] Producción                           (futuro)
```

---

## Instalación rápida

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Configurar API key
cp .env.example .env
# Editar .env → agregar ANTHROPIC_API_KEY

# 3. Cargar datos de prueba
python main.py --seed

# 4. Chat con el agente
export ANTHROPIC_API_KEY="sk-ant-..."
python main.py
```

---

## Comandos disponibles

| Comando | Descripción |
|---|---|
| `python main.py` | Chat interactivo con el agente Valeria |
| `python main.py --seed` | Carga datos de prueba |
| `python main.py --listar` | Lista todas las citas |
| `python main.py --escenario` | Pruebas automáticas sin IA |
| `python main.py --debug` | Chat con logs internos |
| `python -m src.scheduler` | Simula el proceso de confirmación diaria |
| `python -m src.scheduler --dry-run` | Ver qué haría el scheduler sin enviar |
| `python -m src.scheduler --simular` | Procesa citas + simula respuestas |
| `python -m src.webhook` | Simula mensajes entrantes de pacientes |
| `python -m src.mydoc_connector` | Muestra checklist de integración con Mydoc |
| `python -m pytest tests/ -v` | Ejecuta todos los tests (40 tests) |

---

## Estructura del proyecto

```
Agentes-IA/
├── src/
│   ├── models.py           ← Entidades: Paciente, Medico, Cita
│   ├── database.py         ← CRUD SQLite (mock del sistema clínico)
│   ├── tools.py            ← 9 herramientas del agente (tool use)
│   ├── agent.py            ← Agente "Valeria" (Claude API + historial)
│   ├── scheduler.py        ← Proceso diario de confirmación proactiva
│   ├── webhook.py          ← Manejador de mensajes entrantes WhatsApp
│   └── mydoc_connector.py  ← Interfaz + stub para conectar con Mydoc
├── data/
│   └── seed.py             ← 5 pacientes, 3 médicos, 7 citas de ejemplo
├── tests/
│   ├── test_database.py    ← 17 tests de la capa de datos
│   └── test_tools.py       ← 23 tests de las herramientas
├── main.py                 ← CLI de pruebas
├── .env.example            ← Plantilla de variables de entorno
└── requirements.txt
```

---

## Flujo del scheduler (confirmación proactiva)

```bash
# Ver qué haría el scheduler mañana (sin enviar nada)
python -m src.scheduler --dry-run

# Ejecutar el scheduler (simula envío de mensajes)
python -m src.scheduler

# Ejecutar + simular respuestas de pacientes
python -m src.scheduler --simular

# Procesar una fecha específica
python -m src.scheduler --fecha 2026-02-20 --simular
```

**Resultado esperado:**
```
Cita [cita004] → Carlos Ramirez (+56955667788)
  OK - Mensaje enviado via whatsapp
  Mensaje: "Hola Carlos! 👋 Te recordamos que tienes una cita...
             Responde SI para confirmar o NO para cancelar."

Simulando respuestas de 2 pacientes...
  [cita004] Carlos Ramirez: CONFIRMO
  [cita005] Valentina Lopez: SIN RESPUESTA (timeout)
```

---

## Flujo del webhook (paciente escribe primero)

```bash
python -m src.webhook
```

Simula estos escenarios:
1. Paciente escribe "Si, confirmo" → cita se confirma automáticamente
2. Paciente escribe "No, no voy a poder" → cita se cancela
3. Paciente escribe "Quiero cambiar mi hora" → inicia flujo de reagendamiento
4. Número desconocido → respuesta genérica
5. Mensaje libre → pasa al agente conversacional

---

## Herramientas del agente (Valeria)

El agente puede ejecutar estas acciones durante la conversación:

| Herramienta | Descripción |
|---|---|
| `buscar_citas_paciente` | Busca por nombre o teléfono |
| `obtener_detalle_cita` | Detalles completos de una cita |
| `listar_citas_del_dia` | Agenda del día |
| `listar_citas_pendientes` | Citas sin confirmar |
| `confirmar_cita` | Cambia estado: `agendado` → `confirmado` |
| `cancelar_cita` | Cancela una cita |
| `reagendar_cita` | Nueva fecha/hora (crea nueva cita, marca original) |
| `enviar_mensaje_paciente` | Simula envío WhatsApp/SMS |
| `registrar_respuesta_paciente` | Registra respuesta del paciente |

---

## Hoja de ruta al MVP conectado

### Lo que falta investigar (hacer ya)

Ver checklist completo:
```bash
python -m src.mydoc_connector
```

**Puntos clave:**

**1. Mydoc API** → Contactar soporte en mydoc.cl
- Pregunta: *"¿Tienen API REST o mecanismo de integración para conectar sistemas externos?"*
- Si tienen API: `src/mydoc_connector.py` → implementar `ConectorMydocREST`
- Si no tienen API: ver Opción B (exportación de archivos)

**2. WhatsApp Business** → Registrar número
- Ir a [business.whatsapp.com](https://business.whatsapp.com)
- O usar proveedor: **Twilio** o **Infobip** (buenos en Chile)
- Crear templates de mensaje para aprobación de Meta:
  - Template de confirmación (mensaje proactivo)
  - Template de cancelación
  - Template de reagendamiento

**3. Variables de entorno para el MVP**
```bash
# .env (cuando estemos listos)
ANTHROPIC_API_KEY=sk-ant-...
MYDOC_API_URL=https://...
MYDOC_API_TOKEN=...
WHATSAPP_API_TOKEN=...
WHATSAPP_PHONE_ID=...
```

### Decisiones de arquitectura pendientes

| Decisión | Opciones | Recomendación |
|---|---|---|
| Hosting del sistema | Servidor propio / VPS / Cloud | VPS simple (DigitalOcean ~$12/mes) |
| Proveedor WhatsApp | Twilio / Infobip / Meta directo | Twilio (más documentación) |
| Base de datos MVP | SQLite → PostgreSQL | PostgreSQL cuando escalemos |
| Horario scheduler | Diario 10 AM / Múltiples veces | 10 AM + recordatorio 3 PM |

---

## Tests

```bash
# Todos los tests (40 tests, 100% pasando)
python -m pytest tests/ -v

# Con cobertura
python -m pytest tests/ -v --cov=src --cov-report=term-missing
```

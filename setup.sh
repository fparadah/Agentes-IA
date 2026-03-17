#!/bin/bash
# setup.sh — Configuracion inicial del proyecto Rosita
# Ejecutar una sola vez despues de clonar el repositorio.
# Uso: bash setup.sh

set -e

echo ""
echo "  Rosita — Setup inicial"
echo "  ======================"
echo ""

# 1. Verificar Python 3.11+
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED="3.11"

if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"; then
    echo "  Python $PYTHON_VERSION detectado"
else
    echo "  ERROR: Se requiere Python 3.11 o superior (tienes $PYTHON_VERSION)"
    echo "  Descarga desde: https://www.python.org/downloads/"
    exit 1
fi

# 2. Crear entorno virtual
if [ ! -d ".venv" ]; then
    echo "  Creando entorno virtual (.venv/)..."
    python3 -m venv .venv
else
    echo "  Entorno virtual ya existe (.venv/)"
fi

# 3. Activar entorno e instalar dependencias
echo "  Instalando dependencias..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q
echo "  Dependencias instaladas"

# 4. Crear .env si no existe
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "  Archivo .env creado desde .env.example"
    echo "  IMPORTANTE: edita .env y agrega tu ANTHROPIC_API_KEY"
else
    echo "  .env ya existe (no se sobreescribio)"
fi

# 5. Crear directorio de datos
mkdir -p data

# 6. Cargar datos de prueba
echo ""
echo "  Cargando datos de prueba en la base de datos..."
PYTHONPATH=. .venv/bin/python main.py --seed

echo ""
echo "  =========================================="
echo "  Setup completado exitosamente!"
echo "  =========================================="
echo ""
echo "  Proximos pasos:"
echo ""
echo "  1. Editar .env y agregar tu ANTHROPIC_API_KEY:"
echo "     nano .env   (o abre con VS Code)"
echo ""
echo "  2. Chatear con Rosita:"
echo "     make chat"
echo "     (o: PYTHONPATH=. .venv/bin/python main.py)"
echo ""
echo "  3. Iniciar servidor FastAPI (cuando tengas las credenciales WhatsApp):"
echo "     make server"
echo ""
echo "  4. En VS Code: presiona F5 y elige la configuracion que quieras ejecutar"
echo ""

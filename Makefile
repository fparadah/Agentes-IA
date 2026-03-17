# Comandos del sistema de agenda clinica — Rosita
# Uso: make <comando>
# Requiere: Python 3.11+, entorno virtual en .venv/

.PHONY: help setup seed chat server webhook test test-cov clean

PYTHON = .venv/bin/python
PIP    = .venv/bin/pip

# -------------------------------------------------------------------
# help — muestra esta lista (comando por defecto)
# -------------------------------------------------------------------
help:
	@echo ""
	@echo "  Rosita — Sistema de Agenda Clinica"
	@echo "  ==================================="
	@echo ""
	@echo "  Primera vez:"
	@echo "    make setup      Crea el entorno virtual e instala dependencias"
	@echo "    make seed       Carga datos de prueba en la base de datos"
	@echo ""
	@echo "  Desarrollo:"
	@echo "    make chat       Inicia el chat interactivo con Rosita"
	@echo "    make server     Inicia el servidor FastAPI (puerto 8000)"
	@echo "    make webhook    Simula mensajes entrantes de WhatsApp"
	@echo "    make schedule   Ejecuta el scheduler una vez (confirmaciones)"
	@echo ""
	@echo "  Tests:"
	@echo "    make test       Corre los tests con pytest"
	@echo "    make test-cov   Tests con reporte de cobertura"
	@echo ""
	@echo "  Limpieza:"
	@echo "    make clean      Elimina cache de Python"
	@echo ""

# -------------------------------------------------------------------
# setup — primera vez
# -------------------------------------------------------------------
setup:
	@echo "Creando entorno virtual..."
	python3 -m venv .venv
	@echo "Instalando dependencias..."
	$(PIP) install --upgrade pip -q
	$(PIP) install -r requirements.txt -q
	@echo ""
	@echo "  Listo! Proximos pasos:"
	@echo "  1. cp .env.example .env"
	@echo "  2. Editar .env y agregar tu ANTHROPIC_API_KEY"
	@echo "  3. make seed   (cargar datos de prueba)"
	@echo "  4. make chat   (chatear con Rosita)"
	@echo ""

# -------------------------------------------------------------------
# seed — cargar datos de prueba
# -------------------------------------------------------------------
seed:
	PYTHONPATH=. $(PYTHON) main.py --seed

# -------------------------------------------------------------------
# chat — modo interactivo
# -------------------------------------------------------------------
chat:
	PYTHONPATH=. $(PYTHON) main.py

# -------------------------------------------------------------------
# server — servidor FastAPI con recarga automatica
# -------------------------------------------------------------------
server:
	PYTHONPATH=. $(PYTHON) -m uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload

# -------------------------------------------------------------------
# webhook — simular mensajes entrantes de pacientes
# -------------------------------------------------------------------
webhook:
	PYTHONPATH=. $(PYTHON) -m src.webhook

# -------------------------------------------------------------------
# schedule — ejecutar scheduler manualmente
# -------------------------------------------------------------------
schedule:
	PYTHONPATH=. $(PYTHON) main.py --schedule

# -------------------------------------------------------------------
# test — correr todos los tests
# -------------------------------------------------------------------
test:
	PYTHONPATH=. $(PYTHON) -m pytest tests/ -v

# -------------------------------------------------------------------
# test-cov — tests con cobertura HTML
# -------------------------------------------------------------------
test-cov:
	PYTHONPATH=. $(PYTHON) -m pytest tests/ -v --cov=src --cov-report=html
	@echo ""
	@echo "  Reporte de cobertura en: htmlcov/index.html"
	@echo ""

# -------------------------------------------------------------------
# clean — limpiar archivos temporales de Python
# -------------------------------------------------------------------
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov
	@echo "Limpieza completada."

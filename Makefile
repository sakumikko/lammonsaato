# Lammonsaato - Pool Heating Optimizer
# Common development commands

# Use local virtualenv
PYTHON = ./env/bin/python
PIP = ./env/bin/pip

.PHONY: help install test test-thermia test-nordpool test-firebase lint clean deploy

# Default target
help:
	@echo "Lammonsaato - Pool Heating Optimizer"
	@echo ""
	@echo "Available targets:"
	@echo "  install       Install Python dependencies"
	@echo "  test          Run all tests"
	@echo "  test-thermia  Test Thermia heat pump connection"
	@echo "  test-nordpool Test Nordpool price fetching"
	@echo "  test-firebase Test Firebase connection"
	@echo "  lint          Run linting checks"
	@echo "  clean         Clean up temporary files"
	@echo "  deploy        Deploy to Home Assistant (requires SSH)"
	@echo ""

# Install dependencies
install:
	$(PIP) install -r requirements.txt

# Run all tests
test:
	$(PYTHON) -m pytest tests/ -v

# Test Thermia connection
test-thermia:
	$(PYTHON) scripts/standalone/test_thermia.py $(THERMIA_HOST)

# Test Nordpool prices
test-nordpool:
	$(PYTHON) scripts/standalone/test_nordpool.py

# Test Firebase
test-firebase:
	$(PYTHON) scripts/standalone/test_firebase.py --test-connection

# Setup Firebase structure
setup-firebase:
	$(PYTHON) scripts/standalone/test_firebase.py --setup

# Lint Python files
lint:
	@echo "Running flake8..."
	$(PYTHON) -m flake8 scripts/ tests/ --max-line-length=100 --ignore=E501
	@echo "Running black check..."
	$(PYTHON) -m black --check scripts/ tests/ || true

# Clean temporary files
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	find . -type f -name ".DS_Store" -delete

# Deploy to Home Assistant
# Requires: HA_HOST environment variable or edit below
HA_HOST ?= homeassistant.local
HA_USER ?= root

deploy:
	@echo "Deploying to Home Assistant at $(HA_HOST)..."
	@echo "Copying packages..."
	scp homeassistant/packages/pool_heating.yaml $(HA_USER)@$(HA_HOST):/config/packages/
	@echo "Copying pyscript..."
	scp scripts/pyscript/*.py $(HA_USER)@$(HA_HOST):/config/pyscript/
	@echo "Done! Restart Home Assistant to apply changes."

# Watch mode for development
watch:
	@echo "Watching for changes..."
	watchmedo auto-restart --patterns="*.py" --recursive -- pytest tests/ -v

# Generate documentation
docs:
	@echo "Documentation is in docs/ directory"
	@cat docs/PROJECT_PLAN.md

# Validate YAML configurations
validate-yaml:
	@echo "Validating YAML files..."
	$(PYTHON) -c "import yaml; yaml.safe_load(open('homeassistant/packages/pool_heating.yaml'))" && echo "pool_heating.yaml: OK"

# Quick status check
status:
	@echo "=== Project Status ==="
	@echo "Python: $$($(PYTHON) --version)"
	@echo "Dependencies:"
	@$(PIP) list | grep -E "(pythermiagenesis|aiohttp|firebase|pytest)" || echo "  Run 'make install' first"
	@echo ""
	@echo "Environment:"
	@test -f .env && echo "  .env: Found" || echo "  .env: Missing (copy from .env.template)"
	@test -f secrets/firebase-key.json && echo "  Firebase key: Found" || echo "  Firebase key: Missing"

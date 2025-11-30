# Lammonsaato - Pool Heating Optimizer
# Common development commands

# Use local virtualenv with .env wrapper for environment variables
ENV_WRAPPER = ./scripts/run-with-env.sh
PYTHON = $(ENV_WRAPPER) ./env/bin/python
PIP = ./env/bin/pip

# Default configuration (override with environment variables or .env)
THERMIA_HOST ?= 192.168.50.10
HA_HOST ?= homeassistant.local
HA_USER ?= root

.PHONY: help install test test-unit test-thermia test-nordpool test-firebase \
        test-integration test-ha test-ha-entities test-ha-schedule test-ha-workflow \
        test-all lint clean deploy status validate-yaml build dist

# Default target
help:
	@echo "Lammonsaato - Pool Heating Optimizer"
	@echo ""
	@echo "Setup:"
	@echo "  install          Install Python dependencies"
	@echo "  status           Show project status"
	@echo ""
	@echo "Unit Tests (no external dependencies):"
	@echo "  test             Run all pytest unit tests"
	@echo "  test-unit        Alias for test"
	@echo "  test-algorithm-unit  Test price optimization algorithm"
	@echo "  test-yaml        Test HA YAML templates and conditions"
	@echo ""
	@echo "Live Integration Tests:"
	@echo "  test-thermia     Test Thermia Modbus connection"
	@echo "  test-nordpool    Test Nordpool API (live prices)"
	@echo "  test-integration Full integration test (Thermia + Nordpool + Algorithm)"
	@echo ""
	@echo "Home Assistant Tests (requires HA_URL and HA_TOKEN):"
	@echo "  test-ha          Test HA connection"
	@echo "  test-ha-entities List all pool heating entities"
	@echo "  test-ha-schedule Test schedule calculation (calls pyscript)"
	@echo "  test-ha-workflow Test full workflow (DRY RUN)"
	@echo "  test-ha-monitor  Monitor heating session via WebSocket"
	@echo ""
	@echo "All Tests:"
	@echo "  test-all         Run all tests (unit + integration + HA)"
	@echo ""
	@echo "Build & Deployment:"
	@echo "  build            Build distribution package in dist/"
	@echo "  deploy           Deploy to Home Assistant via SSH"
	@echo "  validate-yaml    Validate YAML configuration files"
	@echo ""
	@echo "Other:"
	@echo "  lint             Run linting checks"
	@echo "  clean            Clean up temporary files"
	@echo ""
	@echo "Environment Variables:"
	@echo "  THERMIA_HOST     Thermia IP (default: 192.168.50.10)"
	@echo "  HA_URL           Home Assistant URL"
	@echo "  HA_TOKEN         Home Assistant long-lived token"
	@echo "  TEST_DRY_RUN     Set to 'false' for live hardware control"
	@echo ""

# ============================================
# SETUP
# ============================================

install:
	$(PIP) install -r requirements.txt

status:
	@echo "=== Project Status ==="
	@echo ""
	@echo "Python: $$($(PYTHON) --version 2>&1)"
	@echo ""
	@echo "Dependencies:"
	@$(PIP) list 2>/dev/null | grep -E "(pythermiagenesis|aiohttp|firebase|pytest|requests|websockets)" || echo "  Run 'make install' first"
	@echo ""
	@echo "Configuration:"
	@echo "  THERMIA_HOST: $(THERMIA_HOST)"
	@echo "  HA_URL: $${HA_URL:-not set}"
	@echo "  HA_TOKEN: $${HA_TOKEN:+[set]}"
	@test -f .env && echo "  .env file: Found" || echo "  .env file: Missing (copy from .env.template)"
	@echo ""

# ============================================
# UNIT TESTS (no external dependencies)
# ============================================

test:
	$(PYTHON) -m pytest tests/ -v

test-unit: test

# Test just the price optimizer algorithm
test-algorithm-unit:
	$(PYTHON) -m pytest tests/test_price_optimizer.py -v

# Test the HA YAML configuration (templates, conditions)
test-yaml:
	$(PYTHON) -m pytest tests/test_ha_yaml.py -v

# ============================================
# LIVE INTEGRATION TESTS
# ============================================

# Test Thermia Modbus connection
test-thermia:
	$(PYTHON) scripts/standalone/test_live_integration.py --test thermia --thermia-host $(THERMIA_HOST)

# Test Nordpool API
test-nordpool:
	$(PYTHON) scripts/standalone/test_live_integration.py --test nordpool

# Test algorithm with live Nordpool data
test-algorithm:
	$(PYTHON) scripts/standalone/test_live_integration.py --test algorithm

# Full integration test (Thermia + Nordpool + Algorithm)
test-integration:
	$(PYTHON) scripts/standalone/test_live_integration.py --test full --thermia-host $(THERMIA_HOST)

# ============================================
# HOME ASSISTANT API TESTS
# ============================================

# Test HA connection
test-ha:
	$(PYTHON) scripts/standalone/test_ha_automation.py --check

# List pool heating entities
test-ha-entities:
	$(PYTHON) scripts/standalone/test_ha_automation.py --list-entities

# Test schedule calculation (calls pyscript service)
test-ha-schedule:
	$(PYTHON) scripts/standalone/test_ha_automation.py --test-schedule

# Test full workflow (DRY RUN - won't control hardware)
test-ha-workflow:
	$(PYTHON) scripts/standalone/test_ha_automation.py --test-workflow

# Test full workflow with actual hardware control (CAREFUL!)
test-ha-workflow-live:
	@echo "WARNING: This will control actual hardware!"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	$(PYTHON) scripts/standalone/test_ha_automation.py --test-workflow --no-dry-run

# Monitor heating session via WebSocket
test-ha-monitor:
	$(PYTHON) scripts/standalone/test_ha_automation.py --monitor

# Test Thermia condenser sensors (for energy calculation)
test-ha-sensors:
	$(PYTHON) scripts/standalone/test_condenser_sensors.py

# ============================================
# ALL TESTS
# ============================================

test-all: test test-integration
	@if [ -n "$$HA_TOKEN" ]; then \
		echo "\n=== Running HA Tests ==="; \
		$(PYTHON) scripts/standalone/test_ha_automation.py --test-workflow; \
	else \
		echo "\n=== Skipping HA Tests (HA_TOKEN not set) ==="; \
	fi

# ============================================
# FIREBASE
# ============================================

test-firebase:
	$(PYTHON) scripts/standalone/test_firebase.py --test-connection

setup-firebase:
	$(PYTHON) scripts/standalone/test_firebase.py --setup

# ============================================
# CODE QUALITY
# ============================================

lint:
	@echo "Running flake8..."
	$(PYTHON) -m flake8 scripts/ tests/ --max-line-length=100 --ignore=E501,W503 || true
	@echo ""
	@echo "Running black check..."
	$(PYTHON) -m black --check scripts/ tests/ 2>/dev/null || echo "  (black not installed or files need formatting)"

format:
	$(PYTHON) -m black scripts/ tests/

# ============================================
# VALIDATION
# ============================================

validate-yaml:
	@echo "Validating YAML files..."
	@$(PYTHON) -c "\
import yaml;\
yaml.add_constructor('!secret', lambda l,n: '<secret>', Loader=yaml.SafeLoader);\
yaml.add_constructor('!include', lambda l,n: '<include>', Loader=yaml.SafeLoader);\
yaml.safe_load(open('homeassistant/packages/pool_heating.yaml'));\
print('  pool_heating.yaml: OK')" || echo "  pool_heating.yaml: FAILED"

# ============================================
# BUILD
# ============================================

build:
	@$(PYTHON) scripts/build.py

dist: build

# ============================================
# DEPLOYMENT
# ============================================

deploy:
	@echo "Deploying to Home Assistant at $(HA_HOST)..."
	@echo ""
	@echo "Copying packages..."
	scp homeassistant/packages/pool_heating.yaml $(HA_USER)@$(HA_HOST):/config/packages/
	@echo ""
	@echo "Copying pyscript..."
	ssh $(HA_USER)@$(HA_HOST) "mkdir -p /config/pyscript"
	scp scripts/pyscript/*.py $(HA_USER)@$(HA_HOST):/config/pyscript/
	@echo ""
	@echo "Done! Restart Home Assistant to apply changes."
	@echo "  ssh $(HA_USER)@$(HA_HOST) 'ha core restart'"

# ============================================
# CLEANUP
# ============================================

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	find . -type f -name ".DS_Store" -delete

# ============================================
# DEVELOPMENT HELPERS
# ============================================

# Watch for changes and run tests
watch:
	@echo "Watching for changes..."
	$(PYTHON) -m pytest_watch tests/ -- -v

# Interactive Python shell with project imports
shell:
	$(PYTHON) -i -c "import sys; sys.path.insert(0, 'scripts/standalone'); print('Imports available: ha_client, test_live_integration')"

# Show documentation
docs:
	@cat docs/PROJECT_PLAN.md

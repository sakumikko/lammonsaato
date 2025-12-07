# Mock Server WebSocket Enhancement Plan

## Overview

This document outlines the strategy for enhancing the mock server to support HA WebSocket API, enabling full E2E testing without affecting live Home Assistant data.

## Problem Statement

Currently:
- Mock server only supports REST API + basic WebSocket broadcast
- Web UI's Index page uses `useHomeAssistant` which requires HA WebSocket API
- Settings sliders (and other features) cannot be E2E tested safely
- No entity signature validation between mock and live HA

## Goals

1. Implement HA-compatible WebSocket API in mock server
2. Create entity discovery tool to validate mock matches live HA
3. Enable full E2E testing of all UI components
4. Prevent entity drift between mock and production

---

## Phase 1: Entity Discovery & Validation

### 1.1 Entity Signature Schema

Entity signatures are stored in a committed JSON file with support for:
- **Development entities**: Marked as `deployed: false`, skipped during live validation
- **Offline mode**: Uses committed signatures when HA is unreachable
- **Version tracking**: Track when signatures were last verified

```json
// scripts/mock_server/entity_signatures.json
{
  "version": 2,
  "last_verified": "2024-12-07T12:00:00Z",
  "ha_version": "2024.1.0",
  "entities": [
    {
      "entity_id": "input_number.pool_heating_total_hours",
      "domain": "input_number",
      "state_type": "numeric",
      "deployed": true,
      "min_value": 0,
      "max_value": 5,
      "step": 0.5,
      "notes": null
    },
    {
      "entity_id": "input_number.pool_heating_new_feature",
      "domain": "input_number",
      "state_type": "numeric",
      "deployed": false,
      "min_value": 0,
      "max_value": 100,
      "notes": "In development - not yet deployed to HA"
    }
  ]
}
```

### 1.2 Entity Discovery Script

Create a script that connects to live HA and extracts entity metadata:

```python
# scripts/tools/discover_entities.py

"""
Discovers all pool heating entities from live Home Assistant.
Exports entity signatures for mock server validation.

Usage:
    python -m scripts.tools.discover_entities --output entities.json

Environment:
    HA_URL - Home Assistant URL (e.g., http://192.168.50.11:8123)
    HA_TOKEN - Long-lived access token
"""

import asyncio
import json
import os
from dataclasses import dataclass, asdict
from typing import Any
import aiohttp

@dataclass
class EntitySignature:
    entity_id: str
    domain: str  # input_number, sensor, switch, etc.
    state_type: str  # "numeric", "boolean", "string", "datetime"
    attributes: list[str]  # List of attribute names
    unit_of_measurement: str | None
    min_value: float | None  # For input_number
    max_value: float | None
    step: float | None
    options: list[str] | None  # For input_select

POOL_HEATING_PREFIXES = [
    "input_boolean.pool_heat",
    "input_boolean.pool_heating",
    "input_number.pool_heat",
    "input_number.pool_heating",
    "input_number.pool_target",
    "input_number.pool_true",
    "input_datetime.pool_heat",
    "input_text.pool_heating",
    "sensor.pool_heat",
    "sensor.pool_heating",
    "sensor.pool_thermal",
    "sensor.pool_return",
    "sensor.pool_next",
    "sensor.current_nordpool",
    "binary_sensor.pool_",
    "binary_sensor.nordpool",
    "switch.altaan_",
    "sensor.condenser_",
    "sensor.outdoor_temperature",
    "sensor.compressor_speed",
    "sensor.nordpool_kwh",
    "number.minimum_allowed_gear",
    "number.maximum_allowed_gear",
    "number.tap_water_",
    "number.hot_gas_",
    "number.heat_curve_",
]

async def discover_entities(ha_url: str, token: str) -> list[EntitySignature]:
    """Connect to HA and discover all pool heating entities."""
    signatures = []

    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {token}"}

        # Get all states
        async with session.get(f"{ha_url}/api/states", headers=headers) as resp:
            states = await resp.json()

        for state in states:
            entity_id = state["entity_id"]

            # Filter to pool heating entities
            if not any(entity_id.startswith(prefix) for prefix in POOL_HEATING_PREFIXES):
                continue

            domain = entity_id.split(".")[0]
            attrs = state.get("attributes", {})

            sig = EntitySignature(
                entity_id=entity_id,
                domain=domain,
                state_type=infer_state_type(state["state"], domain),
                attributes=list(attrs.keys()),
                unit_of_measurement=attrs.get("unit_of_measurement"),
                min_value=attrs.get("min"),
                max_value=attrs.get("max"),
                step=attrs.get("step"),
                options=attrs.get("options"),
            )
            signatures.append(sig)

    return signatures

def infer_state_type(state: str, domain: str) -> str:
    """Infer the state type from domain and value."""
    if domain in ("binary_sensor", "input_boolean", "switch"):
        return "boolean"
    if domain == "input_datetime":
        return "datetime"
    if domain == "input_text":
        return "string"
    try:
        float(state)
        return "numeric"
    except (ValueError, TypeError):
        return "string"

async def main():
    ha_url = os.environ.get("HA_URL", "http://192.168.50.11:8123")
    token = os.environ["HA_TOKEN"]

    entities = await discover_entities(ha_url, token)

    # Export to JSON
    output = {
        "version": 1,
        "entity_count": len(entities),
        "entities": [asdict(e) for e in entities]
    }

    with open("scripts/mock_server/entity_signatures.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"Discovered {len(entities)} entities")

    # Print summary by domain
    by_domain = {}
    for e in entities:
        by_domain.setdefault(e.domain, []).append(e.entity_id)

    for domain, ids in sorted(by_domain.items()):
        print(f"  {domain}: {len(ids)}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 1.3 Entity Signature Validation

Add validation with support for offline mode and development entities:

```python
# scripts/mock_server/entity_validator.py

from enum import Enum
from dataclasses import dataclass
import json
import logging
from pathlib import Path

class ValidationMode(Enum):
    STRICT = "strict"        # Fail on any mismatch (deployed entities only)
    WARN = "warn"            # Log warnings but don't fail
    SKIP = "skip"            # Skip validation entirely

@dataclass
class ValidationResult:
    errors: list[str]        # Hard failures (deployed entity mismatch)
    warnings: list[str]      # Soft issues (extra mock entities, dev entities)
    dev_entities: list[str]  # Entities marked as not deployed

SIGNATURE_FILE = Path(__file__).parent / "entity_signatures.json"

def load_signatures() -> dict:
    """
    Load entity signatures from committed file.
    This file is always available (committed to git), enabling offline development.
    """
    if not SIGNATURE_FILE.exists():
        logging.warning(f"Signature file not found: {SIGNATURE_FILE}")
        return {"entities": [], "version": 0}

    with open(SIGNATURE_FILE) as f:
        return json.load(f)

def validate_mock_entities(
    mock_entities: dict,
    mode: ValidationMode = ValidationMode.WARN
) -> ValidationResult:
    """
    Compare mock server entities against committed signatures.

    Args:
        mock_entities: Dict of entity_id -> state from MockStateManager
        mode: Validation strictness level

    Returns:
        ValidationResult with errors, warnings, and dev entity list
    """
    if mode == ValidationMode.SKIP:
        return ValidationResult([], [], [])

    result = ValidationResult(errors=[], warnings=[], dev_entities=[])
    signatures = load_signatures()
    sig_map = {s["entity_id"]: s for s in signatures.get("entities", [])}

    # Check all signature entities exist in mock
    for sig in signatures.get("entities", []):
        entity_id = sig["entity_id"]
        is_deployed = sig.get("deployed", True)

        # Track development entities
        if not is_deployed:
            result.dev_entities.append(entity_id)

        if entity_id not in mock_entities:
            if is_deployed:
                result.errors.append(f"Missing deployed entity: {entity_id}")
            else:
                result.warnings.append(f"Dev entity not in mock: {entity_id}")
            continue

        mock_state = mock_entities[entity_id]

        # Validate state type (only for deployed entities in strict mode)
        if is_deployed and sig.get("state_type") == "numeric":
            try:
                float(mock_state["state"])
            except (ValueError, TypeError):
                result.errors.append(
                    f"{entity_id}: expected numeric, got '{mock_state['state']}'"
                )

        # Validate min/max for input_number (deployed only)
        if is_deployed and sig.get("min_value") is not None:
            try:
                val = float(mock_state["state"])
                if val < sig["min_value"] or val > sig["max_value"]:
                    result.warnings.append(
                        f"{entity_id}: value {val} outside [{sig['min_value']}, {sig['max_value']}]"
                    )
            except (ValueError, TypeError):
                pass

    # Check for extra entities in mock (informational)
    for entity_id in mock_entities:
        if entity_id not in sig_map:
            result.warnings.append(f"Mock has undocumented entity: {entity_id}")

    return result

def validate_or_warn(mock_entities: dict, strict: bool = False) -> bool:
    """
    Convenience function for mock server startup.

    Args:
        mock_entities: Entity states from MockStateManager
        strict: If True, raise exception on errors; if False, just log

    Returns:
        True if validation passed (no errors), False otherwise
    """
    mode = ValidationMode.STRICT if strict else ValidationMode.WARN
    result = validate_mock_entities(mock_entities, mode)

    # Log dev entities
    if result.dev_entities:
        logging.info(f"Development entities (not deployed): {len(result.dev_entities)}")
        for eid in result.dev_entities:
            logging.debug(f"  - {eid}")

    # Log warnings
    for warning in result.warnings:
        logging.warning(f"Entity validation: {warning}")

    # Handle errors
    if result.errors:
        msg = f"Entity validation failed with {len(result.errors)} errors:\n"
        msg += "\n".join(f"  - {e}" for e in result.errors)

        if strict:
            raise ValueError(msg)
        else:
            logging.error(msg)
            return False

    return True
```

### 1.4 Offline Development Workflow

The validation system supports fully offline development:

```
┌─────────────────────────────────────────────────────────────────┐
│ ONLINE (connected to live HA)                                   │
├─────────────────────────────────────────────────────────────────┤
│ 1. Run: python -m scripts.tools.discover_entities               │
│ 2. Review changes to entity_signatures.json                     │
│ 3. Commit updated signatures to git                             │
│ 4. CI validates mock against committed signatures               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ OFFLINE (no HA connection)                                      │
├─────────────────────────────────────────────────────────────────┤
│ 1. Mock server uses committed entity_signatures.json            │
│ 2. Development entities marked "deployed: false" are allowed    │
│ 3. Tests run against mock server without network                │
│ 4. CI passes using committed signatures                         │
└─────────────────────────────────────────────────────────────────┘
```

### 1.5 Adding New Entities (Development Workflow)

When developing a new feature that needs new HA entities:

```bash
# Step 1: Add entity to mock server's StateManager
# In scripts/mock_server/state_manager.py:
self._add_entity("input_number.pool_heating_new_feature", "50", min=0, max=100)

# Step 2: Add to entity_signatures.json with deployed: false
{
  "entity_id": "input_number.pool_heating_new_feature",
  "domain": "input_number",
  "state_type": "numeric",
  "deployed": false,
  "min_value": 0,
  "max_value": 100,
  "notes": "New feature - deploy to HA before marking deployed: true"
}

# Step 3: Develop and test against mock server
make mock-server
npm run dev:test
npm run e2e

# Step 4: Deploy entity to HA (add to pool_heating.yaml)
# Step 5: Verify with discovery script
python -m scripts.tools.discover_entities --verify

# Step 6: Mark entity as deployed
# Change "deployed": false to "deployed": true in entity_signatures.json

# Step 7: Commit all changes
git add homeassistant/packages/pool_heating.yaml
git add scripts/mock_server/entity_signatures.json
git commit -m "feat: add pool_heating_new_feature entity"
```

---

## Phase 2: HA WebSocket API Implementation

### 2.1 Message Protocol

Implement HA WebSocket message format:

```python
# scripts/mock_server/ha_websocket.py

from dataclasses import dataclass
from typing import Any
import json

@dataclass
class HAMessage:
    """Home Assistant WebSocket message."""
    id: int | None = None
    type: str = ""

    # For requests
    domain: str | None = None
    service: str | None = None
    service_data: dict | None = None
    target: dict | None = None
    event_type: str | None = None

    # For responses
    success: bool | None = None
    result: Any = None
    error: dict | None = None
    event: dict | None = None

class HAWebSocketHandler:
    """
    Handles HA WebSocket protocol.

    Message flow:
    1. Client connects
    2. Server sends: {"type": "auth_required", "ha_version": "..."}
    3. Client sends: {"type": "auth", "access_token": "..."}
    4. Server sends: {"type": "auth_ok", "ha_version": "..."}
    5. Client sends commands with incrementing IDs
    6. Server responds with matching IDs
    """

    def __init__(self, state_manager: "MockStateManager"):
        self.state = state_manager
        self.subscriptions: dict[int, str] = {}  # id -> event_type
        self.next_event_id = 1

    async def handle_message(self, raw: str) -> list[dict]:
        """Process incoming message, return responses."""
        msg = json.loads(raw)
        msg_type = msg.get("type")
        msg_id = msg.get("id")

        responses = []

        if msg_type == "auth":
            # Accept any token in mock mode
            responses.append({
                "type": "auth_ok",
                "ha_version": "2024.1.0-mock"
            })

        elif msg_type == "get_states":
            # Return all entity states
            states = self.state.get_all_entity_states()
            responses.append({
                "id": msg_id,
                "type": "result",
                "success": True,
                "result": states
            })

        elif msg_type == "subscribe_events":
            # Subscribe to state changes
            event_type = msg.get("event_type", "state_changed")
            self.subscriptions[msg_id] = event_type
            responses.append({
                "id": msg_id,
                "type": "result",
                "success": True,
                "result": None
            })

        elif msg_type == "call_service":
            # Handle service calls
            domain = msg.get("domain")
            service = msg.get("service")
            data = msg.get("service_data", {})
            target = msg.get("target", {})

            try:
                result = await self.state.call_service(domain, service, data, target)
                responses.append({
                    "id": msg_id,
                    "type": "result",
                    "success": True,
                    "result": result
                })
            except Exception as e:
                responses.append({
                    "id": msg_id,
                    "type": "result",
                    "success": False,
                    "error": {"code": "service_error", "message": str(e)}
                })

        elif msg_type == "recorder/statistics_during_period":
            # Return empty stats for now
            responses.append({
                "id": msg_id,
                "type": "result",
                "success": True,
                "result": {}
            })

        return responses

    def create_state_changed_event(self, entity_id: str, old_state: dict, new_state: dict) -> dict:
        """Create a state_changed event for broadcast."""
        event_id = self.next_event_id
        self.next_event_id += 1

        return {
            "type": "event",
            "event": {
                "event_type": "state_changed",
                "data": {
                    "entity_id": entity_id,
                    "old_state": old_state,
                    "new_state": new_state
                },
                "origin": "LOCAL",
                "time_fired": datetime.now(timezone.utc).isoformat()
            }
        }
```

### 2.2 State Manager

Centralized entity state management:

```python
# scripts/mock_server/state_manager.py

class MockStateManager:
    """Manages entity states for mock HA."""

    def __init__(self):
        self.entities: dict[str, HAEntityState] = {}
        self.change_listeners: list[Callable] = []
        self._init_entities()

    def _init_entities(self):
        """Initialize all pool heating entities with defaults."""
        # Input booleans
        self._add_entity("input_boolean.pool_heating_enabled", "off")
        self._add_entity("input_boolean.pool_heating_night_complete", "off")
        self._add_entity("input_boolean.pool_heating_cost_limit_applied", "off")

        for i in range(1, 11):
            self._add_entity(f"input_boolean.pool_heat_block_{i}_enabled", "off")
            self._add_entity(f"input_boolean.pool_heat_block_{i}_cost_exceeded", "off")

        # Input numbers
        self._add_entity("input_number.pool_heating_min_block_duration", "30",
                        min=30, max=60, step=5)
        self._add_entity("input_number.pool_heating_max_block_duration", "45",
                        min=30, max=60, step=5)
        self._add_entity("input_number.pool_heating_total_hours", "2",
                        min=0, max=5, step=0.5)
        self._add_entity("input_number.pool_heating_max_cost_eur", "0",
                        min=0, max=10, step=0.1)
        self._add_entity("input_number.pool_target_temperature", "28",
                        min=20, max=35, step=0.5)

        for i in range(1, 11):
            self._add_entity(f"input_number.pool_heat_block_{i}_price", "0",
                            min=0, max=100, step=0.01)
            self._add_entity(f"input_number.pool_heat_block_{i}_cost", "0",
                            min=0, max=10, step=0.01)

        # Input datetimes
        for i in range(1, 11):
            self._add_entity(f"input_datetime.pool_heat_block_{i}_start", "")
            self._add_entity(f"input_datetime.pool_heat_block_{i}_end", "")

        # Sensors (read-only)
        self._add_entity("sensor.pool_heating_block_count", "0")
        self._add_entity("sensor.pool_heating_enabled_block_count", "0")
        self._add_entity("sensor.pool_next_heating", "unknown")
        self._add_entity("sensor.nordpool_kwh_fi_eur_3_10_0255", "0.05",
                        attrs={"current_price": 5.0, "raw_today": [], "raw_tomorrow": []})

        # Thermia sensors (simulated)
        self._add_entity("sensor.condenser_out_temperature", "35.0", unit="°C")
        self._add_entity("sensor.condenser_in_temperature", "30.0", unit="°C")

        # Heat pump number entities (gear limits, temps)
        self._add_entity("number.minimum_allowed_gear_in_heating", "1", min=1, max=10)
        self._add_entity("number.maximum_allowed_gear_in_heating", "10", min=1, max=10)
        self._add_entity("number.minimum_allowed_gear_in_pool", "1", min=1, max=10)
        self._add_entity("number.maximum_allowed_gear_in_pool", "10", min=1, max=10)
        self._add_entity("number.tap_water_start_temperature", "45", min=35, max=55)
        self._add_entity("number.tap_water_stop_temperature", "55", min=40, max=65)
        self._add_entity("number.hot_gas_pump_start_temperature", "70", min=50, max=100)
        self._add_entity("number.hot_gas_lower_stop_limit", "60", min=40, max=90)
        self._add_entity("number.hot_gas_upper_stop_limit", "100", min=70, max=120)
        self._add_entity("number.heat_curve_max_limitation", "55", min=35, max=65)
        self._add_entity("number.heat_curve_min_limitation", "25", min=15, max=40)

    def _add_entity(self, entity_id: str, state: str, **attrs):
        """Add an entity with state and attributes."""
        self.entities[entity_id] = {
            "entity_id": entity_id,
            "state": state,
            "attributes": {
                "friendly_name": entity_id.split(".")[-1].replace("_", " ").title(),
                **attrs
            },
            "last_changed": datetime.now(timezone.utc).isoformat(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    async def call_service(self, domain: str, service: str, data: dict, target: dict) -> None:
        """Handle service calls, update entity states."""
        entity_ids = target.get("entity_id", [])
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]

        for entity_id in entity_ids:
            if entity_id not in self.entities:
                raise ValueError(f"Unknown entity: {entity_id}")

            old_state = dict(self.entities[entity_id])

            if domain in ("input_boolean", "switch"):
                if service == "turn_on":
                    self.entities[entity_id]["state"] = "on"
                elif service == "turn_off":
                    self.entities[entity_id]["state"] = "off"
                elif service == "toggle":
                    current = self.entities[entity_id]["state"]
                    self.entities[entity_id]["state"] = "off" if current == "on" else "on"

            elif domain in ("input_number", "number"):
                if service == "set_value":
                    value = data.get("value")
                    self.entities[entity_id]["state"] = str(value)

            # Update timestamps
            now = datetime.now(timezone.utc).isoformat()
            self.entities[entity_id]["last_changed"] = now
            self.entities[entity_id]["last_updated"] = now

            # Notify listeners
            new_state = self.entities[entity_id]
            for listener in self.change_listeners:
                await listener(entity_id, old_state, new_state)

    def get_all_entity_states(self) -> list[dict]:
        """Return all entity states in HA format."""
        return list(self.entities.values())
```

### 2.3 WebSocket Server Integration

Update FastAPI server to serve HA-compatible WebSocket:

```python
# In scripts/mock_server/server.py

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from .ha_websocket import HAWebSocketHandler
from .state_manager import MockStateManager

app = FastAPI()
state_manager = MockStateManager()
connected_clients: set[WebSocket] = set()

@app.websocket("/api/websocket")
async def ha_websocket_endpoint(websocket: WebSocket):
    """
    HA-compatible WebSocket endpoint.

    This replaces the existing /ws endpoint for clients using useHomeAssistant.
    """
    await websocket.accept()
    connected_clients.add(websocket)

    handler = HAWebSocketHandler(state_manager)

    # Send auth_required immediately
    await websocket.send_json({
        "type": "auth_required",
        "ha_version": "2024.1.0-mock"
    })

    try:
        while True:
            raw = await websocket.receive_text()
            responses = await handler.handle_message(raw)

            for response in responses:
                await websocket.send_json(response)

    except WebSocketDisconnect:
        connected_clients.discard(websocket)

# State change broadcaster
async def broadcast_state_change(entity_id: str, old_state: dict, new_state: dict):
    """Broadcast state changes to all connected clients."""
    event = {
        "type": "event",
        "event": {
            "event_type": "state_changed",
            "data": {
                "entity_id": entity_id,
                "old_state": old_state,
                "new_state": new_state
            }
        }
    }

    for client in list(connected_clients):
        try:
            await client.send_json(event)
        except:
            connected_clients.discard(client)

# Register broadcaster
state_manager.change_listeners.append(broadcast_state_change)
```

---

## Phase 3: Vite Proxy Configuration

### 3.1 Configure Vite to Proxy to Mock Server

Update `web-ui/vite.config.ts`:

```typescript
export default defineConfig(({ mode }) => ({
  // ... existing config ...

  server: {
    host: "::",
    port: 8080,
    proxy: mode === 'test' ? {
      // In test mode, proxy HA API to mock server
      '/api/websocket': {
        target: 'ws://localhost:8765',
        ws: true,
        rewrite: (path) => '/api/websocket'
      },
      '/api': {
        target: 'http://localhost:8765',
        changeOrigin: true
      }
    } : undefined
  }
}));
```

### 3.2 Add Test Mode Script

In `package.json`:

```json
{
  "scripts": {
    "dev": "vite",
    "dev:test": "vite --mode test",
    "e2e": "BASE_URL=http://localhost:8080 playwright test"
  }
}
```

---

## Phase 4: Testing Strategy

### 4.1 Test Hierarchy

```
Unit Tests (Python)
└── Test schedule algorithm
└── Test cost calculations
└── Test entity signature validation

Integration Tests (Python + Mock Server)
└── Test WebSocket message handling
└── Test service call state updates
└── Test state change broadcasting

E2E Tests (Playwright + Mock Server)
└── Settings sliders
└── Schedule editor
└── Block management
└── Cost constraints
```

### 4.2 E2E Test Setup

```typescript
// web-ui/e2e/fixtures.ts

import { test as base } from '@playwright/test';

export const test = base.extend({
  // Auto-reset mock server before each test
  page: async ({ page }, use) => {
    // Reset mock server state
    await page.request.post('http://localhost:8765/api/reset');
    await use(page);
  }
});

// Example test using fixtures
test('slider should save to mock server', async ({ page }) => {
  await page.goto('/');

  // Open settings
  await page.getByTitle('Heat Pump Settings').click();
  await expect(page.getByRole('dialog')).toBeVisible();

  // Change slider
  const slider = page.locator('[role="slider"]').first();
  await slider.focus();
  await slider.press('ArrowRight');

  // Wait for save
  await expect(page.locator('[data-testid="slider-success"]')).toBeVisible();

  // Verify server state updated
  const response = await page.request.get('http://localhost:8765/api/states');
  const states = await response.json();
  // ... verify entity value changed
});
```

### 4.3 Entity Signature Test

```python
# tests/test_entity_signatures.py

import pytest
from scripts.tools.discover_entities import discover_entities
from scripts.mock_server.state_manager import MockStateManager

@pytest.mark.integration
async def test_mock_matches_live_ha():
    """Verify mock server entities match live HA signatures."""
    # Skip if no HA connection
    if not os.environ.get("HA_TOKEN"):
        pytest.skip("HA_TOKEN not set")

    # Get live signatures
    live_entities = await discover_entities(
        os.environ["HA_URL"],
        os.environ["HA_TOKEN"]
    )
    live_ids = {e.entity_id for e in live_entities}

    # Get mock entities
    manager = MockStateManager()
    mock_ids = set(manager.entities.keys())

    # Check coverage
    missing = live_ids - mock_ids
    assert not missing, f"Mock missing entities: {missing}"

    # Check types match
    for entity in live_entities:
        mock_state = manager.entities[entity.entity_id]
        if entity.state_type == "numeric":
            assert mock_state["state"].replace(".", "").isdigit(), \
                f"{entity.entity_id}: expected numeric state"
```

---

## Phase 5: CI/CD Integration

### 5.1 GitHub Actions Workflow

The CI workflow uses committed signatures (offline mode) - no live HA connection required:

```yaml
# .github/workflows/e2e.yml

name: E2E Tests

on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Python deps
        run: pip install -r requirements.txt

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install web-ui deps
        run: cd web-ui && npm ci

      - name: Install Playwright
        run: cd web-ui && npx playwright install chromium

      - name: Start mock server
        run: |
          # Mock server uses committed entity_signatures.json
          # No live HA connection needed - fully offline
          python -m scripts.mock_server &
          sleep 5

      - name: Start web UI (test mode)
        run: |
          cd web-ui && npm run dev:test &
          sleep 10

      - name: Run E2E tests
        run: cd web-ui && npm run e2e

      - name: Upload test results
        uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: playwright-report
          path: web-ui/playwright-report/

  # Optional: verify signatures against live HA (manual trigger only)
  verify-signatures:
    runs-on: ubuntu-latest
    if: github.event_name == 'workflow_dispatch'

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install deps
        run: pip install aiohttp

      - name: Verify signatures against live HA
        env:
          HA_URL: ${{ secrets.HA_URL }}
          HA_TOKEN: ${{ secrets.HA_TOKEN }}
        run: |
          if [ -n "$HA_TOKEN" ]; then
            python -m scripts.tools.discover_entities --verify
          else
            echo "HA_TOKEN not set - skipping live verification"
          fi
```

### 5.2 Validation Modes in CI

| Mode | When Used | Behavior |
|------|-----------|----------|
| **Offline (default)** | All CI runs | Uses committed signatures, no HA needed |
| **Verify** | Manual trigger | Compares live HA against committed signatures |
| **Strict** | Pre-release | Fails if any deployed entity mismatches |

### 5.3 Local Development Commands

```bash
# Start mock server (uses committed signatures, offline)
make mock-server

# Start mock server with strict validation (fails on errors)
MOCK_STRICT=1 make mock-server

# Update signatures from live HA (requires HA_TOKEN)
python -m scripts.tools.discover_entities --output scripts/mock_server/entity_signatures.json

# Verify mock matches live HA without updating
python -m scripts.tools.discover_entities --verify

# Show signature diff (what changed since last commit)
python -m scripts.tools.discover_entities --diff
```

---

## Implementation Checklist

### Phase 1: Entity Discovery & Validation
- [ ] Create `scripts/mock_server/entity_signatures.json` schema
- [ ] Create `scripts/tools/discover_entities.py` with CLI options:
  - `--output FILE` - Write discovered entities to file
  - `--verify` - Compare live HA against committed signatures
  - `--diff` - Show what changed since last commit
- [ ] Create `scripts/mock_server/entity_validator.py` with:
  - `ValidationMode` enum (STRICT, WARN, SKIP)
  - `deployed: false` support for development entities
  - Offline mode using committed signatures
- [ ] Run initial discovery against live HA
- [ ] Commit initial `entity_signatures.json`
- [ ] Add validation to mock server startup (warn mode by default)

### Phase 2: WebSocket API
- [ ] Create `scripts/mock_server/ha_websocket.py`
- [ ] Create `scripts/mock_server/state_manager.py`
- [ ] Add `/api/websocket` endpoint
- [ ] Implement `auth` flow
- [ ] Implement `get_states`
- [ ] Implement `subscribe_events`
- [ ] Implement `call_service` for all domains
- [ ] Implement state change broadcasting

### Phase 3: Vite Integration
- [ ] Add proxy config for test mode
- [ ] Add `dev:test` npm script
- [ ] Test WebSocket proxying works

### Phase 4: Tests
- [ ] Move settings-sliders tests to use mock server
- [ ] Add entity signature validation test
- [ ] Verify all E2E tests pass against mock

### Phase 5: CI/CD
- [ ] Add GitHub Actions workflow
- [ ] Configure artifact upload on failure
- [ ] Add entity signature check to CI

---

## Timeline Estimate

| Phase | Effort | Dependencies |
|-------|--------|--------------|
| Phase 1: Entity Discovery | 2-4 hours | HA access |
| Phase 2: WebSocket API | 8-12 hours | Phase 1 |
| Phase 3: Vite Integration | 1-2 hours | Phase 2 |
| Phase 4: Tests | 4-6 hours | Phase 3 |
| Phase 5: CI/CD | 2-3 hours | Phase 4 |

**Total: 17-27 hours**

---

## Risk Mitigation

1. **Entity drift**: Run signature discovery weekly, fail CI if mismatch
2. **WebSocket complexity**: Start with minimal protocol, add features incrementally
3. **State consistency**: Use single source of truth (MockStateManager)
4. **Race conditions**: Implement message queuing with async locks

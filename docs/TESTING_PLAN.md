# Testing Plan - External Testing with Live Data

## Overview

This plan enables testing the pool heating system outside of Home Assistant OS using:
- **Live Thermia Modbus** - Direct connection to heat pump
- **Live Nordpool API** - Real electricity prices
- **HA REST/WebSocket API** - Control and monitor HA entities remotely

## Testing Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                    TESTING LAYERS                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Layer 1: Unit Tests (No external dependencies)                 │
│  ├── Price optimization algorithm                               │
│  ├── Schedule calculation logic                                 │
│  └── Data transformation functions                              │
│                                                                  │
│  Layer 2: Integration Tests (Live external services)            │
│  ├── Thermia Modbus - Read real sensor values                   │
│  ├── Nordpool API - Fetch real prices                           │
│  └── Algorithm with real data                                   │
│                                                                  │
│  Layer 3: HA Integration Tests (Requires running HA)            │
│  ├── Read HA entity states via REST API                         │
│  ├── Call HA services (switch control, scripts)                 │
│  ├── Trigger automations                                        │
│  └── End-to-end workflow validation                             │
│                                                                  │
│  Layer 4: System Tests (Full integration)                       │
│  ├── Simulate full heating cycle                                │
│  ├── Monitor temperature changes                                │
│  └── Validate data logging                                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Test Commands

```bash
# Layer 1: Unit tests (no dependencies)
make test

# Layer 2: Live integration tests
make test-thermia          # Test Thermia connection
make test-nordpool         # Test Nordpool API
make test-integration      # Full integration tests

# Layer 3: HA API tests (requires HA running)
make test-ha               # Test HA connection
make test-ha-services      # Test service calls

# Layer 4: System tests
make test-system           # Full system test (careful - controls real hardware!)
```

## Configuration

Set environment variables or create `.env`:

```bash
# Thermia Heat Pump
THERMIA_HOST=192.168.50.10
THERMIA_PORT=502

# Home Assistant (for API tests)
HA_URL=http://homeassistant.local:8123
HA_TOKEN=your_long_lived_access_token

# Test mode (prevents actual hardware control)
TEST_DRY_RUN=true
```

## Safety Considerations

1. **DRY_RUN mode** - Default for all hardware control tests
2. **Confirmation prompts** - For any test that controls real hardware
3. **Timeouts** - All operations have reasonable timeouts
4. **Rollback** - Tests restore original state when possible

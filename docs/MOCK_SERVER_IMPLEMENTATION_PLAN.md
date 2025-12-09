# Mock Server WebSocket Implementation Plan

**Purpose:** Executable plan for Claude to implement independently.
**Goal:** Make mock server speak HA WebSocket API so `useHomeAssistant.ts` works with it.

---

## Current State Analysis

| Component | Current State | Target State |
|-----------|--------------|--------------|
| Mock Server REST | ✅ Complete | Keep as-is |
| Mock Server WebSocket | Custom protocol (`/ws`) | HA protocol (`/api/websocket`) |
| `useMockServer.ts` | Works with custom protocol | Keep for backward compat |
| `useHomeAssistant.ts` | Requires real HA | Works with mock server |
| Entity signatures | None | Validated against live HA |
| E2E tests | Use `useMockServer` | Use `useHomeAssistant` via mock |

---

## Phase 1: Entity Discovery & Signatures

**Objective:** Create entity signature system for validation.

### Step 1.1: Create Entity Signature Schema

**File:** `scripts/mock_server/entity_signatures.json`

```bash
# Verification command after creation:
cat scripts/mock_server/entity_signatures.json | python -m json.tool > /dev/null && echo "Valid JSON"
```

**Acceptance Criteria:**
- [ ] JSON file exists and is valid
- [ ] Contains `version`, `last_verified`, `entities` array
- [ ] Each entity has: `entity_id`, `domain`, `state_type`, `deployed`
- [ ] Development entities marked `deployed: false`

### Step 1.2: Create Entity Discovery Script

**File:** `scripts/tools/discover_entities.py`

**Required functionality:**
1. Connect to live HA via REST API
2. Filter pool heating entities by prefix
3. Extract entity metadata (domain, type, min/max, unit)
4. Output to JSON file
5. CLI flags: `--output`, `--verify`, `--diff`

```bash
# Verification commands:
./env/bin/python -m scripts.tools.discover_entities --help
# Should show: --output, --verify, --diff options

# Test with live HA (requires HA_TOKEN):
HA_TOKEN="..." ./env/bin/python -m scripts.tools.discover_entities --output /tmp/test_entities.json
```

**Acceptance Criteria:**
- [ ] Script runs without errors
- [ ] Discovers 50+ pool heating entities from live HA
- [ ] Outputs valid JSON with correct schema
- [ ] `--verify` mode compares against committed signatures
- [ ] `--diff` mode shows changes since last commit

### Step 1.3: Create Entity Validator

**File:** `scripts/mock_server/entity_validator.py`

**Required functionality:**
1. `ValidationMode` enum: STRICT, WARN, SKIP
2. `load_signatures()` - Load from committed JSON
3. `validate_mock_entities()` - Compare mock vs signatures
4. Handle `deployed: false` entities (skip in strict mode)
5. Return `ValidationResult` with errors, warnings, dev_entities

```bash
# Verification:
./env/bin/python -c "from scripts.mock_server.entity_validator import validate_mock_entities, ValidationMode; print('OK')"
```

**Acceptance Criteria:**
- [ ] Imports without errors
- [ ] Validates mock entities against signatures
- [ ] Deployed entities cause errors on mismatch
- [ ] Undeployed entities only cause warnings
- [ ] Works offline with committed signatures

### Step 1.4: Run Initial Discovery

```bash
# Run against live HA:
HA_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI5YzYzODZjMWUwN2I0YWJmYTZmNTU4NGVhNDI1ZmQ3MSIsImlhdCI6MTc2NDQzMjk0MiwiZXhwIjoyMDc5NzkyOTQyfQ.A7LLK57awAb8PdDxbjHiwLmPJte29TCvp-y71FFRHCc" \
HA_URL="http://192.168.50.11:8123" \
./env/bin/python -m scripts.tools.discover_entities --output scripts/mock_server/entity_signatures.json

# Verify output:
cat scripts/mock_server/entity_signatures.json | head -50
```

**Acceptance Criteria:**
- [ ] `entity_signatures.json` committed to git
- [ ] Contains all pool heating entities
- [ ] Each entity has correct metadata

---

## Phase 2: HA WebSocket API Implementation

**Objective:** Add HA-compatible WebSocket endpoint to mock server.

### Step 2.1: Create State Manager Module

**File:** `scripts/mock_server/state_manager.py`

**Required functionality:**
1. `MockStateManager` class
2. `HAEntityState` format matching HA API
3. Initialize all pool heating entities with defaults
4. `call_service()` method for state mutations
5. `get_all_entity_states()` returning HA-format list
6. Change listeners for broadcasting

```bash
# Verification:
./env/bin/python -c "
from scripts.mock_server.state_manager import MockStateManager
mgr = MockStateManager()
states = mgr.get_all_entity_states()
print(f'Initialized {len(states)} entities')
assert len(states) > 50, 'Expected 50+ entities'
print('OK')
"
```

**Acceptance Criteria:**
- [ ] Manages 50+ entities
- [ ] Returns HA-format state objects
- [ ] `call_service()` updates state correctly
- [ ] Notifies listeners on state change

### Step 2.2: Create HA WebSocket Handler

**File:** `scripts/mock_server/ha_websocket.py`

**Required message types:**
1. `auth_required` → `auth` → `auth_ok` flow
2. `get_states` → returns all entity states
3. `subscribe_events` → registers for state_changed
4. `call_service` → calls StateManager
5. `recorder/statistics_during_period` → returns empty (stub)

```bash
# Verification:
./env/bin/python -c "
from scripts.mock_server.ha_websocket import HAWebSocketHandler
from scripts.mock_server.state_manager import MockStateManager
mgr = MockStateManager()
handler = HAWebSocketHandler(mgr)
print('OK')
"
```

**Acceptance Criteria:**
- [ ] Implements HA WebSocket protocol
- [ ] Auth flow works (accepts any token in mock mode)
- [ ] `get_states` returns all entities
- [ ] `call_service` updates state
- [ ] Broadcasts `state_changed` events

### Step 2.3: Add WebSocket Endpoint to Server

**File:** `scripts/mock_server/server.py` (modify)

**Changes:**
1. Import `HAWebSocketHandler`, `MockStateManager`
2. Add `/api/websocket` endpoint
3. Send `auth_required` on connect
4. Route messages through handler
5. Broadcast state changes to all clients

```bash
# Start server and test WebSocket:
./env/bin/python -m scripts.mock_server &
sleep 2

# Test auth flow with wscat:
echo '{"type":"auth","access_token":"test"}' | websocat ws://localhost:8765/api/websocket

# Or with Python:
./env/bin/python -c "
import asyncio
import websockets
import json

async def test():
    async with websockets.connect('ws://localhost:8765/api/websocket') as ws:
        # Should receive auth_required
        msg = json.loads(await ws.recv())
        assert msg['type'] == 'auth_required', f'Expected auth_required, got {msg}'

        # Send auth
        await ws.send(json.dumps({'type': 'auth', 'access_token': 'test'}))

        # Should receive auth_ok
        msg = json.loads(await ws.recv())
        assert msg['type'] == 'auth_ok', f'Expected auth_ok, got {msg}'

        # Test get_states
        await ws.send(json.dumps({'id': 1, 'type': 'get_states'}))
        msg = json.loads(await ws.recv())
        assert msg['success'], f'get_states failed: {msg}'
        print(f'Got {len(msg[\"result\"])} entities')

        print('All WebSocket tests passed!')

asyncio.run(test())
"
```

**Acceptance Criteria:**
- [ ] `/api/websocket` endpoint works
- [ ] Auth flow completes successfully
- [ ] `get_states` returns all entities
- [ ] `call_service` works via WebSocket
- [ ] State changes broadcast to all clients

---

## Phase 3: Vite Proxy Configuration

**Objective:** Route WebSocket through Vite dev server in test mode.

### Step 3.1: Update Vite Config

**File:** `web-ui/vite.config.ts` (modify)

**Changes:**
1. Add proxy config for `test` mode
2. Proxy `/api/websocket` to `ws://localhost:8765`
3. Proxy `/api/*` to `http://localhost:8765`

```bash
# Verification - start in test mode:
cd web-ui && npm run dev:test &
sleep 5

# Test proxy works:
curl -s http://localhost:8080/api/ | head -3
# Should return mock server response
```

**Acceptance Criteria:**
- [ ] `npm run dev:test` starts with proxy
- [ ] REST API proxied correctly
- [ ] WebSocket proxied correctly

### Step 3.2: Add Test Mode Script

**File:** `web-ui/package.json` (modify)

**Changes:**
1. Add `"dev:test": "vite --mode test"`
2. Optionally add `"e2e:mock": "BASE_URL=http://localhost:8080 playwright test"`

```bash
# Verification:
cd web-ui && npm run dev:test &
sleep 5
curl http://localhost:8080/api/ && echo "Proxy works"
```

**Acceptance Criteria:**
- [ ] `npm run dev:test` script exists
- [ ] Vite starts in test mode with proxy enabled

---

## Phase 4: Integration Testing

**Objective:** Verify `useHomeAssistant` works with mock server.

### Step 4.1: Create Test Page for HA Hook

**File:** `web-ui/src/pages/MockHATest.tsx` (new, temporary)

Simple page that:
1. Uses `useHomeAssistant` hook
2. Displays connection status
3. Shows entity count
4. Tests service calls

```bash
# After creating, verify it compiles:
cd web-ui && npm run build
```

### Step 4.2: Update E2E Tests to Use Mock HA

**File:** `web-ui/e2e/ha-websocket.spec.ts` (new)

Tests:
1. Connect to mock via HA WebSocket API
2. Verify auth flow
3. Verify entity states received
4. Test service calls update state
5. Test state change events broadcast

```bash
# Run test:
cd web-ui && BASE_URL=http://localhost:8080 npx playwright test e2e/ha-websocket.spec.ts
```

**Acceptance Criteria:**
- [ ] Tests connect via HA WebSocket protocol
- [ ] Auth flow works
- [ ] Entity states received
- [ ] Service calls work
- [ ] Events broadcast correctly

### Step 4.3: Migrate Existing Tests

Update these tests to work with `useHomeAssistant` via mock:
- `settings-sliders.spec.ts` - Remove skip, use mock server
- `cost-constraint.spec.ts` - Already works with mock

```bash
# Run full E2E suite:
make e2e-test
```

**Acceptance Criteria:**
- [ ] All E2E tests pass against mock server
- [ ] No tests require live HA

---

## Phase 5: CI/CD Integration

**Objective:** Run E2E tests in GitHub Actions without live HA.

### Step 5.1: Create GitHub Actions Workflow

**File:** `.github/workflows/e2e.yml` (new)

Steps:
1. Checkout code
2. Setup Python 3.11
3. Setup Node 20
4. Install dependencies
5. Start mock server
6. Start Vite in test mode
7. Run Playwright tests
8. Upload artifacts on failure

```bash
# Local verification (simulates CI):
./env/bin/python -m scripts.mock_server &
cd web-ui && npm run dev:test &
sleep 10
cd web-ui && npx playwright test --reporter=list
```

**Acceptance Criteria:**
- [ ] Workflow file created
- [ ] E2E tests pass in CI environment
- [ ] No live HA required
- [ ] Artifacts uploaded on failure

### Step 5.2: Add Entity Signature Validation to CI

Add step to verify mock server entities match committed signatures:

```yaml
- name: Validate entity signatures
  run: |
    ./env/bin/python -c "
    from scripts.mock_server.entity_validator import validate_or_warn
    from scripts.mock_server.state_manager import MockStateManager
    mgr = MockStateManager()
    entities = {e['entity_id']: e for e in mgr.get_all_entity_states()}
    assert validate_or_warn(entities, strict=True), 'Entity validation failed'
    print('Entity validation passed')
    "
```

**Acceptance Criteria:**
- [ ] CI validates mock entities against signatures
- [ ] Fails on deployed entity mismatch
- [ ] Passes with development entities

---

## Execution Order

Run phases sequentially. Each phase must pass verification before proceeding.

```
Phase 1 (Entity Discovery)     ~2 hours
    ├── 1.1 Signature schema
    ├── 1.2 Discovery script
    ├── 1.3 Validator
    └── 1.4 Initial discovery
              ↓
Phase 2 (WebSocket API)        ~4 hours
    ├── 2.1 State manager
    ├── 2.2 WebSocket handler
    └── 2.3 Server integration
              ↓
Phase 3 (Vite Proxy)           ~1 hour
    ├── 3.1 Vite config
    └── 3.2 Test scripts
              ↓
Phase 4 (Integration Tests)    ~2 hours
    ├── 4.1 Test page
    ├── 4.2 HA WebSocket tests
    └── 4.3 Migrate existing tests
              ↓
Phase 5 (CI/CD)                ~1 hour
    ├── 5.1 GitHub workflow
    └── 5.2 Signature validation
```

---

## Verification Commands Summary

```bash
# Phase 1 - Entity Discovery
cat scripts/mock_server/entity_signatures.json | python -m json.tool > /dev/null
./env/bin/python -m scripts.tools.discover_entities --help
./env/bin/python -c "from scripts.mock_server.entity_validator import ValidationMode; print('OK')"

# Phase 2 - WebSocket API
./env/bin/python -c "from scripts.mock_server.state_manager import MockStateManager; print(len(MockStateManager().get_all_entity_states()))"
./env/bin/python -m scripts.mock_server &
./env/bin/python tests/test_ha_websocket.py  # Create this test

# Phase 3 - Vite Proxy
cd web-ui && npm run dev:test &
curl http://localhost:8080/api/

# Phase 4 - Integration Tests
cd web-ui && BASE_URL=http://localhost:8080 npx playwright test

# Phase 5 - CI/CD
# Push to GitHub and verify workflow runs
```

---

## Rollback Plan

If issues arise:
1. Each phase is independent - can rollback individual files
2. Keep existing `/ws` endpoint working (backward compat)
3. Keep `useMockServer.ts` as fallback
4. Entity signatures are additive (don't delete existing)

---

## Success Criteria

Implementation is complete when:
1. [ ] `entity_signatures.json` committed with 50+ entities
2. [ ] `/api/websocket` endpoint speaks HA protocol
3. [ ] `useHomeAssistant.ts` works with mock server
4. [ ] All E2E tests pass without live HA
5. [ ] GitHub Actions workflow runs successfully
6. [ ] Entity validation catches signature mismatches

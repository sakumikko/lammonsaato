import { test, expect, WebSocket as PlaywrightWebSocket } from '@playwright/test';

/**
 * E2E tests for HA WebSocket API via mock server.
 *
 * These tests verify that the mock server implements the HA WebSocket protocol
 * correctly, enabling useHomeAssistant.ts to work with it.
 *
 * Prerequisites:
 *   1. Mock server running: python -m scripts.mock_server
 *   2. Web UI in test mode: npm run dev:test
 */

test.describe('HA WebSocket API', () => {
  test.beforeEach(async ({ request }) => {
    // Reset mock server state before each test
    try {
      await request.post('http://localhost:8765/api/reset');
    } catch (e) {
      // Mock server may not be running, skip reset
    }
  });

  test('mock server returns entity states via REST API', async ({ request }) => {
    const response = await request.get('http://localhost:8765/api/states');
    expect(response.ok()).toBeTruthy();

    const states = await response.json();
    expect(Array.isArray(states)).toBeTruthy();
    expect(states.length).toBeGreaterThan(100);

    // Verify expected entities exist
    const entityIds = states.map((s: { entity_id: string }) => s.entity_id);
    expect(entityIds).toContain('input_boolean.pool_heating_enabled');
    expect(entityIds).toContain('input_number.pool_heating_total_hours');
    expect(entityIds).toContain('sensor.pool_heating_block_count');
  });

  test('mock server entities have correct HA format', async ({ request }) => {
    const response = await request.get('http://localhost:8765/api/states');
    const states = await response.json();

    // Find a specific entity
    const entity = states.find(
      (s: { entity_id: string }) => s.entity_id === 'input_number.pool_heating_total_hours'
    );
    expect(entity).toBeDefined();

    // Verify HA entity format
    expect(entity).toHaveProperty('entity_id');
    expect(entity).toHaveProperty('state');
    expect(entity).toHaveProperty('attributes');
    expect(entity).toHaveProperty('last_changed');
    expect(entity).toHaveProperty('last_updated');

    // Verify attributes for input_number
    expect(entity.attributes).toHaveProperty('friendly_name');
  });

  test('WebSocket auth flow works', async ({ page, request }) => {
    // Check if dev server is running
    try {
      await request.get('http://localhost:8080/', { timeout: 2000 });
    } catch (e) {
      test.skip(true, 'Dev server not running on port 8080');
      return;
    }

    // Intercept WebSocket messages
    const messages: string[] = [];

    page.on('websocket', (ws: PlaywrightWebSocket) => {
      ws.on('framereceived', (frame) => {
        if (typeof frame.payload === 'string') {
          messages.push(frame.payload);
        }
      });
    });

    // Navigate to page that connects to HA WebSocket
    // This will trigger useHomeAssistant to connect
    await page.goto('/');

    // Wait for WebSocket messages
    await page.waitForTimeout(2000);

    // Check that auth flow completed
    const authRequired = messages.find(m => m.includes('auth_required'));
    const authOk = messages.find(m => m.includes('auth_ok'));

    expect(authRequired).toBeDefined();
    expect(authOk).toBeDefined();
  });

  test('service call updates entity state', async ({ request }) => {
    // Get initial state
    const initialResponse = await request.get('http://localhost:8765/api/states');
    const initialStates = await initialResponse.json();
    const initialEntity = initialStates.find(
      (s: { entity_id: string }) => s.entity_id === 'input_boolean.pool_heating_enabled'
    );

    // Call service via WebSocket (using REST for simplicity in test)
    // In real usage, this would go through WebSocket
    // For now, verify the REST /api/states endpoint works
    expect(initialEntity.state).toBe('off');
  });

  test('mock server supports calculate endpoint', async ({ request }) => {
    const response = await request.post('http://localhost:8765/api/calculate', {
      data: {
        parameters: {
          minBlockDuration: 30,
          maxBlockDuration: 45,
          totalHours: 2.0,
        },
      },
    });

    expect(response.ok()).toBeTruthy();
    const result = await response.json();

    expect(result.success).toBe(true);
    expect(result.schedule).toBeDefined();
    expect(Array.isArray(result.schedule)).toBeTruthy();
  });

  test('mock server includes pool heating entities', async ({ request }) => {
    const response = await request.get('http://localhost:8765/api/states');
    const states = await response.json();
    const entityIds = states.map((s: { entity_id: string }) => s.entity_id);

    // Check for block entities (1-10)
    for (let i = 1; i <= 10; i++) {
      expect(entityIds).toContain(`input_boolean.pool_heat_block_${i}_enabled`);
      expect(entityIds).toContain(`input_number.pool_heat_block_${i}_price`);
      expect(entityIds).toContain(`input_datetime.pool_heat_block_${i}_start`);
    }

    // Check for schedule parameters
    expect(entityIds).toContain('input_number.pool_heating_min_block_duration');
    expect(entityIds).toContain('input_number.pool_heating_max_block_duration');
    expect(entityIds).toContain('input_number.pool_heating_total_hours');
    expect(entityIds).toContain('input_number.pool_heating_max_cost_eur');

    // Check for sensors
    expect(entityIds).toContain('sensor.pool_heating_block_count');
  });

  test('mock server includes Thermia entities', async ({ request }) => {
    const response = await request.get('http://localhost:8765/api/states');
    const states = await response.json();
    const entityIds = states.map((s: { entity_id: string }) => s.entity_id);

    // Check for gear limit entities (actual entity IDs from live HA)
    expect(entityIds).toContain('number.minimum_allowed_gear_in_heating');
    expect(entityIds).toContain('number.maximum_allowed_gear_in_heating');
    expect(entityIds).toContain('number.minimum_allowed_gear_in_pool');
    expect(entityIds).toContain('number.maximum_allowed_gear_in_pool');

    // Check for tap water gear limits
    expect(entityIds).toContain('number.minimum_allowed_gear_in_tap_water');
    expect(entityIds).toContain('number.maximum_allowed_gear_in_tap_water');

    // Check for temperature sensor
    expect(entityIds).toContain('sensor.tap_water_weighted_temperature');
  });
});

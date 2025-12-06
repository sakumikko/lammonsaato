import { test, expect } from '@playwright/test';

/**
 * E2E tests for the Cost Constraint feature.
 *
 * These tests verify:
 * - Cost limit input in the schedule editor
 * - Cost per block display
 * - Cost-exceeded block styling
 * - Warning banner when cost limit is applied
 * - Total cost display
 *
 * Prerequisites:
 *   - Mock server running: make mock-server
 *   - Web UI dev server: make web-dev
 */

test.describe('Cost Constraint - Local Mode', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/testbench');
    // Switch to local mode (doesn't require mock server)
    await page.getByRole('button', { name: /local/i }).click();
  });

  test('should display cost limit input in editor', async ({ page }) => {
    // Open editor
    await page.getByTestId('schedule-editor-toggle').click();
    await expect(page.getByTestId('schedule-editor-panel')).toBeVisible();

    // Verify cost limit input exists
    await expect(page.getByTestId('input-max-cost')).toBeVisible();
  });

  test('should accept free number input for cost limit', async ({ page }) => {
    // Open editor
    await page.getByTestId('schedule-editor-toggle').click();

    // Find cost input and enter a value
    const costInput = page.getByTestId('input-max-cost');
    await costInput.fill('2.50');

    // Verify value is set
    await expect(costInput).toHaveValue('2.50');
  });

  test('should clear cost limit when input is emptied', async ({ page }) => {
    // Open editor
    await page.getByTestId('schedule-editor-toggle').click();

    // Set then clear
    const costInput = page.getByTestId('input-max-cost');
    await costInput.fill('2.00');
    await costInput.clear();

    // Should show placeholder (no limit)
    await expect(costInput).toHaveValue('');
  });

  test('should show cost per block in schedule', async ({ page }) => {
    // Verify cost is displayed for each block
    const blocksContainer = page.getByTestId('schedule-blocks');
    await expect(blocksContainer).toBeVisible();

    // Look for cost display (€ symbol followed by number)
    const costElements = page.locator('[data-testid="block-cost"]');
    const count = await costElements.count();

    // Should have at least one block with cost if blocks exist
    const blockCount = await blocksContainer.getAttribute('data-block-count');
    if (parseInt(blockCount || '0') > 0) {
      expect(count).toBeGreaterThan(0);
    }
  });

  test('should show total cost in schedule summary', async ({ page }) => {
    // Look for total cost display
    await expect(page.getByTestId('total-cost')).toBeVisible();
  });
});

test.describe('Cost Constraint - Mock Server Integration', () => {
  // Run serially because tests share the same mock server
  test.describe.configure({ mode: 'serial' });

  test.beforeEach(async ({ page, request }) => {
    // Reset mock server state before each test
    try {
      await request.post('http://localhost:8765/api/reset');
    } catch {
      // Server not running, will be skipped in test
    }
    await page.goto('/testbench');
    // Wait for page to load and potentially connect to server
    await page.waitForTimeout(500);
  });

  test('should calculate correct costs with typical prices', async ({ page }) => {
    // Skip if mock server not connected
    const connected = await page.getByText(/mock server connected/i).isVisible();
    test.skip(!connected, 'Mock server not running');

    // Open editor
    await page.getByTestId('schedule-editor-toggle').click();
    await expect(page.getByTestId('schedule-editor-panel')).toBeVisible();

    // Set 2h schedule without cost limit
    await page.getByTestId('select-total-hours').click();
    await page.getByRole('option', { name: '2h', exact: true }).click();

    // Clear any existing cost limit
    const costInput = page.getByTestId('input-max-cost');
    await costInput.clear();

    // Save
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/parameters') && resp.status() === 200),
      page.waitForResponse(resp => resp.url().includes('/api/calculate') && resp.status() === 200),
      page.getByTestId('schedule-editor-save').click(),
    ]);

    await page.waitForTimeout(500);

    // Should show total cost
    const totalCost = page.getByTestId('total-cost');
    await expect(totalCost).toBeVisible();
    // Cost should be a positive number
    const costText = await totalCost.textContent();
    expect(costText).toMatch(/€[\d.]+/);
  });

  test('should disable blocks when cost limit is exceeded', async ({ page, request }) => {
    test.setTimeout(60000);
    const connected = await page.getByText(/mock server connected/i).isVisible();
    test.skip(!connected, 'Mock server not running');

    // Switch to high_prices scenario (typical_winter prices are too cheap for cost limit to trigger)
    try {
      await request.post('http://localhost:8765/api/scenario', {
        data: { scenario: 'high_prices' },
      });
    } catch {
      test.skip(true, 'Could not set scenario');
    }

    // Open editor
    await page.getByTestId('schedule-editor-toggle').click();
    await expect(page.getByTestId('schedule-editor-panel')).toBeVisible();

    // Set 3h schedule
    await page.getByTestId('select-total-hours').click();
    await page.getByRole('option', { name: '3h', exact: true }).click();

    // Set a cost limit that will disable some blocks with high prices
    // (with high prices, each 30min block costs ~€0.40-0.50)
    const costInput = page.getByTestId('input-max-cost');
    await costInput.fill('0.50');

    // Save
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/parameters') && resp.status() === 200),
      page.waitForResponse(resp => resp.url().includes('/api/calculate') && resp.status() === 200),
      page.getByTestId('schedule-editor-save').click(),
    ]);

    await page.waitForTimeout(500);

    // Should show cost limit warning
    await expect(page.getByTestId('cost-limit-warning')).toBeVisible();

    // Should have some cost-exceeded blocks
    const exceededBlocks = page.locator('[data-cost-exceeded="true"]');
    const exceededCount = await exceededBlocks.count();
    expect(exceededCount).toBeGreaterThan(0);
  });

  test('should show warning banner when cost limit applied', async ({ page, request }) => {
    test.setTimeout(60000);
    const connected = await page.getByText(/mock server connected/i).isVisible();
    test.skip(!connected, 'Mock server not running');

    // Switch to high_prices scenario (typical_winter prices are too cheap for cost limit to trigger)
    try {
      await request.post('http://localhost:8765/api/scenario', {
        data: { scenario: 'high_prices' },
      });
    } catch {
      test.skip(true, 'Could not set scenario');
    }

    // Open editor
    await page.getByTestId('schedule-editor-toggle').click();
    await expect(page.getByTestId('schedule-editor-panel')).toBeVisible();

    // Set parameters with low cost limit
    await page.getByTestId('select-total-hours').click();
    await page.getByRole('option', { name: '2h', exact: true }).click();

    const costInput = page.getByTestId('input-max-cost');
    await costInput.fill('0.50');

    // Save - this triggers recalculation with the high_prices scenario
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/parameters') && resp.status() === 200),
      page.waitForResponse(resp => resp.url().includes('/api/calculate') && resp.status() === 200),
      page.getByTestId('schedule-editor-save').click(),
    ]);

    await page.waitForTimeout(500);

    // Warning should be visible
    const warning = page.getByTestId('cost-limit-warning');
    await expect(warning).toBeVisible();

    // Warning should mention cost limit
    await expect(warning).toContainText(/cost|kustannus/i);
  });

  test('should not show warning when no cost limit', async ({ page }) => {
    const connected = await page.getByText(/mock server connected/i).isVisible();
    test.skip(!connected, 'Mock server not running');

    // Open editor
    await page.getByTestId('schedule-editor-toggle').click();

    // Set parameters without cost limit
    await page.getByTestId('select-total-hours').click();
    await page.getByRole('option', { name: '2h', exact: true }).click();

    const costInput = page.getByTestId('input-max-cost');
    await costInput.clear();

    // Save
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/parameters') && resp.status() === 200),
      page.waitForResponse(resp => resp.url().includes('/api/calculate') && resp.status() === 200),
      page.getByTestId('schedule-editor-save').click(),
    ]);

    await page.waitForTimeout(500);

    // Warning should NOT be visible
    await expect(page.getByTestId('cost-limit-warning')).not.toBeVisible();
  });

  test('should enable cheapest blocks first when cost limited', async ({ page, request }) => {
    test.setTimeout(60000);
    const connected = await page.getByText(/mock server connected/i).isVisible();
    test.skip(!connected, 'Mock server not running');

    // Switch to high_prices scenario
    try {
      await request.post('http://localhost:8765/api/scenario', {
        data: { scenario: 'high_prices' },
      });
    } catch {
      test.skip(true, 'Could not set scenario');
    }

    // Open editor and set cost limit
    await page.getByTestId('schedule-editor-toggle').click();

    await page.getByTestId('select-total-hours').click();
    await page.getByRole('option', { name: '3h', exact: true }).click();

    const costInput = page.getByTestId('input-max-cost');
    await costInput.fill('0.60');

    // Save
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/parameters') && resp.status() === 200),
      page.waitForResponse(resp => resp.url().includes('/api/calculate') && resp.status() === 200),
      page.getByTestId('schedule-editor-save').click(),
    ]);

    await page.waitForTimeout(500);

    // Get enabled and disabled blocks
    const enabledBlocks = page.locator('[data-block-enabled="true"]');
    const exceededBlocks = page.locator('[data-cost-exceeded="true"]');

    const enabledCount = await enabledBlocks.count();
    const exceededCount = await exceededBlocks.count();

    // Should have some enabled and some exceeded
    if (exceededCount > 0) {
      // Get prices of enabled and exceeded blocks
      const enabledPrices: number[] = [];
      const exceededPrices: number[] = [];

      for (let i = 0; i < enabledCount; i++) {
        const priceAttr = await enabledBlocks.nth(i).getAttribute('data-block-price');
        if (priceAttr) enabledPrices.push(parseFloat(priceAttr));
      }

      for (let i = 0; i < exceededCount; i++) {
        const priceAttr = await exceededBlocks.nth(i).getAttribute('data-block-price');
        if (priceAttr) exceededPrices.push(parseFloat(priceAttr));
      }

      // Enabled blocks should generally be cheaper than exceeded
      if (enabledPrices.length > 0 && exceededPrices.length > 0) {
        const maxEnabled = Math.max(...enabledPrices);
        const minExceeded = Math.min(...exceededPrices);
        expect(maxEnabled).toBeLessThanOrEqual(minExceeded);
      }
    }
  });

  test('should allow manual override of cost-exceeded blocks', async ({ page, request }) => {
    test.setTimeout(60000);
    const connected = await page.getByText(/mock server connected/i).isVisible();
    test.skip(!connected, 'Mock server not running');

    // Switch to high_prices scenario
    try {
      await request.post('http://localhost:8765/api/scenario', {
        data: { scenario: 'high_prices' },
      });
    } catch {
      test.skip(true, 'Could not set scenario');
    }

    // Open editor and set cost limit
    await page.getByTestId('schedule-editor-toggle').click();

    await page.getByTestId('select-total-hours').click();
    await page.getByRole('option', { name: '2h', exact: true }).click();

    const costInput = page.getByTestId('input-max-cost');
    await costInput.fill('0.40');

    // Save
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/parameters') && resp.status() === 200),
      page.waitForResponse(resp => resp.url().includes('/api/calculate') && resp.status() === 200),
      page.getByTestId('schedule-editor-save').click(),
    ]);

    await page.waitForTimeout(500);

    // Find a cost-exceeded block's switch
    const exceededBlock = page.locator('[data-cost-exceeded="true"]').first();
    const hasExceeded = await exceededBlock.isVisible().catch(() => false);

    if (hasExceeded) {
      // The switch should be functional (not disabled)
      const blockSwitch = exceededBlock.locator('button[role="switch"]');
      await expect(blockSwitch).toBeEnabled();

      // Click to enable the block manually
      await blockSwitch.click();

      // Wait for state update
      await page.waitForTimeout(500);

      // Block should now be enabled
      const switchState = await blockSwitch.getAttribute('data-state');
      expect(switchState).toBe('checked');
    }
  });

  /**
   * REGRESSION TEST: Stale closure bug with cost limit
   */
  test('regression: should send correct cost limit after changing value', async ({ page }) => {
    test.setTimeout(60000);
    const connected = await page.getByText(/mock server connected/i).isVisible();
    test.skip(!connected, 'Mock server not running');

    // Open editor
    await page.getByTestId('schedule-editor-toggle').click();

    // Set initial cost limit
    const costInput = page.getByTestId('input-max-cost');
    await costInput.fill('1.00');

    // Save first time
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/parameters') && resp.status() === 200),
      page.waitForResponse(resp => resp.url().includes('/api/calculate') && resp.status() === 200),
      page.getByTestId('schedule-editor-save').click(),
    ]);

    await page.waitForTimeout(500);
    await expect(page.getByTestId('schedule-editor-panel')).not.toBeVisible({ timeout: 5000 });

    // Reopen editor and change value
    await page.getByTestId('schedule-editor-toggle').click();
    await expect(page.getByTestId('schedule-editor-panel')).toBeVisible();

    // Change to different value
    await costInput.clear();
    await costInput.fill('0.50');

    // Save - with stale closure bug, it would send 1.00 instead of 0.50
    let sentMaxCost: number | null = null;
    await Promise.all([
      page.waitForResponse(async resp => {
        if (resp.url().includes('/api/parameters') && resp.status() === 200) {
          try {
            const req = resp.request();
            const body = req.postDataJSON();
            sentMaxCost = body.maxCostEur;
          } catch {
            // ignore
          }
          return true;
        }
        return false;
      }),
      page.waitForResponse(resp => resp.url().includes('/api/calculate') && resp.status() === 200),
      page.getByTestId('schedule-editor-save').click(),
    ]);

    // Verify the correct value was sent
    expect(sentMaxCost).toBe(0.50);
  });

  /**
   * REGRESSION TEST: Very low cost limit should disable ALL blocks
   *
   * Bug discovered 2025-12-06: When max_cost_eur is set to 0.01€ (lower than
   * any individual block cost), all blocks should be marked as cost_exceeded
   * and disabled. In practice, this wasn't happening because:
   * 1. The cost constraint wasn't being applied after recalculation
   * 2. Blocks remained enabled despite exceeding the cost limit
   */
  test('regression: very low cost limit should disable all blocks', async ({ page, request }) => {
    test.setTimeout(60000);
    const connected = await page.getByText(/mock server connected/i).isVisible();
    test.skip(!connected, 'Mock server not running');

    // Use high_prices scenario to ensure costs are high enough
    try {
      await request.post('http://localhost:8765/api/scenario', {
        data: { scenario: 'high_prices' },
      });
    } catch {
      test.skip(true, 'Could not set scenario');
    }

    // Open editor
    await page.getByTestId('schedule-editor-toggle').click();
    await expect(page.getByTestId('schedule-editor-panel')).toBeVisible();

    // Set 2h schedule
    await page.getByTestId('select-total-hours').click();
    await page.getByRole('option', { name: '2h', exact: true }).click();

    // Set VERY low cost limit - 0.01€ is lower than any single block cost
    // (A 30min block at 10c/kWh costs €0.25)
    const costInput = page.getByTestId('input-max-cost');
    await costInput.fill('0.01');

    // Save and wait for recalculation
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/parameters') && resp.status() === 200),
      page.waitForResponse(resp => resp.url().includes('/api/calculate') && resp.status() === 200),
      page.getByTestId('schedule-editor-save').click(),
    ]);

    await page.waitForTimeout(500);

    // CRITICAL: With such a low limit, ALL blocks should be cost_exceeded
    const exceededBlocks = page.locator('[data-cost-exceeded="true"]');
    const enabledBlocks = page.locator('[data-block-enabled="true"]');

    const exceededCount = await exceededBlocks.count();
    const enabledCount = await enabledBlocks.count();

    // All scheduled blocks should be marked as cost_exceeded
    // (enabled blocks should be 0 because cost is too low)
    expect(exceededCount).toBeGreaterThan(0);
    expect(enabledCount).toBe(0);

    // Should show cost limit warning
    await expect(page.getByTestId('cost-limit-warning')).toBeVisible();
  });
});

// Note: High prices scenario test was removed to avoid flakiness when running in parallel.
// The cost constraint functionality with high prices is already tested in the Mock Server
// Integration tests (should disable blocks, should show warning, should enable cheapest first)
// which all use the high_prices scenario.

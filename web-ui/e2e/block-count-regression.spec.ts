import { test, expect } from '@playwright/test';

/**
 * Regression tests for block count and cost display bugs.
 *
 * Bug discovered 2025-12-06:
 * - useHomeAssistant.ts only read blocks 1-4, ignoring blocks 5-10
 * - useHomeAssistant.ts didn't read cost entities (costEur, costExceeded)
 * - useHomeAssistant.ts didn't save maxCostEur parameter
 *
 * Result: UI showed 2h (4 blocks) when HA had 2.5h (5 blocks) scheduled,
 * and all costs showed €0.00
 */

test.describe('Block Count and Cost Display - Regression Tests', () => {
  test.beforeEach(async ({ page, request }) => {
    // Reset mock server state
    try {
      await request.post('http://localhost:8765/api/reset');
    } catch {
      // Server not running
    }
    await page.goto('/testbench');
    await page.waitForTimeout(500);
  });

  test('should display more than 4 blocks when scheduled', async ({ page, request }) => {
    const connected = await page.getByText(/mock server connected/i).isVisible();
    test.skip(!connected, 'Mock server not running');

    // Open editor and set 3h heating (should create 6 blocks of 30min)
    await page.getByTestId('schedule-editor-toggle').click();
    await expect(page.getByTestId('schedule-editor-panel')).toBeVisible();

    // Set 3h total
    await page.getByTestId('select-total-hours').click();
    await page.getByRole('option', { name: '3h', exact: true }).click();

    // Set min/max to 30m for predictable block count
    await page.getByTestId('select-min-block').click();
    await page.getByRole('option', { name: '30m' }).click();
    await page.getByTestId('select-max-block').click();
    await page.getByRole('option', { name: '30m' }).click();

    // Save and recalculate
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/calculate') && resp.status() === 200),
      page.getByTestId('schedule-editor-save').click(),
    ]);

    await page.waitForTimeout(500);

    // CRITICAL: Should have 6 blocks (3h ÷ 30min = 6 blocks)
    // Bug: only showed 4 blocks because loop was `for (n = 1; n <= 4)`
    const blocksContainer = page.getByTestId('schedule-blocks');
    const blockCount = await blocksContainer.getAttribute('data-block-count');

    expect(parseInt(blockCount || '0')).toBeGreaterThanOrEqual(5);
  });

  test('should display non-zero costs for blocks', async ({ page, request }) => {
    const connected = await page.getByText(/mock server connected/i).isVisible();
    test.skip(!connected, 'Mock server not running');

    // Open editor
    await page.getByTestId('schedule-editor-toggle').click();
    await expect(page.getByTestId('schedule-editor-panel')).toBeVisible();

    // Set 2h schedule
    await page.getByTestId('select-total-hours').click();
    await page.getByRole('option', { name: '2h', exact: true }).click();

    // Save and recalculate
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/calculate') && resp.status() === 200),
      page.getByTestId('schedule-editor-save').click(),
    ]);

    await page.waitForTimeout(500);

    // CRITICAL: Block costs should NOT be €0.00
    // Bug: costs showed €0.00 because useHomeAssistant didn't read cost entities
    const costElements = page.locator('[data-testid="block-cost"]');
    const count = await costElements.count();

    expect(count).toBeGreaterThan(0);

    // Check that at least one cost is non-zero
    let hasNonZeroCost = false;
    for (let i = 0; i < count; i++) {
      const text = await costElements.nth(i).textContent();
      if (text && !text.includes('€0.00')) {
        hasNonZeroCost = true;
        break;
      }
    }

    expect(hasNonZeroCost).toBe(true);
  });

  test('should display total cost in summary', async ({ page, request }) => {
    const connected = await page.getByText(/mock server connected/i).isVisible();
    test.skip(!connected, 'Mock server not running');

    // Open editor
    await page.getByTestId('schedule-editor-toggle').click();

    // Set 2h schedule
    await page.getByTestId('select-total-hours').click();
    await page.getByRole('option', { name: '2h', exact: true }).click();

    // Save and recalculate
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/calculate') && resp.status() === 200),
      page.getByTestId('schedule-editor-save').click(),
    ]);

    await page.waitForTimeout(500);

    // CRITICAL: Total cost should be displayed and non-zero
    const totalCost = page.getByTestId('total-cost');
    await expect(totalCost).toBeVisible();

    const costText = await totalCost.textContent();
    expect(costText).not.toBe('€0.00');
    expect(costText).toMatch(/€[\d.]+/);
  });

  test('should save maxCostEur parameter to server', async ({ page, request }) => {
    const connected = await page.getByText(/mock server connected/i).isVisible();
    test.skip(!connected, 'Mock server not running');

    // Open editor
    await page.getByTestId('schedule-editor-toggle').click();
    await expect(page.getByTestId('schedule-editor-panel')).toBeVisible();

    // Set max cost
    const costInput = page.getByTestId('input-max-cost');
    await costInput.fill('1.50');

    // Save - capture the request to verify maxCostEur is sent
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

    // CRITICAL: maxCostEur should be sent to server
    // Bug: useHomeAssistant.setScheduleParameters didn't include maxCostEur
    expect(sentMaxCost).toBe(1.50);
  });

  test('should display correct total minutes for 5+ blocks', async ({ page, request }) => {
    const connected = await page.getByText(/mock server connected/i).isVisible();
    test.skip(!connected, 'Mock server not running');

    // Open editor and set 2.5h heating
    await page.getByTestId('schedule-editor-toggle').click();
    await expect(page.getByTestId('schedule-editor-panel')).toBeVisible();

    // Set 2.5h total (should create 5 blocks of 30min)
    await page.getByTestId('select-total-hours').click();
    await page.getByRole('option', { name: '2.5h' }).click();

    // Set min/max to 30m
    await page.getByTestId('select-min-block').click();
    await page.getByRole('option', { name: '30m' }).click();
    await page.getByTestId('select-max-block').click();
    await page.getByRole('option', { name: '30m' }).click();

    // Save and recalculate
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/calculate') && resp.status() === 200),
      page.getByTestId('schedule-editor-save').click(),
    ]);

    await page.waitForTimeout(500);

    // CRITICAL: Total should show 150 minutes (2.5h × 60)
    // Bug: showed 120 minutes because only 4 blocks were read
    const totalMinutes = page.getByTestId('total-minutes');
    const minutesText = await totalMinutes.textContent();

    // Should be 150 min (5 × 30min blocks)
    expect(minutesText).toContain('150');
  });
});

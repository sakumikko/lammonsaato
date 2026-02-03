import { test, expect } from '@playwright/test';

/**
 * E2E tests for Cold Weather Mode.
 *
 * Tests the cold weather mode toggle, hour checkbox grid, and block generation.
 *
 * TDD: These tests should be written BEFORE implementation and should FAIL
 * until the cold weather feature is implemented.
 *
 * Prerequisites:
 *   - Mock server running: make mock-server
 *   - Web UI dev server: make web-dev
 */

test.describe('Cold Weather Mode - Local Mode', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/testbench');
    // Switch to local mode (doesn't require mock server)
    await page.getByRole('button', { name: /local/i }).click();
  });

  test('should display cold weather toggle in editor', async ({ page }) => {
    // Open editor
    await page.getByTestId('schedule-editor-toggle').click();
    await expect(page.getByTestId('schedule-editor-panel')).toBeVisible();

    // Cold weather toggle should exist
    await expect(page.getByTestId('cold-weather-toggle')).toBeVisible();
  });

  test('toggle ON should show cold weather controls', async ({ page }) => {
    // Open editor
    await page.getByTestId('schedule-editor-toggle').click();
    await expect(page.getByTestId('schedule-editor-panel')).toBeVisible();

    // Enable cold weather mode
    await page.getByTestId('cold-weather-toggle').click();

    // Should show cold weather specific controls
    await expect(page.getByTestId('cold-hour-grid')).toBeVisible();
    await expect(page.getByTestId('select-cold-duration')).toBeVisible();

    // Should hide normal mode controls
    await expect(page.getByTestId('select-min-block')).not.toBeVisible();
    await expect(page.getByTestId('select-max-block')).not.toBeVisible();
    await expect(page.getByTestId('select-total-hours')).not.toBeVisible();
  });

  test('toggle OFF should restore normal controls', async ({ page }) => {
    // Open editor
    await page.getByTestId('schedule-editor-toggle').click();
    await expect(page.getByTestId('schedule-editor-panel')).toBeVisible();

    // Enable then disable cold weather mode
    await page.getByTestId('cold-weather-toggle').click();
    await page.getByTestId('cold-weather-toggle').click();

    // Normal controls should be visible again
    await expect(page.getByTestId('select-min-block')).toBeVisible();
    await expect(page.getByTestId('select-max-block')).toBeVisible();
    await expect(page.getByTestId('select-total-hours')).toBeVisible();

    // Cold weather controls should be hidden
    await expect(page.getByTestId('cold-hour-grid')).not.toBeVisible();
  });

  test('hour grid should have 24 hour buttons', async ({ page }) => {
    // Open editor and enable cold weather mode
    await page.getByTestId('schedule-editor-toggle').click();
    await page.getByTestId('cold-weather-toggle').click();

    // Hour grid should have 24 buttons (0-23)
    const hourGrid = page.getByTestId('cold-hour-grid');
    const hourButtons = hourGrid.locator('button');
    const count = await hourButtons.count();

    expect(count).toBe(24);
  });

  test('hour buttons should toggle on click', async ({ page }) => {
    // Open editor and enable cold weather mode
    await page.getByTestId('schedule-editor-toggle').click();
    await page.getByTestId('cold-weather-toggle').click();

    // Find hour 12 button
    const hour12 = page.getByTestId('cold-hour-12');

    // Check initial state
    const initialSelected = await hour12.getAttribute('data-selected');

    // Click to toggle
    await hour12.click();

    // State should have changed
    const newSelected = await hour12.getAttribute('data-selected');
    expect(newSelected).not.toBe(initialSelected);
  });

  test('cold weather duration should offer 5, 10, 15 minute options', async ({ page }) => {
    // Open editor and enable cold weather mode
    await page.getByTestId('schedule-editor-toggle').click();
    await page.getByTestId('cold-weather-toggle').click();

    // Open duration dropdown
    await page.getByTestId('select-cold-duration').click();

    // Should have 5, 10, 15 options
    await expect(page.getByRole('option', { name: '5 min' })).toBeVisible();
    await expect(page.getByRole('option', { name: '10 min' })).toBeVisible();
    await expect(page.getByRole('option', { name: '15 min' })).toBeVisible();

    // Should NOT have normal duration options
    await expect(page.getByRole('option', { name: '30 min' })).not.toBeVisible();
    await expect(page.getByRole('option', { name: '45 min' })).not.toBeVisible();
  });
});

test.describe('Cold Weather Mode - Mock Server Integration', () => {
  test.describe.configure({ mode: 'serial' });

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

  test('save should produce blocks for selected hours', async ({ page }) => {
    const connected = await page.getByText(/mock server connected/i).isVisible();
    test.skip(!connected, 'Mock server not running');

    // Open editor and enable cold weather mode
    await page.getByTestId('schedule-editor-toggle').click();
    await expect(page.getByTestId('schedule-editor-panel')).toBeVisible();
    await page.getByTestId('cold-weather-toggle').click();

    // Select 5 specific hours: 21, 22, 23, 0, 1
    const hoursToSelect = [21, 22, 23, 0, 1];

    // First, deselect all hours
    const hourGrid = page.getByTestId('cold-hour-grid');
    const selectedHours = hourGrid.locator('button[data-selected="true"]');
    const selectedCount = await selectedHours.count();
    for (let i = 0; i < selectedCount; i++) {
      await selectedHours.first().click();
      await page.waitForTimeout(50);
    }

    // Then select our target hours
    for (const hour of hoursToSelect) {
      await page.getByTestId(`cold-hour-${hour}`).click();
    }

    // Save
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/calculate') && resp.status() === 200),
      page.getByTestId('schedule-editor-save').click(),
    ]);

    await page.waitForTimeout(500);

    // Should have 5 blocks
    const blocksContainer = page.getByTestId('schedule-blocks');
    const blockCount = await blocksContainer.getAttribute('data-block-count');
    expect(parseInt(blockCount || '0')).toBe(5);
  });

  test('blocks should show 5 minute duration', async ({ page }) => {
    const connected = await page.getByText(/mock server connected/i).isVisible();
    test.skip(!connected, 'Mock server not running');

    // Open editor and enable cold weather mode
    await page.getByTestId('schedule-editor-toggle').click();
    await page.getByTestId('cold-weather-toggle').click();

    // Set duration to 5 min (should be default)
    await page.getByTestId('select-cold-duration').click();
    await page.getByRole('option', { name: '5 min' }).click();

    // Save
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/calculate') && resp.status() === 200),
      page.getByTestId('schedule-editor-save').click(),
    ]);

    await page.waitForTimeout(500);

    // Blocks should show 5min duration
    const durationText = page.locator('[data-testid^="block-duration"]').first();
    await expect(durationText).toContainText('5');
  });

  test('blocks should start at :05 past each hour', async ({ page }) => {
    const connected = await page.getByText(/mock server connected/i).isVisible();
    test.skip(!connected, 'Mock server not running');

    // Open editor and enable cold weather mode
    await page.getByTestId('schedule-editor-toggle').click();
    await page.getByTestId('cold-weather-toggle').click();

    // Save with default hours
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/calculate') && resp.status() === 200),
      page.getByTestId('schedule-editor-save').click(),
    ]);

    await page.waitForTimeout(500);

    // Check block start times - all should be :05
    const blockTimes = page.locator('[data-testid^="block-time"]');
    const count = await blockTimes.count();

    for (let i = 0; i < count; i++) {
      const timeText = await blockTimes.nth(i).textContent();
      // Should contain :05 (e.g., "21:05" or "21:05-21:10")
      expect(timeText).toMatch(/:05/);
    }
  });

  test('cold weather panel should show visual distinction', async ({ page }) => {
    const connected = await page.getByText(/mock server connected/i).isVisible();
    test.skip(!connected, 'Mock server not running');

    // Open editor and enable cold weather mode
    await page.getByTestId('schedule-editor-toggle').click();
    await page.getByTestId('cold-weather-toggle').click();

    // Save
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/calculate') && resp.status() === 200),
      page.getByTestId('schedule-editor-save').click(),
    ]);

    await page.waitForTimeout(500);

    // Panel should have cold weather indicator
    const schedulePanel = page.getByTestId('schedule-panel');
    await expect(schedulePanel).toHaveAttribute('data-cold-weather', 'true');
  });

  test('should send cold weather parameters to server', async ({ page }) => {
    const connected = await page.getByText(/mock server connected/i).isVisible();
    test.skip(!connected, 'Mock server not running');

    // Open editor and enable cold weather mode
    await page.getByTestId('schedule-editor-toggle').click();
    await page.getByTestId('cold-weather-toggle').click();

    // Set specific values
    await page.getByTestId('select-cold-duration').click();
    await page.getByRole('option', { name: '10 min' }).click();

    // Capture request parameters
    let sentParams: Record<string, unknown> | null = null;
    await Promise.all([
      page.waitForResponse(async resp => {
        if (resp.url().includes('/api/parameters') && resp.status() === 200) {
          try {
            const req = resp.request();
            sentParams = req.postDataJSON();
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

    // Verify cold weather parameters were sent
    expect(sentParams).not.toBeNull();
    expect(sentParams?.coldWeatherMode).toBe(true);
    expect(sentParams?.coldBlockDuration).toBe(10);
    expect(sentParams?.coldEnabledHours).toBeDefined();
  });

  test('should use compact layout for many blocks', async ({ page }) => {
    const connected = await page.getByText(/mock server connected/i).isVisible();
    test.skip(!connected, 'Mock server not running');

    // Open editor and enable cold weather mode
    await page.getByTestId('schedule-editor-toggle').click();
    await page.getByTestId('cold-weather-toggle').click();

    // Select 10 hours to get many blocks
    const hoursToSelect = [18, 19, 20, 21, 22, 23, 0, 1, 2, 3];
    const hourGrid = page.getByTestId('cold-hour-grid');

    // Deselect all first
    const selectedHours = hourGrid.locator('button[data-selected="true"]');
    const selectedCount = await selectedHours.count();
    for (let i = 0; i < selectedCount; i++) {
      await selectedHours.first().click();
      await page.waitForTimeout(50);
    }

    // Select target hours
    for (const hour of hoursToSelect) {
      await page.getByTestId(`cold-hour-${hour}`).click();
    }

    // Save
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/calculate') && resp.status() === 200),
      page.getByTestId('schedule-editor-save').click(),
    ]);

    await page.waitForTimeout(500);

    // Should have 10 blocks in compact layout
    const blocksContainer = page.getByTestId('schedule-blocks');
    const blockCount = await blocksContainer.getAttribute('data-block-count');
    expect(parseInt(blockCount || '0')).toBe(10);

    // Should use compact layout (grid)
    await expect(blocksContainer).toHaveAttribute('data-layout', 'compact');
  });

  test('normal mode should still work after cold weather', async ({ page }) => {
    const connected = await page.getByText(/mock server connected/i).isVisible();
    test.skip(!connected, 'Mock server not running');

    // Open editor, enable cold weather, then disable it
    await page.getByTestId('schedule-editor-toggle').click();
    await page.getByTestId('cold-weather-toggle').click();
    await page.getByTestId('cold-weather-toggle').click();

    // Set normal mode parameters
    await page.getByTestId('select-total-hours').click();
    await page.getByRole('option', { name: '2h', exact: true }).click();

    // Save
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/calculate') && resp.status() === 200),
      page.getByTestId('schedule-editor-save').click(),
    ]);

    await page.waitForTimeout(500);

    // Should have normal blocks (not cold weather)
    const schedulePanel = page.getByTestId('schedule-panel');
    const coldWeatherAttr = await schedulePanel.getAttribute('data-cold-weather');
    expect(coldWeatherAttr).not.toBe('true');
  });
});

test.describe('Cold Weather Mode - Pre/Post Circulation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/testbench');
    await page.getByRole('button', { name: /local/i }).click();
  });

  test('should display pre-circulation input when cold mode enabled', async ({ page }) => {
    await page.getByTestId('schedule-editor-toggle').click();
    await page.getByTestId('cold-weather-toggle').click();

    await expect(page.getByTestId('input-cold-pre-circulation')).toBeVisible();
  });

  test('should display post-circulation input when cold mode enabled', async ({ page }) => {
    await page.getByTestId('schedule-editor-toggle').click();
    await page.getByTestId('cold-weather-toggle').click();

    await expect(page.getByTestId('input-cold-post-circulation')).toBeVisible();
  });

  test('pre-circulation default should be 5 minutes', async ({ page }) => {
    await page.getByTestId('schedule-editor-toggle').click();
    await page.getByTestId('cold-weather-toggle').click();

    const preCircInput = page.getByTestId('input-cold-pre-circulation');
    const value = await preCircInput.inputValue();
    expect(value).toBe('5');
  });

  test('post-circulation default should be 5 minutes', async ({ page }) => {
    await page.getByTestId('schedule-editor-toggle').click();
    await page.getByTestId('cold-weather-toggle').click();

    const postCircInput = page.getByTestId('input-cold-post-circulation');
    const value = await postCircInput.inputValue();
    expect(value).toBe('5');
  });
});

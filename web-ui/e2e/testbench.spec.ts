import { test, expect } from '@playwright/test';

/**
 * E2E tests for the Test Bench page.
 *
 * These tests verify the schedule editor UI works correctly with the real
 * Python optimization algorithm via the mock server.
 *
 * Prerequisites:
 *   - Mock server running: make mock-server
 *   - Web UI dev server: make web-dev
 */

test.describe('Test Bench - Local Mode', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/testbench');
    // Switch to local mode (doesn't require mock server)
    await page.getByRole('button', { name: /local/i }).click();
  });

  test('should display schedule panel', async ({ page }) => {
    const panel = page.getByTestId('schedule-panel');
    await expect(panel).toBeVisible();
  });

  test('should show default schedule blocks', async ({ page }) => {
    const blocksContainer = page.getByTestId('schedule-blocks');
    const blockCount = await blocksContainer.getAttribute('data-block-count');
    expect(parseInt(blockCount || '0')).toBeGreaterThanOrEqual(3);
  });

  test('should update schedule with presets', async ({ page }) => {
    // Click "Disabled (0h)" preset
    await page.getByRole('button', { name: /disabled.*0h/i }).click();

    // Wait for schedule to update
    await page.waitForTimeout(1000);

    // Should show 0 scheduled minutes
    const totalMinutes = page.getByTestId('total-minutes');
    await expect(totalMinutes).toContainText('0');
  });

  test('should toggle block enabled state', async ({ page }) => {
    // Find first switch
    const firstSwitch = page.locator('button[role="switch"]').first();

    // Get initial state
    const initialChecked = await firstSwitch.getAttribute('data-state');

    // Click to toggle
    await firstSwitch.click();
    await page.waitForTimeout(500);

    // State should change
    const newChecked = await firstSwitch.getAttribute('data-state');
    expect(newChecked).not.toBe(initialChecked);
  });

  test('should simulate day/night time', async ({ page }) => {
    // Initially in daytime
    await expect(page.getByText(/heating window is not active/i)).toBeVisible();

    // Click Night button
    await page.getByRole('button', { name: /night/i }).click();

    // Should now be in heating window
    await expect(page.getByText(/heating window is active/i)).toBeVisible();
  });
});

test.describe('Test Bench - Server Mode', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/testbench');
    // Should start in server mode by default
  });

  test('should show server connection status', async ({ page }) => {
    // Should show either connected or not running message
    const connected = await page.getByText(/mock server connected/i).isVisible();
    const notRunning = await page.getByText(/mock server not running/i).isVisible();

    expect(connected || notRunning).toBeTruthy();
  });

  test('should switch between server and local modes', async ({ page }) => {
    // Click local
    await page.getByRole('button', { name: /local/i }).click();
    await expect(page.getByText(/local mock data/i)).toBeVisible();

    // Switch back to server
    await page.getByRole('button', { name: /server/i }).click();
    await expect(page.getByText(/real algorithm via mock server/i)).toBeVisible();
  });
});

test.describe('Test Bench - Schedule Editor', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/testbench');
    await page.getByRole('button', { name: /local/i }).click();
  });

  test('should open schedule editor', async ({ page }) => {
    // Click settings button
    await page.getByTestId('schedule-editor-toggle').click();

    // Should show editor panel
    await expect(page.getByTestId('schedule-editor-panel')).toBeVisible();
    await expect(page.getByTestId('select-min-block')).toBeVisible();
    await expect(page.getByTestId('select-max-block')).toBeVisible();
    await expect(page.getByTestId('select-total-hours')).toBeVisible();
  });

  test('should close editor with toggle button', async ({ page }) => {
    // Open editor
    await page.getByTestId('schedule-editor-toggle').click();
    await expect(page.getByTestId('schedule-editor-panel')).toBeVisible();

    // Click toggle again to close
    await page.getByTestId('schedule-editor-toggle').click();

    // Editor should be closed
    await expect(page.getByTestId('schedule-editor-panel')).not.toBeVisible();
  });

  test('should change total hours', async ({ page }) => {
    // Open editor
    await page.getByTestId('schedule-editor-toggle').click();

    // Click total hours selector
    await page.getByTestId('select-total-hours').click();

    // Select 3h option
    await page.getByRole('option', { name: '3h', exact: true }).click();

    // Verify selection changed
    await expect(page.getByTestId('select-total-hours')).toContainText('3h');
  });
});

test.describe('Test Bench - Schedule Calculation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/testbench');
    await page.getByRole('button', { name: /local/i }).click();
  });

  test('should update total minutes when changing total hours via editor', async ({ page }) => {
    // Open editor
    await page.getByTestId('schedule-editor-toggle').click();

    // Change total hours to 3h
    await page.getByTestId('select-total-hours').click();
    await page.getByRole('option', { name: '3h', exact: true }).click();

    // Click save
    await page.getByTestId('schedule-editor-save').click();

    // Wait for update
    await page.waitForTimeout(1500);

    // Verify total minutes changed to 180 (3h)
    await expect(page.getByTestId('total-minutes')).toContainText('180');
  });

  test('should show correct block count for 1h total', async ({ page }) => {
    // Click "Short (30/30, 1h)" preset
    await page.getByRole('button', { name: /short.*30.*1h/i }).click();
    await page.waitForTimeout(1000);

    // 1h = 60min
    await expect(page.getByTestId('total-minutes')).toContainText('60');
  });

  test('should show no blocks when disabled (0h)', async ({ page }) => {
    // Click "Disabled (0h)" preset
    await page.getByRole('button', { name: /disabled.*0h/i }).click();
    await page.waitForTimeout(1000);

    // Should show 0 scheduled minutes
    await expect(page.getByTestId('total-minutes')).toContainText('0');

    // Block count should be 0
    const blocksContainer = page.getByTestId('schedule-blocks');
    await expect(blocksContainer).toHaveAttribute('data-block-count', '0');
  });

  test('should calculate 5h as 300 minutes', async ({ page }) => {
    // Click "Maximum (60/60, 5h)" preset - 5h is max due to heating window constraint
    await page.getByRole('button', { name: /maximum.*5h/i }).click();
    await page.waitForTimeout(1000);

    // 5h = 300min
    await expect(page.getByTestId('total-minutes')).toContainText('300');
  });
});

test.describe('Test Bench - Warning Modal', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/testbench');
    await page.getByRole('button', { name: /local/i }).click();
    // Set to night mode
    await page.getByRole('button', { name: /night/i }).click();
  });

  test('should show warning when editing during heating window', async ({ page }) => {
    // Open editor
    await page.getByTestId('schedule-editor-toggle').click();

    // Click save
    await page.getByTestId('schedule-editor-save').click();

    // Should show warning dialog
    await expect(page.getByRole('alertdialog')).toBeVisible();
  });

  test('should cancel warning dialog', async ({ page }) => {
    // Open editor and trigger warning
    await page.getByTestId('schedule-editor-toggle').click();
    await page.getByTestId('schedule-editor-save').click();

    // Cancel
    await page.getByRole('button', { name: /peruuta|cancel/i }).click();

    // Dialog should close
    await expect(page.getByRole('alertdialog')).not.toBeVisible();

    // Editor should still be open
    await expect(page.getByTestId('schedule-editor-panel')).toBeVisible();
  });
});

test.describe('Test Bench - Mock Server Integration', () => {
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

  test('should calculate 5h schedule with mock server', async ({ page }) => {
    // Skip if mock server not connected
    const connected = await page.getByText(/mock server connected/i).isVisible();
    test.skip(!connected, 'Mock server not running');

    // Open editor
    await page.getByTestId('schedule-editor-toggle').click();
    await expect(page.getByTestId('schedule-editor-panel')).toBeVisible();

    // Set to 5h
    await page.getByTestId('select-total-hours').click();
    await page.getByRole('option', { name: '5h', exact: true }).click();

    // Clear any cost limit that might be set from parallel tests
    const costInput = page.getByTestId('input-max-cost');
    await costInput.clear();

    // Save and wait for API calls to complete
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/parameters') && resp.status() === 200),
      page.waitForResponse(resp => resp.url().includes('/api/calculate') && resp.status() === 200),
      page.getByTestId('schedule-editor-save').click(),
    ]);

    // Wait for state to propagate
    await page.waitForTimeout(500);

    // Should show 300 minutes (5h = 300min)
    await expect(page.getByTestId('total-minutes')).toContainText('300', { timeout: 10000 });

    // Should have multiple blocks (5h with 30-45min blocks = ~7-9 blocks)
    const blocksContainer = page.getByTestId('schedule-blocks');
    const blockCount = await blocksContainer.getAttribute('data-block-count');
    expect(parseInt(blockCount || '0')).toBeGreaterThanOrEqual(7);
  });

  /**
   * REGRESSION TEST: Stale closure bug
   *
   * This test catches the bug where changing a parameter value in the editor
   * would send the OLD value instead of the NEW value due to stale closures
   * in useCallback dependencies.
   *
   * The bug: handleSave captured an old doSaveAndRecalculate that had stale editParams
   *
   * Reproduction steps:
   * 1. Start with default 2h
   * 2. Change to 3.5h in editor
   * 3. Click save
   * 4. BUG: Server receives 2h instead of 3.5h
   */
  test('should send correct parameters after changing value (stale closure regression)', async ({ page }) => {
    // Skip if mock server not connected
    const connected = await page.getByText(/mock server connected/i).isVisible();
    test.skip(!connected, 'Mock server not running');

    // Verify we start with default 2h (120 min)
    await expect(page.getByTestId('total-minutes')).toContainText('120');

    // Open editor
    await page.getByTestId('schedule-editor-toggle').click();

    // Verify editor shows current value (2h)
    await expect(page.getByTestId('select-total-hours')).toContainText('2h');

    // Change to 3.5h - this is the critical step that exposed the bug
    await page.getByTestId('select-total-hours').click();
    await page.getByRole('option', { name: '3.5h' }).click();

    // Verify selector shows new value
    await expect(page.getByTestId('select-total-hours')).toContainText('3.5h');

    // Save - with the bug, this would send 2h instead of 3.5h
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/parameters') && resp.status() === 200),
      page.waitForResponse(resp => resp.url().includes('/api/calculate') && resp.status() === 200),
      page.getByTestId('schedule-editor-save').click(),
    ]);

    // Wait for state to propagate
    await page.waitForTimeout(500);

    // CRITICAL ASSERTION: Should show 210 minutes (3.5h = 210min)
    // With the stale closure bug, this would show 120 min (2h)
    await expect(page.getByTestId('total-minutes')).toContainText('210', { timeout: 10000 });
  });

  /**
   * Test multiple consecutive parameter changes
   * Ensures each change is correctly captured and sent
   */
  test('should handle multiple consecutive parameter changes', async ({ page }) => {
    test.setTimeout(90000); // Longer timeout for multiple API calls
    const connected = await page.getByText(/mock server connected/i).isVisible();
    test.skip(!connected, 'Mock server not running');

    // Helper to save and wait for API
    const saveAndWait = async () => {
      await Promise.all([
        page.waitForResponse(resp => resp.url().includes('/api/parameters') && resp.status() === 200),
        page.waitForResponse(resp => resp.url().includes('/api/calculate') && resp.status() === 200),
        page.getByTestId('schedule-editor-save').click(),
      ]);
      await page.waitForTimeout(1000); // Longer wait for state to propagate
    };

    // Helper to open editor (handles case where it's already open)
    const openEditor = async () => {
      const editorPanel = page.getByTestId('schedule-editor-panel');
      const isVisible = await editorPanel.isVisible();
      if (!isVisible) {
        await page.getByTestId('schedule-editor-toggle').click();
        await expect(editorPanel).toBeVisible({ timeout: 5000 });
      }
    };

    // Helper to ensure editor is closed
    const closeEditorIfOpen = async () => {
      const editorPanel = page.getByTestId('schedule-editor-panel');
      const isVisible = await editorPanel.isVisible();
      if (isVisible) {
        await page.getByTestId('schedule-editor-toggle').click();
        await expect(editorPanel).not.toBeVisible({ timeout: 5000 });
      }
    };

    // First change: 2h -> 4h
    await openEditor();
    await page.getByTestId('select-total-hours').click();
    await page.getByRole('option', { name: '4h', exact: true }).click();
    await saveAndWait();
    await expect(page.getByTestId('total-minutes')).toContainText('240', { timeout: 15000 });

    // Close editor before next change
    await closeEditorIfOpen();

    // Second change: 4h -> 1h
    await openEditor();
    await page.getByTestId('select-total-hours').click();
    await page.getByRole('option', { name: '1h', exact: true }).click();
    await saveAndWait();
    await expect(page.getByTestId('total-minutes')).toContainText('60', { timeout: 15000 });

    // Close editor before next change
    await closeEditorIfOpen();

    // Third change: 1h -> 3h
    await openEditor();
    await page.getByTestId('select-total-hours').click();
    await page.getByRole('option', { name: '3h', exact: true }).click();
    await saveAndWait();
    await expect(page.getByTestId('total-minutes')).toContainText('180', { timeout: 15000 });
  });

});

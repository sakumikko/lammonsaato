import { test, expect } from '@playwright/test';

/**
 * E2E tests for simplified topbar.
 *
 * Tests verify:
 * - StatusIndicator shows connection/system status
 * - SettingsDropdown contains theme, language, heat pump settings
 * - Heat pump settings sheet opens from dropdown
 *
 * Prerequisites:
 *   1. Mock server running: python -m scripts.mock_server
 *   2. Web UI in test mode: npm run dev:test
 */

test.describe('Simplified Topbar', () => {
  test.beforeEach(async ({ page, request }) => {
    // Check if dev server is running (port 8081 for test mode)
    try {
      await request.get('http://localhost:8081/', { timeout: 2000 });
    } catch (e) {
      test.skip(true, 'Dev server not running on port 8081');
      return;
    }

    // Reset mock server state
    try {
      await request.post('http://localhost:8765/api/reset');
    } catch (e) {
      // Mock server may not be running, skip reset
    }

    await page.goto('/');
    // Wait for WebSocket connection
    await page.waitForTimeout(1500);
  });

  test('status indicator is visible and shows status', async ({ page }) => {
    const statusIndicator = page.getByTestId('status-indicator');
    await expect(statusIndicator).toBeVisible();

    // Should have a status attribute
    const status = await statusIndicator.getAttribute('data-status');
    expect(['disconnected', 'idle', 'active']).toContain(status);
  });

  test('status indicator shows tooltip on hover', async ({ page }) => {
    const statusIndicator = page.getByTestId('status-indicator');
    await statusIndicator.hover();

    // Tooltip should appear
    await expect(page.getByRole('tooltip')).toBeVisible();
  });

  test('settings dropdown exists and can be opened', async ({ page }) => {
    const settingsButton = page.getByTestId('settings-dropdown');
    await expect(settingsButton).toBeVisible();

    // Click to open dropdown
    await settingsButton.click();

    // Dropdown menu should appear with options
    const dropdown = page.locator('[role="menu"]');
    await expect(dropdown).toBeVisible();
  });

  test('settings dropdown contains theme toggle', async ({ page }) => {
    const settingsButton = page.getByTestId('settings-dropdown');
    await settingsButton.click();

    // Find theme toggle item (contains Sun or Moon icon)
    const themeItem = page.locator('[role="menuitem"]').filter({
      has: page.locator('svg'),
    }).first();
    await expect(themeItem).toBeVisible();
  });

  test('settings dropdown contains language toggle', async ({ page }) => {
    const settingsButton = page.getByTestId('settings-dropdown');
    await settingsButton.click();

    // Find language item (contains FI or EN)
    const languageItem = page.locator('[role="menuitem"]').filter({
      hasText: /FI|EN/,
    });
    await expect(languageItem).toBeVisible();
  });

  test('settings dropdown contains heat pump settings', async ({ page }) => {
    const settingsButton = page.getByTestId('settings-dropdown');
    await settingsButton.click();

    // Find heat pump settings item
    const heatPumpItem = page.locator('[role="menuitem"]').filter({
      has: page.locator('svg.lucide-wrench'),
    });
    await expect(heatPumpItem).toBeVisible();
  });

  test('heat pump settings sheet opens from dropdown', async ({ page }) => {
    const settingsButton = page.getByTestId('settings-dropdown');
    await settingsButton.click();

    // Click heat pump settings
    const heatPumpItem = page.locator('[role="menuitem"]').filter({
      has: page.locator('svg.lucide-wrench'),
    });
    await heatPumpItem.click();

    // Sheet should open (wait for animation)
    await page.waitForTimeout(300);

    // Sheet content should be visible
    const sheet = page.locator('[role="dialog"]');
    await expect(sheet).toBeVisible();
  });

  test('theme can be toggled from dropdown', async ({ page }) => {
    // Get initial theme
    const html = page.locator('html');
    const initialClass = await html.getAttribute('class');
    const isDarkInitially = initialClass?.includes('dark');

    // Open settings and toggle theme
    const settingsButton = page.getByTestId('settings-dropdown');
    await settingsButton.click();

    // Click first menu item (theme toggle)
    const themeItem = page.locator('[role="menuitem"]').first();
    await themeItem.click();

    // Wait for theme change
    await page.waitForTimeout(100);

    // Theme should have changed
    const newClass = await html.getAttribute('class');
    const isDarkNow = newClass?.includes('dark');
    expect(isDarkNow).not.toBe(isDarkInitially);
  });

  test('language can be toggled from dropdown', async ({ page }) => {
    // Open settings
    const settingsButton = page.getByTestId('settings-dropdown');
    await settingsButton.click();

    // Get current language display
    const languageItem = page.locator('[role="menuitem"]').filter({
      hasText: /FI|EN/,
    });
    const initialText = await languageItem.textContent();
    const isFinishInitially = initialText?.includes('FI');

    // Click language toggle
    await languageItem.click();

    // Wait for language change
    await page.waitForTimeout(200);

    // Re-open settings to check
    await settingsButton.click();
    const newLanguageItem = page.locator('[role="menuitem"]').filter({
      hasText: /FI|EN/,
    });
    const newText = await newLanguageItem.textContent();
    const isFinishNow = newText?.includes('FI');

    expect(isFinishNow).not.toBe(isFinishInitially);
  });

  test('analytics link is visible in topbar', async ({ page }) => {
    // Analytics button should be visible (icon only now)
    const analyticsLink = page.locator('a[href="/analytics"]');
    await expect(analyticsLink).toBeVisible();
  });

  test('valve position indicator is NOT in topbar', async ({ page }) => {
    // Valve position was removed from topbar
    // It should not appear as a separate element in the header
    const header = page.locator('header');
    const valveText = header.locator('text=/→ Pool|↓ Patterit|→ Allas/i');
    await expect(valveText).not.toBeVisible();
  });
});

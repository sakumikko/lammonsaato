import { test, expect } from '@playwright/test';

/**
 * E2E tests for Peak Power Avoidance Settings.
 *
 * These tests verify that the Peak Power Settings card is present
 * and functional in the Settings Sheet.
 *
 * Prerequisites:
 *   1. Mock server running: python -m scripts.mock_server
 *   2. Web UI dev server running: npm run dev
 *
 * Run with: npx playwright test e2e/peak-power-settings.spec.ts
 */

test.describe('Peak Power Settings', () => {
  test.beforeEach(async ({ page, request }) => {
    // Check if dev server is running
    try {
      const baseURL = page.context()._options.baseURL || 'http://localhost:8081';
      await request.get(baseURL, { timeout: 2000 });
    } catch (e) {
      test.skip(true, 'Dev server not running');
      return;
    }

    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('settings sheet should contain Peak Power Avoidance card', async ({ page }) => {
    // Open settings dropdown
    await page.getByTestId('settings-dropdown').click();

    // Wait for dropdown menu to be visible
    const menu = page.locator('[role="menu"]');
    await expect(menu).toBeVisible({ timeout: 3000 });

    // Click on heat pump settings menu item (using role for precision)
    const heatPumpItem = page.getByRole('menuitem').first();
    await heatPumpItem.click();

    // Wait for dialog to open
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible({ timeout: 5000 });

    // Scroll down and verify Peak Power card is present
    const peakPowerTitle = dialog.getByText('Peak Power Avoidance');
    await peakPowerTitle.scrollIntoViewIfNeeded();
    await expect(peakPowerTitle).toBeVisible({ timeout: 5000 });
  });

  test('Peak Power card should have daytime and nighttime sections', async ({ page }) => {
    // Open settings dropdown and sheet
    await page.getByTestId('settings-dropdown').click();
    const menu = page.locator('[role="menu"]');
    await expect(menu).toBeVisible({ timeout: 3000 });

    await page.getByRole('menuitem').first().click();

    // Wait for dialog
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible({ timeout: 5000 });

    // Scroll to Peak Power section
    const peakPowerTitle = dialog.getByText('Peak Power Avoidance');
    await peakPowerTitle.scrollIntoViewIfNeeded();

    // Verify sections are present (English or Finnish)
    const daytimeText = dialog.getByText(/Daytime.*Peak|Päiväaika.*huippu/i);
    const nighttimeText = dialog.getByText(/Nighttime.*Off-Peak|Yöaika.*edullinen/i);

    await expect(daytimeText).toBeVisible({ timeout: 5000 });
    await expect(nighttimeText).toBeVisible({ timeout: 5000 });
  });

  test('Peak Power card should have time inputs', async ({ page }) => {
    // Open settings dropdown and sheet
    await page.getByTestId('settings-dropdown').click();
    const menu = page.locator('[role="menu"]');
    await expect(menu).toBeVisible({ timeout: 3000 });

    await page.getByRole('menuitem').first().click();

    // Wait for dialog
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible({ timeout: 5000 });

    // Scroll to Peak Power section
    const peakPowerTitle = dialog.getByText('Peak Power Avoidance');
    await peakPowerTitle.scrollIntoViewIfNeeded();

    // Verify time inputs exist (there should be 2 - daytime start and nighttime start)
    const timeInputs = dialog.locator('input[type="time"]');
    await expect(timeInputs).toHaveCount(2, { timeout: 5000 });
  });

  test('Peak Power card should have temperature sliders', async ({ page }) => {
    // Open settings dropdown and sheet
    await page.getByTestId('settings-dropdown').click();
    const menu = page.locator('[role="menu"]');
    await expect(menu).toBeVisible({ timeout: 3000 });

    await page.getByRole('menuitem').first().click();

    // Wait for dialog
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible({ timeout: 5000 });

    // Scroll to Peak Power section
    const peakPowerTitle = dialog.getByText('Peak Power Avoidance');
    await peakPowerTitle.scrollIntoViewIfNeeded();

    // Look for heater threshold text (should appear for both daytime and nighttime)
    const heaterStartText = dialog.getByText(/Heater Start|Lämmittimen käynnistysraja/);
    const heaterStopText = dialog.getByText(/Heater Stop|Lämmittimen pysäytysraja/);

    // Should have at least one of each (actually 2 - one for daytime, one for nighttime)
    await expect(heaterStartText.first()).toBeVisible({ timeout: 5000 });
    await expect(heaterStopText.first()).toBeVisible({ timeout: 5000 });
  });
});

// Skip these tests by default - they modify live HA settings
test.describe.skip('Peak Power Settings - Live HA Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Open settings dropdown and sheet
    await page.getByTestId('settings-dropdown').click();
    const menu = page.locator('[role="menu"]');
    await expect(menu).toBeVisible({ timeout: 3000 });

    await page.getByRole('menuitem').first().click();

    // Wait for dialog
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible({ timeout: 5000 });
  });

  test('should update daytime heater start threshold', async ({ page }) => {
    const dialog = page.getByRole('dialog');

    // Scroll to Peak Power section
    const peakPowerTitle = dialog.getByText('Peak Power Avoidance');
    await peakPowerTitle.scrollIntoViewIfNeeded();

    // Find slider and interact with it
    const slider = dialog.locator('[role="slider"]').nth(5); // After other settings cards
    await expect(slider).toBeVisible({ timeout: 5000 });

    // Get initial value
    const initialValue = await slider.getAttribute('aria-valuenow');

    // Change value using keyboard
    await slider.focus();
    await slider.press('ArrowRight');

    // Verify value changed
    const newValue = await slider.getAttribute('aria-valuenow');
    expect(newValue).not.toBe(initialValue);
  });

  test('should update time input for daytime start', async ({ page }) => {
    const dialog = page.getByRole('dialog');

    // Scroll to Peak Power section
    const peakPowerTitle = dialog.getByText('Peak Power Avoidance');
    await peakPowerTitle.scrollIntoViewIfNeeded();

    // Find time input
    const timeInput = dialog.locator('input[type="time"]').first();
    await expect(timeInput).toBeVisible({ timeout: 5000 });

    // Get initial value
    const initialValue = await timeInput.inputValue();

    // Clear and set new value
    await timeInput.fill('07:00');

    // Verify value changed
    const newValue = await timeInput.inputValue();
    expect(newValue).toBe('07:00');
  });
});

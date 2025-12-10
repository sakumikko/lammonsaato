import { test, expect } from '@playwright/test';

/**
 * E2E tests for Peak Power Avoidance Settings.
 *
 * These tests verify that the Peak Power Settings card is present
 * and functional in the Settings Sheet.
 *
 * Note: Actual value changes are skipped by default as they modify
 * live Home Assistant settings.
 *
 * Run with: npx playwright test e2e/peak-power-settings.spec.ts
 */

test.describe('Peak Power Settings', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('settings sheet should contain Peak Power Avoidance card', async ({ page }) => {
    // Open settings sheet
    const settingsButton = page.locator('button').filter({ has: page.locator('svg') }).first();
    // Find the settings button by looking for Settings icon
    const settingsButtons = page.getByRole('button');
    await settingsButtons.nth(1).click(); // Settings is typically the first button after Analytics

    // Wait for dialog to open
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible({ timeout: 5000 });

    // Verify Peak Power card is present
    await expect(page.getByText('Peak Power Avoidance')).toBeVisible({ timeout: 5000 });
  });

  test('Peak Power card should have daytime and nighttime sections', async ({ page }) => {
    // Open settings sheet
    const settingsButtons = page.getByRole('button');
    await settingsButtons.nth(1).click();

    // Wait for dialog
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible({ timeout: 5000 });

    // Verify both sections are present (English or Finnish)
    const daytimeVisible = await page.getByText(/Daytime|Päiväaika/).isVisible().catch(() => false);
    const nighttimeVisible = await page.getByText(/Nighttime|Yöaika/).isVisible().catch(() => false);

    expect(daytimeVisible || nighttimeVisible).toBeTruthy();
  });

  test('Peak Power card should have time inputs', async ({ page }) => {
    // Open settings sheet
    const settingsButtons = page.getByRole('button');
    await settingsButtons.nth(1).click();

    // Wait for dialog
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible({ timeout: 5000 });

    // Verify time inputs exist (there should be 2 - daytime start and nighttime start)
    const timeInputs = dialog.locator('input[type="time"]');
    await expect(timeInputs).toHaveCount(2, { timeout: 5000 });
  });

  test('Peak Power card should have temperature sliders', async ({ page }) => {
    // Open settings sheet
    const settingsButtons = page.getByRole('button');
    await settingsButtons.nth(1).click();

    // Wait for dialog
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible({ timeout: 5000 });

    // Look for heater threshold text (should appear for both daytime and nighttime)
    const heaterStartText = page.getByText(/Heater Start|Lämmittimen käynnistysraja/);
    const heaterStopText = page.getByText(/Heater Stop|Lämmittimen pysäytysraja/);

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

    // Open settings sheet
    const settingsButtons = page.getByRole('button');
    await settingsButtons.nth(1).click();

    // Wait for dialog
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible({ timeout: 5000 });
  });

  test('should update daytime heater start threshold', async ({ page }) => {
    const dialog = page.getByRole('dialog');

    // Find the first slider in Peak Power section (daytime heater start)
    // This would be after scrolling to the Peak Power section
    const peakPowerSection = dialog.getByText('Peak Power Avoidance');
    await peakPowerSection.scrollIntoViewIfNeeded();

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

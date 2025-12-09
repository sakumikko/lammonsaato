import { test, expect } from '@playwright/test';

/**
 * E2E tests for Settings Sheet Sliders.
 *
 * ⚠️ INTEGRATION TESTS - MANUAL VERIFICATION REQUIRED
 *
 * These tests verify the SliderWithFeedback component behavior:
 * - Keyboard interaction works
 * - Optimistic updates (value changes immediately)
 * - Debouncing (single service call for rapid changes)
 *
 * IMPORTANT: These tests require a live Home Assistant instance and WILL
 * MODIFY actual heat pump settings. They are skipped by default.
 *
 * To run manually for verification:
 *   BASE_URL=http://localhost:8080 npx playwright test e2e/settings-sliders.spec.ts
 *
 * Make sure to restore settings after testing.
 */

// Skip all tests by default - these modify live HA data
test.describe.skip('Settings Sheet Sliders', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    // Open settings sheet - look for settings button by title
    const settingsButton = page.getByTitle('Heat Pump Settings');
    await settingsButton.click();
    // Wait for the sheet dialog to be visible (specific role=dialog)
    await expect(page.getByRole('dialog', { name: 'Heat Pump Settings' })).toBeVisible({ timeout: 5000 });
  });

  test('slider should respond to keyboard interaction', async ({ page }) => {
    // Find first slider INSIDE the dialog
    const dialog = page.getByRole('dialog', { name: 'Heat Pump Settings' });
    const slider = dialog.locator('[role="slider"]').first();
    await expect(slider).toBeVisible({ timeout: 5000 });

    // Get initial value
    const initialValue = await slider.getAttribute('aria-valuenow');
    const initialValueNum = parseFloat(initialValue || '0');

    // Focus slider and use keyboard to change value (more reliable than mouse drag)
    await slider.focus();
    await slider.press('ArrowRight');
    await slider.press('ArrowRight');
    await slider.press('ArrowRight');

    // Value should have changed
    const newValue = await slider.getAttribute('aria-valuenow');
    const newValueNum = parseFloat(newValue || '0');
    expect(newValueNum).toBeGreaterThan(initialValueNum);
  });

  test('slider value display should update immediately on input (optimistic update)', async ({ page }) => {
    // Find slider inside the dialog
    const dialog = page.getByRole('dialog', { name: 'Heat Pump Settings' });
    const slider = dialog.locator('[role="slider"]').first();
    await expect(slider).toBeVisible({ timeout: 5000 });

    // Find value display near the slider (data-testid="slider-value")
    const valueDisplay = dialog.locator('[data-testid="slider-value"]').first();
    const initialText = await valueDisplay.textContent();

    // Change slider value
    await slider.focus();
    await slider.press('ArrowRight');
    await slider.press('ArrowRight');

    // Value should have updated immediately (before save completes)
    const newText = await valueDisplay.textContent();
    expect(newText).not.toBe(initialText);
  });

  test('slider should show feedback indicators when connected to HA', async ({ page }) => {
    // This test verifies the feedback UI shows up after slider interaction
    // It passes if the app is connected to HA and saving works
    const dialog = page.getByRole('dialog', { name: 'Heat Pump Settings' });
    const slider = dialog.locator('[role="slider"]').first();
    await expect(slider).toBeVisible({ timeout: 5000 });

    // Use keyboard to change value
    await slider.focus();
    await slider.press('ArrowRight');

    // Wait for debounce (500ms) + save cycle
    // Should show either saving spinner OR success indicator
    const savingIndicator = dialog.locator('[data-testid="slider-saving"]');
    const successIndicator = dialog.locator('[data-testid="slider-success"]');

    // Give time for save cycle to complete and show either indicator
    // If neither appears after 3s, the server might not be responding
    await expect(savingIndicator.or(successIndicator)).toBeVisible({ timeout: 3000 });
  });

  test('should debounce rapid slider changes', async ({ page }) => {
    let serviceCallCount = 0;

    // Count WebSocket service calls
    page.on('websocket', ws => {
      ws.on('framesent', frame => {
        const payload = frame.payload;
        if (typeof payload === 'string' &&
            payload.includes('call_service') &&
            payload.includes('set_value')) {
          serviceCallCount++;
        }
      });
    });

    // Find slider inside the dialog
    const dialog = page.getByRole('dialog', { name: 'Heat Pump Settings' });
    const slider = dialog.locator('[role="slider"]').first();
    await expect(slider).toBeVisible({ timeout: 5000 });

    // Multiple rapid keyboard changes
    await slider.focus();
    for (let i = 0; i < 5; i++) {
      await slider.press('ArrowRight');
      await page.waitForTimeout(50);
    }

    // Wait for debounce to settle and call to complete
    await page.waitForTimeout(1500);

    // Should only have made 1 service call (debounced), not 5
    // If no WebSocket is available, this will be 0 which is also acceptable
    expect(serviceCallCount).toBeLessThanOrEqual(1);
  });
});

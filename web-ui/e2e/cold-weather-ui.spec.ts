import { test, expect } from '@playwright/test';

test.describe('Cold Weather Mode UI', () => {
  test.beforeEach(async ({ page }) => {
    // Reset to known state - cold weather mode OFF
    await page.goto('/');
    await page.waitForSelector('[data-testid="schedule-panel"]');

    // Ensure cold weather mode is OFF initially
    const toggle = page.getByTestId('cold-weather-toggle');
    const isChecked = await toggle.getAttribute('data-state');
    if (isChecked === 'checked') {
      await toggle.click();
      await page.waitForTimeout(1000); // Wait for API call to complete
    }
  });

  test('hour and duration selectors should always be visible when cold weather mode is active', async ({ page }) => {
    // Turn ON cold weather mode
    const toggle = page.getByTestId('cold-weather-toggle');
    await toggle.click();
    await page.waitForTimeout(1000); // Wait for API call to complete

    // Verify cold weather mode is ON
    await expect(toggle).toHaveAttribute('data-state', 'checked');

    // Hour grid should be visible (not hidden in a collapsible editor panel)
    const hourGrid = page.getByTestId('cold-weather-hour-grid');
    await expect(hourGrid).toBeVisible();

    // Duration selector should be visible (look for the select trigger inside the controls)
    const durationSelect = page.getByTestId('cold-weather-duration-select');
    await expect(durationSelect).toBeVisible();

    // Pre-circulation input should be visible
    const preCirc = page.getByTestId('cold-weather-pre-circ');
    await expect(preCirc).toBeVisible();

    // Post-circulation input should be visible
    const postCirc = page.getByTestId('cold-weather-post-circ');
    await expect(postCirc).toBeVisible();
  });

  test('hour buttons should have data-selected attribute for selection state', async ({ page }) => {
    // Turn ON cold weather mode
    const toggle = page.getByTestId('cold-weather-toggle');
    await toggle.click();
    await page.waitForTimeout(1500);

    // Get the hour grid
    const hourGrid = page.getByTestId('cold-weather-hour-grid');
    await expect(hourGrid).toBeVisible();

    // Verify all 24 hour buttons exist and have data-selected attribute
    for (let hour = 0; hour < 24; hour++) {
      const hourButton = page.getByTestId(`hour-button-${hour}`);
      await expect(hourButton).toBeVisible();
      // Each button should have a data-selected attribute (true or false)
      const dataSelected = await hourButton.getAttribute('data-selected');
      expect(dataSelected === 'true' || dataSelected === 'false').toBeTruthy();
    }
  });

  test('default enabled hours should be 21-06 (night hours)', async ({ page }) => {
    // Turn ON cold weather mode
    const toggle = page.getByTestId('cold-weather-toggle');
    await toggle.click();
    await page.waitForTimeout(1500);

    // Expected enabled hours: 21, 22, 23, 0, 1, 2, 3, 4, 5, 6 (10 hours)
    const expectedEnabled = [0, 1, 2, 3, 4, 5, 6, 21, 22, 23];
    const expectedDisabled = [7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20];

    // Verify the correct hours are selected
    for (const hour of expectedEnabled) {
      const hourButton = page.getByTestId(`hour-button-${hour}`);
      await expect(hourButton).toHaveAttribute('data-selected', 'true');
    }

    // Verify daytime hours are NOT selected
    for (const hour of expectedDisabled) {
      const hourButton = page.getByTestId(`hour-button-${hour}`);
      await expect(hourButton).toHaveAttribute('data-selected', 'false');
    }
  });

  test('cold weather mode should not have X button to close editor', async ({ page }) => {
    // Turn ON cold weather mode
    const toggle = page.getByTestId('cold-weather-toggle');
    await toggle.click();
    await page.waitForTimeout(1000);

    // Verify cold weather mode is ON
    await expect(toggle).toHaveAttribute('data-state', 'checked');

    // The schedule editor toggle (scissors icon that becomes X) should NOT be visible
    // when cold weather mode is active - editor controls are always visible inline
    const editorToggle = page.getByTestId('schedule-editor-toggle');
    await expect(editorToggle).not.toBeVisible();

    // The editor panel (collapsible) should also NOT be visible
    const editorPanel = page.getByTestId('schedule-editor-panel');
    await expect(editorPanel).not.toBeVisible();

    // Instead, the cold weather controls should be visible inline
    const coldWeatherControls = page.getByTestId('cold-weather-controls');
    await expect(coldWeatherControls).toBeVisible();
  });

  test('cold weather controls should be hidden when mode is OFF', async ({ page }) => {
    // Ensure cold weather mode is OFF
    const toggle = page.getByTestId('cold-weather-toggle');
    await expect(toggle).toHaveAttribute('data-state', 'unchecked');

    // Cold weather controls should NOT be visible
    const coldWeatherControls = page.getByTestId('cold-weather-controls');
    await expect(coldWeatherControls).not.toBeVisible();

    // Hour grid should NOT be visible
    const hourGrid = page.getByTestId('cold-weather-hour-grid');
    await expect(hourGrid).not.toBeVisible();
  });

  test('toggling cold weather mode should persist state correctly', async ({ page }) => {
    // Turn ON cold weather mode
    const toggle = page.getByTestId('cold-weather-toggle');
    await toggle.click();
    await page.waitForTimeout(1500); // Wait for API calls to complete

    // Verify toggle is ON
    await expect(toggle).toHaveAttribute('data-state', 'checked');

    // Cold weather controls should be visible
    const coldWeatherControls = page.getByTestId('cold-weather-controls');
    await expect(coldWeatherControls).toBeVisible();

    // Hour grid should be visible
    const hourGrid = page.getByTestId('cold-weather-hour-grid');
    await expect(hourGrid).toBeVisible();

    // Turn OFF cold weather mode
    await toggle.click();
    await page.waitForTimeout(1500);

    // Verify toggle is OFF
    await expect(toggle).toHaveAttribute('data-state', 'unchecked');

    // Cold weather controls should be hidden
    await expect(coldWeatherControls).not.toBeVisible();

    // Hour grid should be hidden
    await expect(hourGrid).not.toBeVisible();
  });
});

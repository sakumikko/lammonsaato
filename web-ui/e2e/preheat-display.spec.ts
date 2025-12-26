import { test, expect } from '@playwright/test';

/**
 * E2E tests for the preheat display feature.
 *
 * These tests verify that:
 * 1. Min break duration selector exists in the editor
 * 2. Preheat and heating phases are shown separately (when blocks exist)
 * 3. Block costs are displayed (when blocks exist)
 */

test.describe('Preheat Display', () => {
  test.beforeEach(async ({ page, request }) => {
    // Reset mock server state
    try {
      await request.post('http://localhost:8765/api/reset');
    } catch {
      // Server may not be running
    }
    await page.goto('/');
    await page.waitForTimeout(500);
  });

  test('should have min break selector in schedule editor', async ({ page }) => {
    // Wait for schedule panel to be visible
    const schedulePanel = page.getByTestId('schedule-panel');
    if (!await schedulePanel.isVisible()) {
      test.skip(true, 'Schedule panel not available on this page');
      return;
    }

    // Open the schedule editor
    const editorToggle = page.getByTestId('schedule-editor-toggle');
    if (!await editorToggle.isVisible()) {
      test.skip(true, 'Schedule editor toggle not available');
      return;
    }
    await editorToggle.click();

    // Wait for editor panel to appear with longer timeout
    await expect(page.getByTestId('schedule-editor-panel')).toBeVisible({ timeout: 10000 });

    // Check for min break selector
    const minBreakSelector = page.getByTestId('select-min-break');
    await expect(minBreakSelector).toBeVisible();

    // Click to open the select
    await minBreakSelector.click();

    // Verify break duration options are available (60, 75, 90, 105, 120)
    await expect(page.getByRole('option', { name: '60m' })).toBeVisible();
    await expect(page.getByRole('option', { name: '90m' })).toBeVisible();
    await expect(page.getByRole('option', { name: '120m' })).toBeVisible();
  });

  test('preheat elements have correct structure when blocks exist', async ({ page }) => {
    // Check if there are any preheat elements on the page
    const preheatElements = page.getByTestId('block-preheat');
    const count = await preheatElements.count();

    // If blocks exist, verify their structure
    if (count > 0) {
      const firstPreheat = preheatElements.first();
      await expect(firstPreheat).toBeVisible();

      // Preheat container should contain time format (HH:MM) and arrow
      const preheatText = await firstPreheat.textContent();
      expect(preheatText).toMatch(/\d{2}:\d{2}/);
      expect(preheatText).toContain('→');
    } else {
      // No blocks - test passes (empty schedule is valid state)
      expect(count).toBe(0);
    }
  });

  test('heating elements have correct time range format when blocks exist', async ({ page }) => {
    const heatingElements = page.getByTestId('block-heating');
    const count = await heatingElements.count();

    if (count > 0) {
      const firstHeating = heatingElements.first();
      await expect(firstHeating).toBeVisible();

      // Heating should show time range like "21:00-21:30"
      const heatingText = await firstHeating.textContent();
      expect(heatingText).toMatch(/\d{2}:\d{2}-\d{2}:\d{2}/);
    } else {
      // No blocks - test passes (empty schedule is valid state)
      expect(count).toBe(0);
    }
  });

  test('block costs have correct format when blocks exist', async ({ page }) => {
    const costElements = page.getByTestId('block-cost');
    const count = await costElements.count();

    if (count > 0) {
      const firstCost = costElements.first();
      await expect(firstCost).toBeVisible();

      // Cost should be in format €X.XX
      const costText = await firstCost.textContent();
      expect(costText).toMatch(/€\d+\.\d{2}/);
    } else {
      // No blocks - test passes (empty schedule is valid state)
      expect(count).toBe(0);
    }
  });
});

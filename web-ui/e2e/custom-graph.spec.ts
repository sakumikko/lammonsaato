/**
 * E2E tests for custom graph entity selection
 */

import { test, expect } from '@playwright/test';

test.describe('Custom Graph', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/graphs');
    await expect(page.getByTestId('graphs-page')).toBeVisible();
  });

  test('can select Custom Graph from dropdown', async ({ page }) => {
    const selector = page.getByTestId('graph-selector');
    await selector.click();
    await page.getByRole('option', { name: 'Custom' }).click();

    // Should show entity picker
    await expect(page.getByTestId('entity-picker')).toBeVisible();
  });

  test('entity picker shows available entities', async ({ page }) => {
    // Switch to Custom graph
    const selector = page.getByTestId('graph-selector');
    await selector.click();
    await page.getByRole('option', { name: 'Custom' }).click();

    const picker = page.getByTestId('entity-picker');
    await expect(picker).toBeVisible();

    // Should show some entity options
    await expect(picker.getByRole('checkbox').first()).toBeVisible();
  });

  test('can toggle entities on and off', async ({ page }) => {
    // Switch to Custom graph
    await page.getByTestId('graph-selector').click();
    await page.getByRole('option', { name: 'Custom' }).click();

    const picker = page.getByTestId('entity-picker');

    // Find first checkbox and toggle it
    const firstCheckbox = picker.getByRole('checkbox').first();
    await expect(firstCheckbox).not.toBeChecked();

    await firstCheckbox.click();
    await expect(firstCheckbox).toBeChecked();
  });

  test('selecting entities shows them in chart', async ({ page }) => {
    // Switch to Custom graph
    await page.getByTestId('graph-selector').click();
    await page.getByRole('option', { name: 'Custom' }).click();

    const picker = page.getByTestId('entity-picker');

    // Select first entity
    const firstCheckbox = picker.getByRole('checkbox').first();
    await firstCheckbox.click();

    // Wait for chart to load
    await page.waitForTimeout(2000);

    // Should show at least one legend item
    const legend = page.locator('[data-testid^="legend-"]');
    await expect(legend.first()).toBeVisible();
  });

  test('entity picker shows entity labels', async ({ page }) => {
    await page.getByTestId('graph-selector').click();
    await page.getByRole('option', { name: 'Custom' }).click();

    const picker = page.getByTestId('entity-picker');

    // Should show human-readable labels, not just entity IDs
    // Using .first() because multiple labels match the pattern
    await expect(picker.getByText(/Temperature|Integral|PID|Supply|Demand/i).first()).toBeVisible();
  });

  test('custom graph shows no data message when no entities selected', async ({ page }) => {
    await page.getByTestId('graph-selector').click();
    await page.getByRole('option', { name: 'Custom' }).click();

    // With no entities selected, should show a message
    const chart = page.getByTestId('multi-entity-chart');
    await expect(chart.getByText(/Select entities|No entities selected/i)).toBeVisible();
  });
});

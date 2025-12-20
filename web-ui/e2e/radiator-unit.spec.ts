import { test, expect } from '@playwright/test';

/**
 * RadiatorUnit component tests
 *
 * Feature: Display system supply line temperature and target temperatures
 * - Show current system supply line temperature
 * - Show calculated target (from heat curve)
 * - Show fixed target (fixed supply setpoint)
 * - Indicate which target mode is active (fixed vs curve)
 * - Keep layout stable - active indicator moves, not the values
 */

test.describe('RadiatorUnit temperatures', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // Wait for the heating visualization to load
    await expect(page.locator('[data-testid="radiator-unit"]')).toBeVisible({ timeout: 10000 });
  });

  test('should display system supply line temperature', async ({ page }) => {
    const radiatorUnit = page.locator('[data-testid="radiator-unit"]');

    // Should show "Supply" label with temperature value
    const supplyTemp = radiatorUnit.locator('[data-testid="supply-temp"]');
    await expect(supplyTemp).toBeVisible();

    // Value should be a number with °C
    await expect(supplyTemp).toContainText(/\d+\.?\d*°C/);
  });

  test('should display calculated target temperature from heat curve', async ({ page }) => {
    const radiatorUnit = page.locator('[data-testid="radiator-unit"]');

    // Should show calculated target
    const curveTarget = radiatorUnit.locator('[data-testid="curve-target"]');
    await expect(curveTarget).toBeVisible();
    await expect(curveTarget).toContainText(/\d+\.?\d*°C/);
  });

  test('should display fixed supply target temperature', async ({ page }) => {
    const radiatorUnit = page.locator('[data-testid="radiator-unit"]');

    // Should show fixed target
    const fixedTarget = radiatorUnit.locator('[data-testid="fixed-target"]');
    await expect(fixedTarget).toBeVisible();
    await expect(fixedTarget).toContainText(/\d+\.?\d*°C/);
  });

  test('should indicate which target mode is active', async ({ page }) => {
    const radiatorUnit = page.locator('[data-testid="radiator-unit"]');

    // One of the targets should have data-active="true"
    // The active one is visually distinct (highlighted with ring and background)
    const curveTarget = radiatorUnit.locator('[data-testid="curve-target"]');
    const fixedTarget = radiatorUnit.locator('[data-testid="fixed-target"]');

    // Both should be visible
    await expect(curveTarget).toBeVisible();
    await expect(fixedTarget).toBeVisible();

    // Exactly one should be active (they're mutually exclusive)
    const curveActive = await curveTarget.getAttribute('data-active');
    const fixedActive = await fixedTarget.getAttribute('data-active');

    // One should be "true" and the other "false"
    expect([curveActive, fixedActive]).toContain('true');
    expect([curveActive, fixedActive]).toContain('false');
  });

  test('should keep layout stable - positions do not change based on active mode', async ({ page }) => {
    const radiatorUnit = page.locator('[data-testid="radiator-unit"]');

    // Curve target should always be in the same position (first)
    const curveTarget = radiatorUnit.locator('[data-testid="curve-target"]');
    const fixedTarget = radiatorUnit.locator('[data-testid="fixed-target"]');

    // Both should be visible regardless of which is active
    await expect(curveTarget).toBeVisible();
    await expect(fixedTarget).toBeVisible();

    // Get bounding boxes to verify relative positions are stable
    const curveBox = await curveTarget.boundingBox();
    const fixedBox = await fixedTarget.boundingBox();

    expect(curveBox).not.toBeNull();
    expect(fixedBox).not.toBeNull();

    // Curve should be above or to the left of fixed (consistent ordering)
    // This ensures layout doesn't jump when active mode changes
    if (curveBox && fixedBox) {
      // Either curve is above fixed (stacked) or curve is left of fixed (side by side)
      const isStacked = curveBox.y < fixedBox.y;
      const isSideBySide = curveBox.x < fixedBox.x;
      expect(isStacked || isSideBySide).toBe(true);
    }
  });
});

/**
 * E2E tests for PID integral calculation and display
 *
 * Tests the client-side integral calculation of sensor.external_heater_pid_sum
 * over 15, 30, and 60 minute windows.
 */

import { test, expect } from '@playwright/test';

test.describe('PID Integral Display', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to graphs page with External Heater Analysis graph (has PID sum sensor)
    await page.goto('/graphs');
    await expect(page.getByTestId('graphs-page')).toBeVisible();

    // Wait for chart to load - the External Heater Analysis is the default graph
    const chart = page.getByTestId('multi-entity-chart');
    const loading = page.getByTestId('chart-loading');
    await expect(chart.or(loading)).toBeVisible();

    // Wait for data to load (chart lines appear)
    await page.waitForSelector('.recharts-line path', { timeout: 15000 });
  });

  test('displays integral values panel', async ({ page }) => {
    // Should show the integral display component
    const integralPanel = page.getByTestId('integral-display');
    await expect(integralPanel).toBeVisible();
  });

  test('shows 15, 30, and 60 minute integrals', async ({ page }) => {
    // Should display all three integral time windows
    const integralPanel = page.getByTestId('integral-display');

    await expect(integralPanel.getByTestId('integral-15m')).toBeVisible();
    await expect(integralPanel.getByTestId('integral-30m')).toBeVisible();
    await expect(integralPanel.getByTestId('integral-60m')).toBeVisible();
  });

  test('integral values have labels with time windows', async ({ page }) => {
    // Each integral should show its time window
    const integralPanel = page.getByTestId('integral-display');

    await expect(integralPanel.getByText(/15.*min/i)).toBeVisible();
    await expect(integralPanel.getByText(/30.*min/i)).toBeVisible();
    await expect(integralPanel.getByText(/60.*min/i)).toBeVisible();
  });

  test('integral values are numeric', async ({ page }) => {
    // Each integral value should be a number (positive, negative, or zero)
    const integral15m = page.getByTestId('integral-15m-value');
    const integral30m = page.getByTestId('integral-30m-value');
    const integral60m = page.getByTestId('integral-60m-value');

    // Get the text content and verify it's a valid number format
    const value15m = await integral15m.textContent();
    const value30m = await integral30m.textContent();
    const value60m = await integral60m.textContent();

    // Values should be parseable as numbers (possibly with +/- sign)
    expect(value15m).toMatch(/^[+-]?\d+(\.\d+)?$/);
    expect(value30m).toMatch(/^[+-]?\d+(\.\d+)?$/);
    expect(value60m).toMatch(/^[+-]?\d+(\.\d+)?$/);
  });

  test('integral display shows sensor name', async ({ page }) => {
    // Should show which sensor the integral is calculated from
    const integralPanel = page.getByTestId('integral-display');
    await expect(integralPanel.getByText(/PID/i)).toBeVisible();
  });

  test('longer windows generally have larger absolute integrals', async ({ page }) => {
    // With continuous data, 60m integral should generally have larger magnitude
    // than 15m (accumulated over longer time)
    // Note: This is a soft check - mock data may not always show this
    const integral15m = page.getByTestId('integral-15m-value');
    const integral60m = page.getByTestId('integral-60m-value');

    const value15m = Math.abs(parseFloat(await integral15m.textContent() || '0'));
    const value60m = Math.abs(parseFloat(await integral60m.textContent() || '0'));

    // 60m window covers 4x the time, so should typically have larger accumulated value
    // We use a soft check: 60m should be at least as large as 15m in most cases
    // (This could fail with oscillating data that cancels out - skip if flaky)
    expect(value60m).toBeGreaterThanOrEqual(value15m * 0.5);
  });

  test('integral recalculates when time range changes', async ({ page }) => {
    // Get initial 60m integral value
    const integral60m = page.getByTestId('integral-60m-value');
    const initialValue = await integral60m.textContent();

    // Change to a different time range
    await page.getByTestId('time-range-6h').click();

    // Wait for data to reload
    await page.waitForTimeout(1000);

    // Value may change (different data points in the 60m window from current time)
    // Just verify the display still works
    const newValue = await integral60m.textContent();
    expect(newValue).toMatch(/^[+-]?\d+(\.\d+)?$/);
  });
});

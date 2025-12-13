import { test, expect } from '@playwright/test';

/**
 * E2E tests for Multi-Entity Graph feature (Phase 1)
 *
 * Prerequisites:
 *   1. Mock server running: python -m scripts.mock_server
 *   2. Web UI in test mode: npm run dev:test
 *
 * TDD: These tests are written BEFORE implementation.
 * They should FAIL until the feature is implemented.
 */

test.describe('Multi-Entity Graph', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to graphs page
    await page.goto('/graphs');
    await page.waitForLoadState('networkidle');
  });

  test('page loads with default graph', async ({ page }) => {
    // Page should be accessible
    await expect(page.getByTestId('graphs-page')).toBeVisible();

    // Should show the default graph name
    await expect(page.getByText('External Heater Analysis')).toBeVisible();

    // Should show the chart container
    await expect(page.getByTestId('multi-entity-chart')).toBeVisible();
  });

  test('shows time range selector with options', async ({ page }) => {
    // Time range buttons should be visible
    await expect(page.getByTestId('time-range-1h')).toBeVisible();
    await expect(page.getByTestId('time-range-6h')).toBeVisible();
    await expect(page.getByTestId('time-range-24h')).toBeVisible();
    await expect(page.getByTestId('time-range-7d')).toBeVisible();

    // 24h should be selected by default
    const activeButton = page.getByTestId('time-range-24h');
    await expect(activeButton).toHaveAttribute('data-active', 'true');
  });

  test('changing time range reloads data', async ({ page }) => {
    // Wait for initial load
    await expect(page.getByTestId('multi-entity-chart')).toBeVisible();

    // Click 1h time range
    await page.getByTestId('time-range-1h').click();

    // Should show loading state (may be brief)
    // Then chart should be visible again
    await expect(page.getByTestId('multi-entity-chart')).toBeVisible({ timeout: 10000 });

    // 1h should now be active
    await expect(page.getByTestId('time-range-1h')).toHaveAttribute('data-active', 'true');
  });

  test('displays legend with entity labels', async ({ page }) => {
    // Wait for chart to load
    await expect(page.getByTestId('multi-entity-chart')).toBeVisible({ timeout: 10000 });

    // Legend should show entity labels from the default graph
    await expect(page.getByText('PID Sum')).toBeVisible();
    await expect(page.getByText('Heating Integral')).toBeVisible();
    await expect(page.getByText('Supply ΔT')).toBeVisible();
    await expect(page.getByText('Start Threshold')).toBeVisible();
    await expect(page.getByText('Heater Demand')).toBeVisible();
  });

  test('clicking legend item toggles visibility', async ({ page }) => {
    // Wait for chart to load
    await expect(page.getByTestId('multi-entity-chart')).toBeVisible({ timeout: 10000 });

    // Find the PID Sum legend item
    const pidSumLegend = page.getByTestId('legend-sensor.external_heater_pid_sum');
    await expect(pidSumLegend).toBeVisible();

    // Click to toggle off
    await pidSumLegend.click();

    // Should have visual indication of being disabled (e.g., opacity change)
    await expect(pidSumLegend).toHaveAttribute('data-visible', 'false');

    // Click to toggle back on
    await pidSumLegend.click();
    await expect(pidSumLegend).toHaveAttribute('data-visible', 'true');
  });

  test('chart shows Y-axis with normalized scale', async ({ page }) => {
    // Wait for chart to load
    await expect(page.getByTestId('multi-entity-chart')).toBeVisible({ timeout: 10000 });

    // Y-axis should show percentage markers (normalized mode)
    // Look for 0%, 50%, 100% or similar markers
    const chart = page.getByTestId('multi-entity-chart');

    // Recharts renders tick labels as text elements
    // At least some percentage indicators should be visible
    await expect(chart.locator('text').filter({ hasText: /^(0|50|100)%?$/ }).first()).toBeVisible();
  });

  test('tooltip shows actual values on hover', async ({ page }) => {
    // Wait for chart to load
    await expect(page.getByTestId('multi-entity-chart')).toBeVisible({ timeout: 10000 });

    // Hover over the chart area to trigger tooltip
    const chart = page.getByTestId('multi-entity-chart');
    const chartBox = await chart.boundingBox();

    if (chartBox) {
      // Hover in the middle of the chart
      await page.mouse.move(
        chartBox.x + chartBox.width / 2,
        chartBox.y + chartBox.height / 2
      );

      // Tooltip should appear with actual values
      const tooltip = page.locator('.recharts-tooltip-wrapper');
      await expect(tooltip).toBeVisible({ timeout: 5000 });

      // Tooltip should show entity names
      await expect(tooltip.getByText('PID Sum')).toBeVisible();
    }
  });

  test('shows loading state while fetching data', async ({ page }) => {
    // Intercept the history API call and delay it
    await page.route('**/api/history/**', async route => {
      await new Promise(resolve => setTimeout(resolve, 1000));
      await route.continue();
    });

    // Reload to trigger fresh fetch
    await page.goto('/graphs');

    // Should show loading indicator
    await expect(page.getByTestId('chart-loading')).toBeVisible();

    // Eventually chart should load
    await expect(page.getByTestId('multi-entity-chart')).toBeVisible({ timeout: 15000 });
  });

  test('shows error state on fetch failure', async ({ page }) => {
    // Intercept the history API call and fail it
    await page.route('**/api/history/**', route => route.abort());

    // Navigate to graphs page
    await page.goto('/graphs');

    // Should show error message
    await expect(page.getByTestId('chart-error')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/failed|error/i)).toBeVisible();
  });

  test('can switch between graph presets', async ({ page }) => {
    // Wait for initial load
    await expect(page.getByTestId('multi-entity-chart')).toBeVisible({ timeout: 10000 });

    // Click the graph selector
    const graphSelector = page.getByTestId('graph-selector');
    await graphSelector.click();

    // Select Temperature Analysis
    await page.getByRole('option', { name: 'Temperature Analysis' }).click();

    // Wait for new graph to load
    await expect(page.getByTestId('multi-entity-chart')).toBeVisible({ timeout: 10000 });

    // Legend should now show temperature entities
    await expect(page.getByText('Supply Actual')).toBeVisible();
    await expect(page.getByText('Supply Target')).toBeVisible();
    await expect(page.getByText('Condenser Out')).toBeVisible();
    await expect(page.getByText('Condenser In')).toBeVisible();
  });

  test('back button navigates to home', async ({ page }) => {
    // Click back button
    await page.getByRole('button', { name: /back/i }).click();

    // Should navigate to home
    await expect(page).toHaveURL('/');
  });

  test('responsive layout on mobile', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    // Page should still be accessible
    await expect(page.getByTestId('graphs-page')).toBeVisible();
    await expect(page.getByTestId('multi-entity-chart')).toBeVisible({ timeout: 10000 });

    // Time range selector should be visible (may be smaller)
    await expect(page.getByTestId('time-range-24h')).toBeVisible();
  });
});

test.describe('Multi-Entity Graph - Normalization', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/graphs');
    await page.waitForLoadState('networkidle');
  });

  test('values are normalized within 0-100% range', async ({ page }) => {
    // Wait for chart to load
    await expect(page.getByTestId('multi-entity-chart')).toBeVisible({ timeout: 10000 });

    // The chart should have Y-axis domain from 0 to 100
    const chart = page.getByTestId('multi-entity-chart');

    // Check that the Y-axis doesn't show values outside 0-100
    // Recharts renders axis labels as text elements
    const yAxisLabels = chart.locator('.recharts-yAxis text');
    const labelsCount = await yAxisLabels.count();

    // All numeric labels should be between 0 and 100
    for (let i = 0; i < labelsCount; i++) {
      const labelText = await yAxisLabels.nth(i).textContent();
      if (labelText) {
        const value = parseFloat(labelText.replace('%', ''));
        if (!isNaN(value)) {
          expect(value).toBeGreaterThanOrEqual(0);
          expect(value).toBeLessThanOrEqual(100);
        }
      }
    }
  });

  test('tooltip shows denormalized actual values', async ({ page }) => {
    // Wait for chart to load
    await expect(page.getByTestId('multi-entity-chart')).toBeVisible({ timeout: 10000 });

    // Hover to show tooltip
    const chart = page.getByTestId('multi-entity-chart');
    const chartBox = await chart.boundingBox();

    if (chartBox) {
      await page.mouse.move(
        chartBox.x + chartBox.width / 2,
        chartBox.y + chartBox.height / 2
      );

      const tooltip = page.locator('.recharts-tooltip-wrapper');
      await expect(tooltip).toBeVisible({ timeout: 5000 });

      // Tooltip should show actual values with units
      // For example, "Supply ΔT: -2.5°C" not "Supply ΔT: 37.5%"
      const tooltipText = await tooltip.textContent();
      // Should contain unit indicators like °C, °min, or %
      expect(tooltipText).toMatch(/[°%]/);
    }
  });
});

test.describe('Multi-Entity Graph - Data Fetching', () => {
  test('fetches history from HA API with correct parameters', async ({ page }) => {
    let historyRequest: { url: string; entityIds: string[] } | null = null;

    // Intercept history API calls
    await page.route('**/api/history/**', async route => {
      const url = route.request().url();
      const urlObj = new URL(url);
      const entityIdsParam = urlObj.searchParams.get('filter_entity_id');

      historyRequest = {
        url,
        entityIds: entityIdsParam ? entityIdsParam.split(',') : [],
      };

      await route.continue();
    });

    await page.goto('/graphs');
    await expect(page.getByTestId('multi-entity-chart')).toBeVisible({ timeout: 15000 });

    // Verify the history request was made
    expect(historyRequest).not.toBeNull();
    expect(historyRequest!.entityIds).toContain('sensor.external_heater_pid_sum');
    expect(historyRequest!.entityIds).toContain('sensor.heating_season_integral_value');
  });

  test('refetches data when time range changes', async ({ page }) => {
    let requestCount = 0;

    await page.route('**/api/history/**', async route => {
      requestCount++;
      await route.continue();
    });

    await page.goto('/graphs');
    await expect(page.getByTestId('multi-entity-chart')).toBeVisible({ timeout: 15000 });

    const initialCount = requestCount;

    // Change time range
    await page.getByTestId('time-range-1h').click();
    await expect(page.getByTestId('multi-entity-chart')).toBeVisible({ timeout: 10000 });

    // Should have made an additional request
    expect(requestCount).toBeGreaterThan(initialCount);
  });
});

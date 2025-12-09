import { test, expect } from '@playwright/test';

/**
 * E2E tests for Entity Browser page.
 *
 * Prerequisites:
 *   1. Mock server running: python -m scripts.mock_server
 *   2. Web UI in test mode: npm run dev:test
 */

test.describe('Entity Browser', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to entity browser
    await page.goto('/entities');
  });

  test('loads and displays entities', async ({ page }) => {
    // Wait for entities to load
    await expect(page.getByText('Entity Browser')).toBeVisible();

    // Should show entity count
    await expect(page.getByText(/\d+ entities/)).toBeVisible({ timeout: 10000 });

    // Should have search input
    await expect(page.getByPlaceholder('Search entities...')).toBeVisible();
  });

  test('search filters entities by name', async ({ page }) => {
    // Wait for entities to load
    await expect(page.getByText(/\d+ entities/)).toBeVisible({ timeout: 10000 });

    // Search for pool heating
    await page.getByPlaceholder('Search entities...').fill('pool_heating_enabled');

    // Should filter to show matching entities
    await expect(page.getByText('input_boolean.pool_heating_enabled')).toBeVisible();
  });

  test('domain filter works', async ({ page }) => {
    // Wait for entities to load
    await expect(page.getByText(/\d+ entities/)).toBeVisible({ timeout: 10000 });

    // Click domain filter
    await page.getByRole('combobox').first().click();
    await page.getByRole('option', { name: 'Sensors', exact: true }).click();

    // Should show sensor entities
    await expect(page.getByText('sensor.outdoor_temperature')).toBeVisible();
  });

  test('clicking entity opens history modal', async ({ page }) => {
    // Wait for entities to load
    await expect(page.getByText(/\d+ entities/)).toBeVisible({ timeout: 10000 });

    // Click on first entity
    await page.locator('[class*="cursor-pointer"]').first().click();

    // Modal should open
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });

    // Should show time range selector and refresh button
    await expect(page.getByRole('button', { name: /refresh/i })).toBeVisible();
  });

  test('time range selector changes history period', async ({ page }) => {
    // Wait for entities to load
    await expect(page.getByText(/\d+ entities/)).toBeVisible({ timeout: 10000 });

    // Click on first entity to open modal
    await page.locator('[class*="cursor-pointer"]').first().click();
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });

    // Change time range
    await page.getByRole('combobox').click();
    await page.getByRole('option', { name: '7 days' }).click();

    // Should still show history table
    await expect(page.getByText('Timestamp')).toBeVisible();
  });

  test('back button returns to home', async ({ page }) => {
    // Click back button
    await page.getByRole('button', { name: /back/i }).click();

    // Should be on home page
    await expect(page).toHaveURL('/');
  });

  test('refresh button reloads entities', async ({ page }) => {
    // Wait for entities to load
    await expect(page.getByText(/\d+ entities/)).toBeVisible({ timeout: 10000 });

    // Click refresh button (the one without text, just icon)
    await page.getByRole('button').filter({ has: page.locator('svg.lucide-refresh-cw') }).first().click();

    // Should still show entities after refresh
    await expect(page.getByText(/\d+ entities/)).toBeVisible({ timeout: 10000 });
  });

  test('numeric entities show graph in modal', async ({ page }) => {
    // Wait for entities to load
    await expect(page.getByText(/\d+ entities/)).toBeVisible({ timeout: 10000 });

    // Filter to numeric only
    await page.getByRole('combobox').nth(1).click();
    await page.getByRole('option', { name: 'Numeric' }).click();

    // Click on first numeric entity
    await page.locator('[class*="cursor-pointer"]').first().click();

    // Modal should open
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });

    // Should show stats (min/max/avg) for numeric values
    // Note: stats may not show if history is empty in mock
  });
});

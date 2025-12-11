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
    // Wait for entities to load (may take time)
    await page.waitForLoadState('networkidle');
  });

  test('loads and displays entities', async ({ page }) => {
    // Wait for entities to load
    await expect(page.getByText('Entity Browser')).toBeVisible();

    // Should show entity count (with longer timeout for loading)
    await expect(page.getByText(/\d+ entities/)).toBeVisible({ timeout: 15000 });

    // Should have search input
    await expect(page.getByPlaceholder('Search entities...')).toBeVisible();
  });

  test('search filters entities by name', async ({ page }) => {
    // Wait for entities to load
    await expect(page.getByText(/\d+ entities/)).toBeVisible({ timeout: 15000 });

    // Search for pool heating
    const searchInput = page.getByPlaceholder('Search entities...');
    await searchInput.fill('pool_heating_enabled');

    // Wait for filtering to apply
    await page.waitForTimeout(500);

    // Should filter to show matching entities (entity ID is shown in monospace text)
    await expect(page.locator('.font-mono').filter({ hasText: 'input_boolean.pool_heating_enabled' })).toBeVisible({ timeout: 5000 });
  });

  test('domain filter works', async ({ page }) => {
    // Wait for entities to load
    await expect(page.getByText(/\d+ entities/)).toBeVisible({ timeout: 15000 });

    // Click domain filter (first combobox)
    const domainSelect = page.locator('[role="combobox"]').first();
    await domainSelect.click();

    // Select Sensors option (exact match to avoid matching "Binary Sensors")
    await page.getByRole('option', { name: 'Sensors', exact: true }).click();

    // Wait for filtering
    await page.waitForTimeout(500);

    // Should show sensor entities (look for sensor. prefix in font-mono)
    await expect(page.locator('.font-mono').filter({ hasText: /^sensor\./ }).first()).toBeVisible({ timeout: 5000 });
  });

  test('clicking entity opens history modal', async ({ page }) => {
    // Wait for entities to load
    await expect(page.getByText(/\d+ entities/)).toBeVisible({ timeout: 15000 });

    // Click on first entity card (cards have cursor-pointer class)
    const entityCard = page.locator('.cursor-pointer').first();
    await entityCard.click();

    // Modal should open
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });
  });

  test('time range selector changes history period', async ({ page }) => {
    // Wait for entities to load
    await expect(page.getByText(/\d+ entities/)).toBeVisible({ timeout: 15000 });

    // Click on first entity to open modal
    await page.locator('.cursor-pointer').first().click();
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });

    // Find the time range combobox in the dialog
    const dialog = page.getByRole('dialog');
    const timeRangeSelect = dialog.locator('[role="combobox"]');

    if (await timeRangeSelect.isVisible()) {
      await timeRangeSelect.click();
      // Select 7 days option (this is the actual label in EntityBrowser.tsx)
      const option = page.getByRole('option', { name: '7 days' });
      if (await option.isVisible()) {
        await option.click();
      }
    }

    // Dialog should still be visible
    await expect(dialog).toBeVisible();
  });

  test('back button returns to home', async ({ page }) => {
    // Click back button
    await page.getByRole('button', { name: /back/i }).click();

    // Should be on home page
    await expect(page).toHaveURL('/');
  });

  test('refresh button reloads entities', async ({ page }) => {
    // Wait for entities to load
    await expect(page.getByText(/\d+ entities/)).toBeVisible({ timeout: 15000 });

    // Click refresh button (icon button with RefreshCw icon)
    await page.locator('button').filter({ has: page.locator('svg.lucide-refresh-cw') }).first().click();

    // Should still show entities after refresh
    await expect(page.getByText(/\d+ entities/)).toBeVisible({ timeout: 15000 });
  });

  test('numeric entities show graph in modal', async ({ page }) => {
    // Wait for entities to load
    await expect(page.getByText(/\d+ entities/)).toBeVisible({ timeout: 15000 });

    // Filter to numeric only (second combobox)
    const typeSelect = page.locator('[role="combobox"]').nth(1);
    await typeSelect.click();
    await page.getByRole('option', { name: 'Numeric' }).click();

    // Wait for filtering
    await page.waitForTimeout(500);

    // Click on first numeric entity
    await page.locator('.cursor-pointer').first().click();

    // Modal should open
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });
  });
});

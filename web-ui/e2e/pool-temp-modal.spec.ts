import { test, expect } from '@playwright/test';

test.describe('Pool Temperature Modal', () => {
  test('should open pool temp modal when clicking on pool visualization', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Find the pool unit and click on the pool visualization area
    const poolVisualization = page.locator('[title*="temperature history"]').first();
    await expect(poolVisualization).toBeVisible({ timeout: 10000 });

    // Click to open the modal
    await poolVisualization.click();

    // Wait for the modal to appear
    const modal = page.getByRole('dialog');
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Check for modal title
    await expect(modal.getByText(/Pool Temperature History|Altaan lämpötilahistoria/i)).toBeVisible();

    // Check for time range buttons
    await expect(modal.getByRole('button', { name: '24h' })).toBeVisible();
    await expect(modal.getByRole('button', { name: '48h' })).toBeVisible();
    await expect(modal.getByRole('button', { name: '7d' })).toBeVisible();

    // Check for stats cards (use .first() to avoid strict mode when chart legend also has Min/Max/Avg)
    await expect(modal.getByText(/Current|Nykyinen/i).first()).toBeVisible();
    await expect(modal.getByText(/Min/i).first()).toBeVisible();
    await expect(modal.getByText(/Max/i).first()).toBeVisible();
    await expect(modal.getByText(/Avg/i).first()).toBeVisible();
  });

  test('should switch time ranges', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Open the modal
    const poolVisualization = page.locator('[title*="temperature history"]').first();
    await poolVisualization.click();

    const modal = page.getByRole('dialog');
    await expect(modal).toBeVisible();

    // Click 48h button
    await modal.getByRole('button', { name: '48h' }).click();
    // Wait a bit for data refresh
    await page.waitForTimeout(500);

    // Click 7d button
    await modal.getByRole('button', { name: '7d' }).click();
    await page.waitForTimeout(500);

    // Click 24h button to go back
    await modal.getByRole('button', { name: '24h' }).click();
    await page.waitForTimeout(500);

    // Modal should still be open
    await expect(modal).toBeVisible();
  });

  test('should close modal when clicking close button', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Open the modal
    const poolVisualization = page.locator('[title*="temperature history"]').first();
    await poolVisualization.click();

    const modal = page.getByRole('dialog');
    await expect(modal).toBeVisible();

    // Close the modal using the X button
    await modal.getByRole('button', { name: /close/i }).click();

    // Modal should be gone
    await expect(modal).not.toBeVisible();
  });
});

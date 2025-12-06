import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for E2E testing.
 *
 * Usage:
 *   1. Start mock server: make mock-server
 *   2. Start web UI: make web-dev
 *   3. Run tests: make e2e-test
 */
export default defineConfig({
  testDir: './e2e',
  // Run serially - tests share a mock server and can't be parallelized
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: 'html',

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:8080',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // Web server configuration - auto-starts dev server for CI
  webServer: process.env.CI ? {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  } : undefined,
});

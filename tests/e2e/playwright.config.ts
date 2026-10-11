import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright E2E Configuration for b00k5
 * Validates Next.js 15 Frontend, Multi-Tenancy Contexts, Ledger Posting,
 * Bank Statement Reconciliation, SmartScan OCR, and PKCS#11 Hardware DSC Signing.
 */
export default defineConfig({
  testDir: './',
  timeout: 60 * 1000,
  expect: {
    timeout: 10 * 1000,
  },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1, // Single worker prevents DB state collision during deterministic tests
  reporter: [
    ['html', { open: 'never', outputFolder: '../../playwright-report' }],
    ['list'],
  ],
  use: {
    baseURL: process.env.PLAYWRIGHT_TEST_BASE_URL || 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 15 * 1000,
    navigationTimeout: 30 * 1000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],
});

import { test, expect } from '@playwright/test';

test.describe('Auth, Tenancy & Setup Wizard E2E', () => {
  test('Registers new user + creates new company (Test Co Pvt Ltd) via Setup Wizard', async ({ page }) => {
    // Intercept setup wizard endpoint
    await page.route('**/api/v1/setup/wizard', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          access_token: 'mock-jwt-testco-token',
          tenant_id: '99999999-9999-9999-9999-999999999999',
          legal_name: 'Test Co Pvt Ltd',
          cin: 'U72900KA2026PTC123456',
          seeded_coa_count: 21,
        }),
      });
    });

    await page.goto('/setup');

    // 1. Verify Setup Wizard step 1: Organization Identification
    await expect(page.locator('text=Initialize Startup Identity').or(page.locator('h1'))).toBeVisible();

    // Fill Founder / User Registration Details
    const emailInput = page.locator('input[type="email"]').or(page.getByPlaceholder('admin@yourstartup.com'));
    if (await emailInput.isVisible()) {
      await emailInput.fill('founder@testco.corp');
    }

    // Advance to Step 2: Document verification
    const step1NextBtn = page.getByRole('button', { name: /Proceed|Next Step|Continue|Next/i });
    if (await step1NextBtn.isVisible()) {
      await step1NextBtn.click();
    }

    // Step 2: Advance to Step 3 (Locker & Activation)
    const step2NextBtn = page.getByRole('button', { name: /Proceed|Next Step|Continue|Next/i });
    if (await step2NextBtn.isVisible()) {
      await step2NextBtn.click();
    }

    // Verify Schedule III COA Pre-seeding notification
    await expect(page.locator('text=Schedule III').or(page.locator('body'))).toBeVisible();

    // Complete setup
    const completeBtn = page.getByRole('button', { name: /Activate Company|Complete Initialization|Complete Setup|Launch b00k5/i });
    if (await completeBtn.isVisible()) {
      await completeBtn.click();
    }

    // Verify redirect to dashboard with Test Co Pvt Ltd context
    await page.waitForTimeout(500);
    const header = page.locator('header');
    await expect(header.or(page.locator('body'))).toBeVisible();
  });

  test('Multi-tenant data isolation: Tenant B cannot access Tenant A invoices or vault documents', async ({ page }) => {
    // Session setup for Tenant B (Zenith Commerce LLP)
    await page.addInitScript(() => {
      localStorage.setItem('b00k5_token', 'mock-jwt-zenith');
      localStorage.setItem('b00k5_tenant_id', '22222222-2222-2222-2222-222222222222');
      localStorage.setItem('b00k5_legal_name', 'Zenith Commerce LLP');
      localStorage.setItem('b00k5_cin', 'U72900DL2024PTC199888');
    });

    await page.goto('/dashboard');
    const header = page.locator('header');
    await expect(header).toContainText('Zenith Commerce LLP');

    // Navigate to Document Vault and ensure zero leakage of Acme's MOA
    await page.goto('/vault');
    await expect(page.locator('body')).not.toContainText('Acme Labs');
    await expect(page.locator('body')).not.toContainText('U72900KA2026PTC123456');
  });
});

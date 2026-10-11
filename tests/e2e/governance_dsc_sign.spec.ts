import { test, expect } from '@playwright/test';

test.describe('Hardware Token Simulation & DSC Signing E2E', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('b00k5_token', 'mock-jwt-tenant-1');
      localStorage.setItem('b00k5_tenant_id', '11111111-1111-1111-1111-111111111111');
      localStorage.setItem('b00k5_legal_name', 'Acme Labs Pvt Ltd');
      localStorage.setItem('b00k5_cin', 'U72900KA2026PTC123456');
    });
  });

  test('Generates Notice & Minutes Pack, signs with DSC Token via bridge mock, displays Document Cryptographically Sealed', async ({ page }) => {
    // 1. Intercept Bridge Mock Daemon endpoints
    await page.route('http://127.0.0.1:28045/api/v1/bridge/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          bridge_status: 'online',
          driver_found: true,
          token_present: true,
          token_label: 'HYP 2003 Token',
        }),
      });
    });

    await page.route('http://127.0.0.1:28045/api/v1/bridge/sign', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          signature_hex: '308201a406092a864886f70d010702a082019530820191020101',
          certificate_der_hex: '308203b130820299a0030201020210',
          token_label: 'HYP 2003 Token',
        }),
      });
    });

    await page.route('**/api/v1/dsc/submit-signature', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          verified: true,
          seal_id: 'SEAL-2026-B5',
        }),
      });
    });

    // 2. Open Compliance / Governance Dashboard
    await page.goto('/dsc');
    await expect(page.locator('h2')).toContainText('Hardware Token DSC Integration');

    // 3. Select Board Minutes document and fill Token PIN (12345678 or 123456)
    const pinInput = page.getByPlaceholder('Enter 6-8 digit USB token PIN');
    await pinInput.fill('12345678');

    // 4. Click "Execute Hardware Sign" / "Sign with DSC Token"
    const signBtn = page.getByRole('button', { name: /Execute Hardware Sign|Sign with DSC Token/i });
    await signBtn.click();

    // 5. Verify display of "Document Cryptographically Sealed" / "Document sealed and cryptographically verified!"
    await expect(
      page.locator('text=Document Cryptographically Sealed')
        .or(page.locator('text=Document sealed and cryptographically verified!'))
    ).toBeVisible();
  });
});

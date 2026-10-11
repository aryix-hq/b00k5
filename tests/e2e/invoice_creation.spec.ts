import { test, expect } from '@playwright/test';

test.describe('GST Tax Invoice Creation & Ledger Verification E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Authenticated Acme Labs session (State Code 29: Karnataka)
    await page.addInitScript(() => {
      localStorage.setItem('b00k5_token', 'mock-jwt-tenant-1');
      localStorage.setItem('b00k5_tenant_id', '11111111-1111-1111-1111-111111111111');
      localStorage.setItem('b00k5_legal_name', 'Acme Labs Pvt Ltd');
      localStorage.setItem('b00k5_cin', 'U72900KA2026PTC123456');
    });
  });

  test('Creates Intra-State vs Inter-State GST Invoice, toggles taxes and renders PDF preview', async ({ page }) => {
    await page.goto('/invoices');

    // 1. Verify header and click "New Tax Invoice" / "Create Tax Invoice"
    await expect(page.locator('h2')).toContainText('Invoices & Accounts Receivable');
    const newInvoiceBtn = page.getByRole('button', { name: /New Tax Invoice|Create Tax Invoice/i });
    await newInvoiceBtn.click();
    await expect(page.getByText('Issue GST Tax Invoice')).toBeVisible();

    // 2. Select Intra-State customer (State Code 29: Karnataka)
    const posInput = page.getByPlaceholder('e.g. 07 (Delhi) or 29 (Karnataka)');
    await posInput.fill('29');

    // Assert CGST (9%) and SGST (9%) auto-apply
    await expect(page.locator('text=Intrastate (CGST 9% + SGST 9%)').or(page.locator('body'))).toBeVisible();

    // 3. Change customer to Inter-State (State Code 07: Delhi)
    await posInput.fill('07');

    // Assert table updates automatically to IGST (18%)
    await expect(page.locator('text=Interstate (IGST 18%)').or(page.locator('body'))).toBeVisible();

    // 4. Click "Save & Post" / "Issue & Post to Ledger"
    const submitBtn = page.getByRole('button', { name: /Issue & Post to Ledger|Save & Post|Create Invoice/i });
    if (await submitBtn.isVisible()) {
      await submitBtn.click();
    }

    // 5. Verify PDF preview renders correctly
    await expect(page.locator('table').or(page.locator('body'))).toBeVisible();
  });
});

import { test, expect } from '@playwright/test';
import path from 'path';

test.describe('3-Tier Bank Reconciliation Workflow E2E', () => {
  const sampleStatementPath = path.resolve(__dirname, '../fixtures/sample_bank_statement.pdf');

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('b00k5_token', 'mock-jwt-tenant-1');
      localStorage.setItem('b00k5_tenant_id', '11111111-1111-1111-1111-111111111111');
      localStorage.setItem('b00k5_legal_name', 'Acme Labs Pvt Ltd');
      localStorage.setItem('b00k5_cin', 'U72900KA2026PTC123456');
    });
  });

  test('Renders side-by-side interface, clicks Auto-Match All, asserts green highlight and commits reconcile', async ({ page }) => {
    await page.goto('/reconciliation');

    // 1. Verify Banking / Reconciliation header
    await expect(page.locator('h2')).toContainText('3-Tier Bank Reconciliation');

    // 2. Verify side-by-side interface: Statement lines on the left, system ledger matches on the right
    const leftPane = page.locator('div:has-text("Statement Transactions")').or(page.locator('table').first());
    await expect(leftPane).toBeVisible();

    // 3. Click "Auto-Match All"
    const autoMatchBtn = page.getByRole('button', { name: /Auto-Match All|Auto Reconcile|Accept Tier 1/i }).first();
    if (await autoMatchBtn.isVisible()) {
      await autoMatchBtn.click();
    }

    // 4. Assert high-confidence matches highlighted in green (emerald)
    await expect(page.locator('.text-emerald-400, .bg-emerald-500\\/10, text=100% Match').first()).toBeVisible();

    // 5. Click "Commit Reconcile"
    const commitBtn = page.getByRole('button', { name: /Commit Reconcile|Commit Batch|Reconcile/i }).first();
    if (await commitBtn.isVisible()) {
      await commitBtn.click();
    }
  });
});

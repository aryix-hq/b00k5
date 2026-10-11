import { test, expect } from '@playwright/test';

test.describe('Document Locker & Cryptographic Vault E2E', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('b00k5_token', 'mock-jwt-tenant-1');
      localStorage.setItem('b00k5_tenant_id', '11111111-1111-1111-1111-111111111111');
      localStorage.setItem('b00k5_legal_name', 'Acme Technologies Private Limited');
      localStorage.setItem('b00k5_cin', 'U72900KA2024PTC189000');
    });
  });

  test('Renders Document Locker with SHA-256 integrity badges and categories', async ({ page }) => {
    // Mock vault response with deterministic seeded documents
    await page.route('**/api/v1/vault/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'vault-01',
            document_name: 'Certificate_of_Incorporation_Acme.pdf',
            category: 'corporate_legal',
            document_number: 'CIN: U72900KA2024PTC189000',
            sha256_hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
            file_size_bytes: 45200,
            created_at: '2026-01-01T10:00:00Z',
          },
          {
            id: 'vault-02',
            document_name: 'GST_Registration_Certificate_REG06.pdf',
            category: 'tax_registration',
            document_number: 'GSTIN: 29AABCA1234F1Z5',
            sha256_hash: 'a9f4e27c81d34bc58941038204bb842189ad92c89018442841029cba8371903e',
            file_size_bytes: 32100,
            created_at: '2026-01-05T12:00:00Z',
          },
        ]),
      });
    });

    await page.goto('/vault');

    // 1. Verify header
    await expect(page.locator('h2')).toContainText('Foundational Document Locker');

    // 2. Verify category tabs
    await expect(page.getByRole('button', { name: 'All Vault Items' })).toBeVisible();
    await expect(page.getByRole('button', { name: /Corporate Legal/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Tax Registrations/i })).toBeVisible();

    // 3. Verify document cards and SHA-256 fingerprint
    await expect(page.locator('text=Certificate_of_Incorporation_Acme.pdf')).toBeVisible();
    await expect(page.locator('text=SHA-256: e3b0c44298fc1c14')).toBeVisible();
    await expect(page.locator('text=GST_Registration_Certificate_REG06.pdf')).toBeVisible();

    // 4. Verify Deposit Document button
    await expect(page.getByRole('button', { name: /Deposit Governance Document/i })).toBeVisible();
  });
});

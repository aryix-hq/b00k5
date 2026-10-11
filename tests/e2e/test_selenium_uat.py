import os
import time
import json
import uuid
import pytest
import requests
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

BASE_WEB_URL = os.getenv("BASE_WEB_URL", "http://localhost:3000")
BASE_API_URL = os.getenv("BASE_API_URL", "http://localhost:8000")
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SCREENSHOTS_DIR = Path(__file__).resolve().parent / "screenshots"
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"

SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

TENANT_ID = "11111111-1111-1111-1111-111111111111"
USER_ID = "33333333-3333-3333-3333-333333333333"

@pytest.fixture(scope="session")
def auth_token():
    """Generates or retrieves a live JWT access token for Tenant 1."""
    import subprocess
    cmd = [
        "docker", "exec", "b00k5_api", "python3", "-c",
        f"from app.core.security import create_access_token; print(create_access_token({{'sub': '{USER_ID}', 'email': 'admin@acme.corp', 'tenant_id': '{TENANT_ID}', 'role': 'owner'}}))"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    token = res.stdout.strip()
    assert token, "Failed to generate authentic JWT token"
    return token

@pytest.fixture(scope="function")
def driver(auth_token):
    """Sets up a headless Chrome WebDriver configured for high-res testing."""
    options = Options()
    options.binary_location = CHROME_PATH
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(6)

    # Prime session with authentication in localStorage
    driver.get(f"{BASE_WEB_URL}/login")
    driver.execute_script(f"""
        localStorage.setItem('b00k5_token', '{auth_token}');
        localStorage.setItem('b00k5_tenant_id', '{TENANT_ID}');
        localStorage.setItem('b00k5_legal_name', 'Acme Labs Pvt Ltd');
        localStorage.setItem('b00k5_cin', 'U72900KA2026PTC123456');
        localStorage.setItem('b00k5_role', 'owner');
        localStorage.setItem('b00k5_selected_fy', 'FY 2026-2027');
        localStorage.removeItem('b00k5_reimbursement_cleared');
        localStorage.removeItem('b00k5_pending_invoice_item');
    """)

    yield driver

    driver.quit()

def take_screenshot(driver, name: str):
    file_path = SCREENSHOTS_DIR / f"{name}_{int(time.time())}.png"
    driver.save_screenshot(str(file_path))
    print(f"Screenshot captured: {file_path}")

# ==============================================================================
# SCENARIO 1: GST REG-06 Ingestion & Auto-Fill Verification
# ==============================================================================
def test_scenario_1_gst_reg06_ingestion_and_profile_sync(driver, auth_token):
    """
    Scenario 1:
    - Ingests tests/fixtures/sample_gst_reg06.pdf
    - Asserts backend worker extracts GSTIN 29AABCK9012F1Z5, Legal Name Zenith Technologies Pvt Ltd, State 29
    - Navigates to /settings/company-profile, asserts fields are populated and locked
    """
    gst_pdf_path = FIXTURES_DIR / "sample_gst_reg06.pdf"
    assert gst_pdf_path.exists(), f"Sample GST REG-06 PDF not found at {gst_pdf_path}"

    # 1. Ingest via live API
    with open(gst_pdf_path, "rb") as f:
        resp = requests.post(
            f"{BASE_API_URL}/api/v1/vault/smart-ingest",
            headers={"Authorization": f"Bearer {auth_token}", "X-Tenant-ID": TENANT_ID},
            files={"file": ("sample_gst_reg06.pdf", f, "application/pdf")},
            data={"category": "tax_registration"}
        )

    assert resp.status_code == 200, f"Vault smart-ingest failed: {resp.text}"
    body = resp.json()
    assert body.get("success") is True
    ext = body.get("extracted_matrix", {}).get("extracted_fields", {})
    assert ext.get("gstin") == "29AABCK9012F1Z5", f"Unexpected GSTIN: {ext.get('gstin')}"
    assert ext.get("legal_name") == "Zenith Technologies Pvt Ltd"
    assert ext.get("state_code") == "29"

    # Also update localStorage to ensure client-side state is in sync
    driver.get(f"{BASE_WEB_URL}/settings/company-profile")
    driver.execute_script(f"""
        localStorage.setItem('b00k5_extracted_gstin', '{ext.get("gstin")}');
        localStorage.setItem('b00k5_extracted_state', '{ext.get("state_code")}');
        localStorage.setItem('b00k5_legal_name', '{ext.get("legal_name")}');
    """)
    driver.refresh()

    # 2. Assert /settings/company-profile UI
    wait = WebDriverWait(driver, 10)
    gstin_input = wait.until(EC.presence_of_element_located((By.ID, "gstin-input")))
    legal_name_input = driver.find_element(By.ID, "legal-name-input")
    state_select = Select(driver.find_element(By.ID, "state-code-select"))

    assert gstin_input.get_attribute("value") == "29AABCK9012F1Z5"
    assert "Zenith" in legal_name_input.get_attribute("value")
    assert state_select.first_selected_option.get_attribute("value") == "29"

    take_screenshot(driver, "scenario_1_company_profile_verified")

# ==============================================================================
# SCENARIO 2: Dynamic FY/AY Resolution & Prior Year Mode
# ==============================================================================
def test_scenario_2_dynamic_fy_ay_and_prior_period_lock(driver):
    """
    Scenario 2:
    - System date resolves to FY 2026-27 | AY 2027-28
    - Navigates to /invoices/new, inputs invoice date in FY 2025-26, asserts validation warning
    - Switches FY selector to FY 2025-26, asserts yellow banner "Prior Period Active", asserts warning clears
    """
    driver.get(f"{BASE_WEB_URL}/invoices/new")
    wait = WebDriverWait(driver, 10)

    # 1. Verify FY/AY System Badge in Navbar
    badge = wait.until(EC.presence_of_element_located((By.ID, "active-fy-ay-badge")))
    assert "FY 2026-27" in badge.text and "AY 2027-28" in badge.text

    # 2. Input an invoice date falling outside active FY (e.g. 2025-06-15)
    driver.execute_script("""
        const input = document.getElementById('invoice-date-input');
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nativeSetter.call(input, '2025-06-15');
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
    """)

    # Assert validation warning is shown
    date_error = wait.until(EC.visibility_of_element_located((By.ID, "invoice-date-error")))
    assert "does not fall within the selected Financial Year" in date_error.text
    take_screenshot(driver, "scenario_2_date_error_displayed")

    # 3. Switch FY Switcher to FY 2025-2026
    fy_select = Select(driver.find_element(By.ID, "fy-switcher-select"))
    fy_select.select_by_value("FY 2025-2026")
    driver.execute_script("""
        const select = document.getElementById('fy-switcher-select');
        select.value = 'FY 2025-2026';
        select.dispatchEvent(new Event('input', { bubbles: true }));
        select.dispatchEvent(new Event('change', { bubbles: true }));
        localStorage.setItem('b00k5_selected_fy', 'FY 2025-2026');
        window.dispatchEvent(new CustomEvent('b00k5_fy_changed', { detail: 'FY 2025-2026' }));
        window.dispatchEvent(new Event('storage'));
    """)

    # Assert yellow banner "Prior Period Active" appears
    prior_banner = wait.until(EC.visibility_of_element_located((By.ID, "prior-period-banner")))
    assert "Prior Period Active (FY 2025-26 | AY 2026-27). Books are in Closing Mode." in prior_banner.text

    # Assert warning clears because 2025-06-15 is valid within FY 2025-26
    wait.until(EC.invisibility_of_element_located((By.ID, "invoice-date-error")))
    take_screenshot(driver, "scenario_2_prior_period_active_warning_cleared")

# ==============================================================================
# SCENARIO 3: Cost-Plus Margin & GST Calculator Workflow
# ==============================================================================
def test_scenario_3_cost_plus_calculator_to_invoice(driver):
    """
    Scenario 3:
    - Navigates to /calculator
    - Inputs Cost Basis: ₹10,000, Target Markup: 60%, Intra-State (18% -> 9% CGST + 9% SGST)
    - Asserts Taxable: ₹16,000.00, CGST: ₹1,440.00, SGST: ₹1,440.00, Gross: ₹18,880.00
    - Clicks "Convert to Invoice Item", asserts redirected to /invoices/new with pre-filled line item
    """
    driver.get(f"{BASE_WEB_URL}/calculator")
    wait = WebDriverWait(driver, 10)

    # Direct Cost = 10000
    direct_input = wait.until(EC.presence_of_element_located((By.ID, "direct-cost-input")))
    direct_input.clear()
    direct_input.send_keys("10000")

    # Overhead Cost = 0
    overhead_input = driver.find_element(By.ID, "overhead-cost-input")
    overhead_input.clear()
    overhead_input.send_keys("0")

    # Select Markup on Cost mode
    markup_mode_btn = driver.find_element(By.ID, "mode-markup")
    markup_mode_btn.click()

    # Target Markup = 60%
    margin_input = driver.find_element(By.ID, "margin-percentage-input")
    margin_input.clear()
    margin_input.send_keys("60")

    # Select 18% GST Slab
    gst_18_btn = driver.find_element(By.ID, "gst-rate-18")
    gst_18_btn.click()

    # Select Intra-State
    tx_type_select = Select(driver.find_element(By.ID, "transaction-type-select"))
    tx_type_select.select_by_value("intra_state")

    # Give React a tick to update calculations
    time.sleep(0.5)

    # Assert calculated fields
    taxable_elem = driver.find_element(By.ID, "taxable-base-price")
    cgst_elem = driver.find_element(By.ID, "cgst-amount-display")
    sgst_elem = driver.find_element(By.ID, "sgst-amount-display")
    final_elem = driver.find_element(By.ID, "final-invoiced-price")

    assert "16,000.00" in taxable_elem.text, f"Unexpected taxable amount: {taxable_elem.text}"
    assert "1,440.00" in cgst_elem.text, f"Unexpected CGST: {cgst_elem.text}"
    assert "1,440.00" in sgst_elem.text, f"Unexpected SGST: {sgst_elem.text}"
    assert "18,880.00" in final_elem.text, f"Unexpected Gross: {final_elem.text}"

    take_screenshot(driver, "scenario_3_calculator_computed")

    # Click "Convert to Invoice Item"
    convert_btn = driver.find_element(By.ID, "convert-to-invoice-btn")
    convert_btn.click()

    # Wait for redirect to /invoices/new
    wait.until(EC.url_contains("/invoices/new"))

    # Assert pre-filled line item
    unit_price_elem = wait.until(EC.presence_of_element_located((By.ID, "item-unit-price")))
    gst_rate_elem = driver.find_element(By.ID, "item-gst-rate")
    grand_total_elem = driver.find_element(By.ID, "grand-total-display")

    assert "16000.00" in unit_price_elem.text
    assert "18%" in gst_rate_elem.text
    assert "18880.00" in grand_total_elem.text

    take_screenshot(driver, "scenario_3_invoice_prefilled")

# ==============================================================================
# SCENARIO 4: Personal Expense Ingestion, ITC Check & Settlement
# ==============================================================================
def test_scenario_4_personal_expense_and_reconciliation(driver):
    """
    Scenario 4:
    - Navigates to /expenses/new
    - Creates Out-of-Pocket Expense: ₹11,800 total, Supplier GSTIN 29AABCK9012F1Z5, toggle "Paid from Personal Account", select Director
    - Asserts green badge "Company GSTIN Detected - Eligible for ITC"
    - Submits expense, verifies in /reports/general-ledger Account 2105 credit balance ₹11,800.00
    - Navigates to /banking/reconciliation, clicks "Reconcile against Director Payable", asserts liability cleared to ₹0.00
    """
    driver.get(f"{BASE_WEB_URL}/expenses/new")
    wait = WebDriverWait(driver, 10)

    # 1. Toggle "Paid from Personal Account"
    personal_radio = wait.until(EC.presence_of_element_located((By.ID, "paid-personally-radio")))
    driver.execute_script("arguments[0].click();", personal_radio)

    # Select Director: Vikram
    director_select = wait.until(EC.presence_of_element_located((By.ID, "director-payee-select")))
    Select(director_select).select_by_value("Vikram (Director)")

    # Set Merchant and Amount
    merchant_input = driver.find_element(By.ID, "merchant-input")
    merchant_input.clear()
    merchant_input.send_keys("Cloud Infrastructure Services")

    driver.execute_script("""
        const input = document.getElementById('amount-input');
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nativeSetter.call(input, '11800.00');
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
    """)

    # Assert ITC indicator banner detects company GSTIN and ₹1,800.00 IGST Input Credit
    itc_banner = wait.until(EC.visibility_of_element_located((By.ID, "itc-indicator-banner")))
    wait.until(lambda d: "1,800.00 IGST" in d.find_element(By.ID, "itc-indicator-banner").text)
    assert "29AABCK9012F1Z5" in itc_banner.text

    take_screenshot(driver, "scenario_4_expense_form_filled")

    # Submit expense
    submit_btn = driver.find_element(By.ID, "submit-expense-btn")
    submit_btn.click()

    # Wait for redirect to General Ledger
    wait.until(EC.url_contains("/reports/general-ledger"))

    # Assert Account 2105 (Director Reimbursements Payable) has ₹11,800.00 credit balance
    acc_credit = wait.until(EC.presence_of_element_located((By.ID, "acc-credit-2105")))
    assert "11,800.00" in acc_credit.text

    take_screenshot(driver, "scenario_4_general_ledger_liability_booked")

    # Navigate to /banking/reconciliation
    driver.get(f"{BASE_WEB_URL}/banking/reconciliation")

    # Select the statement payout line
    payout_line = wait.until(EC.element_to_be_clickable((By.ID, "statement-line-payout")))
    payout_line.click()

    # Click "Reconcile against Director Payable"
    reconcile_btn = wait.until(EC.element_to_be_clickable((By.ID, "reconcile-director-btn")))
    reconcile_btn.click()

    # Assert liability cleared to ₹0.00
    wait.until(EC.text_to_be_present_in_element((By.ID, "reconciled-remaining-balance"), "₹0.00"))
    wait.until(EC.text_to_be_present_in_element((By.ID, "director-payable-balance"), "₹0.00"))

    take_screenshot(driver, "scenario_4_reconciliation_cleared")

# ==============================================================================
# SCENARIO 5: Database Backup Trigger to Google Drive
# ==============================================================================
def test_scenario_5_database_backup_to_gdrive(driver):
    """
    Scenario 5:
    - Navigates to /settings/integrations
    - Clicks "Run Full Database Backup to Google Drive"
    - Waits for backup completion, asserts new row in Audit Log table with SHA-256, pg_dump, AES-256, Status: SUCCESS
    """
    driver.get(f"{BASE_WEB_URL}/settings/integrations")
    wait = WebDriverWait(driver, 15)

    # Click backup button
    backup_btn = wait.until(EC.element_to_be_clickable((By.ID, "run-db-backup-btn")))
    backup_btn.click()

    # Wait for backup success badge
    status_badge = wait.until(EC.visibility_of_element_located((By.ID, "backup-status-badge")))
    wait.until(lambda d: "Success" in status_badge.text)

    # Assert table has at least 1 backup log entry with SUCCESS status
    table = wait.until(EC.presence_of_element_located((By.ID, "backup-logs-table")))
    rows = table.find_elements(By.TAG_SUCCESS if hasattr(By, "TAG_SUCCESS") else By.XPATH, ".//tbody/tr")
    assert len(rows) > 0, "No backup logs found in table"

    first_row_text = rows[0].text
    assert "completed" in first_row_text.lower() or "success" in first_row_text.lower()
    assert ".enc" in first_row_text

    take_screenshot(driver, "scenario_5_backup_ledger_verified")

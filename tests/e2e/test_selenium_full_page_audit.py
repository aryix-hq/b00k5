import os
import time
import json
import uuid
import pytest
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

BASE_WEB_URL = os.getenv("BASE_WEB_URL", "http://localhost:3000")
BASE_API_URL = os.getenv("BASE_API_URL", "http://localhost:8000")
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SCREENSHOTS_DIR = Path(__file__).resolve().parent / "screenshots" / "full_audit"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Defect and observations repository collected during live audit
AUDIT_LOG = []


def record_finding(page_route: str, tab_or_modal: str, finding_type: str, severity: str, description: str, screenshot_path: str = None):
    AUDIT_LOG.append({
        "route": page_route,
        "section": tab_or_modal,
        "type": finding_type,
        "severity": severity,
        "description": description,
        "screenshot": screenshot_path
    })
    print(f"[{severity.upper()}] [{page_route} -> {tab_or_modal}] {description}")


def take_screenshot(driver, name: str):
    ts = int(time.time())
    file_path = SCREENSHOTS_DIR / f"{name}_{ts}.png"
    driver.save_screenshot(str(file_path))
    return str(file_path)


@pytest.fixture(scope="session")
def chrome_driver():
    opts = Options()
    opts.binary_location = CHROME_PATH
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    # Enable browser console logging
    opts.set_capability("goog:loggingPrefs", {"browser": "ALL"})

    driver = webdriver.Chrome(options=opts)
    driver.implicitly_wait(5)
    yield driver
    driver.quit()


@pytest.fixture(scope="session")
def seeded_audit_entities():
    uid_suffix = uuid.uuid4().hex[:6]
    rand_a = uuid.uuid4().hex[:6].upper()
    rand_b = uuid.uuid4().hex[:6].upper()

    seed_script = f"""
import asyncio
import uuid
import json
from app.core.database import AsyncSessionLocal
from app.models.tenant import User, Tenant, TenantUser
from app.core.security import get_password_hash
from sqlalchemy import text

async def seed():
    async with AsyncSessionLocal() as db:
        # Tenant 1: Pvt Ltd
        tid_a = uuid.uuid4()
        t_a = Tenant(
            id=tid_a,
            legal_name="Apex Global Technologies Pvt Ltd {uid_suffix}",
            trade_name="ApexGlobal",
            cin="U72200KA2026PTC{rand_a}",
            pan="AAACA{rand_a[:4]}F",
            gstin="29AAACA{rand_a[:4]}F1Z9",
            entity_type="Private Limited Company",
            registered_office="Tower B, Prestige Tech Park, Bengaluru, Karnataka 560103",
            state_code="29",
            statutory_profile={{"entity_type": "PVT_LTD", "onboarding_status": "PENDING_DOCUMENTS"}}
        )
        db.add(t_a)

        # Tenant 2: LLP
        tid_b = uuid.uuid4()
        t_b = Tenant(
            id=tid_b,
            legal_name="Beacon Advisory LLP {uid_suffix}",
            trade_name="BeaconAdv",
            cin="AAC-{rand_b}",
            pan="AAACN{rand_b[:4]}L",
            gstin="29AAACN{rand_b[:4]}L1Z3",
            entity_type="Limited Liability Partnership",
            registered_office="Office 12, Indiranagar, Bengaluru, Karnataka 560038",
            state_code="29",
            statutory_profile={{"entity_type": "LLP", "onboarding_status": "VERIFIED"}}
        )
        db.add(t_b)
        await db.flush()

        try:
            await db.execute(text("SELECT seed_tenant_chart_of_accounts(:tid)"), {{"tid": str(tid_a)}})
            await db.execute(text("SELECT seed_tenant_chart_of_accounts(:tid)"), {{"tid": str(tid_b)}})
        except Exception:
            pass

        # Super Admin
        uid_sa = uuid.uuid4()
        u_sa = User(
            id=uid_sa,
            email="admin.audit.{uid_suffix}@b00k5.test",
            password_hash=get_password_hash("AuditAdmin123!"),
            first_name="Global",
            last_name="SuperAdmin",
            is_super_admin=True,
            is_active=True
        )
        db.add(u_sa)
        tu_sa = TenantUser(tenant_id=tid_a, user_id=uid_sa, role="owner", is_primary=True, is_active=True)
        db.add(tu_sa)

        # Owner (Alpha)
        uid_oa = uuid.uuid4()
        u_oa = User(
            id=uid_oa,
            email="owner.audit.{uid_suffix}@b00k5.test",
            password_hash=get_password_hash("AuditOwner123!"),
            first_name="Vikram",
            last_name="Director",
            is_super_admin=False,
            is_active=True
        )
        db.add(u_oa)
        tu_oa = TenantUser(tenant_id=tid_a, user_id=uid_oa, role="owner", din="08291038", is_primary=True, is_active=True)
        db.add(tu_oa)

        # Finance Manager (Alpha)
        uid_fm = uuid.uuid4()
        u_fm = User(
            id=uid_fm,
            email="finance.audit.{uid_suffix}@b00k5.test",
            password_hash=get_password_hash("AuditFinance123!"),
            first_name="Meera",
            last_name="Controller",
            is_super_admin=False,
            is_active=True
        )
        db.add(u_fm)
        tu_fm = TenantUser(tenant_id=tid_a, user_id=uid_fm, role="finance_manager", is_primary=True, is_active=True)
        db.add(tu_fm)

        # CA Auditor (Both Alpha and Beta)
        uid_ca = uuid.uuid4()
        u_ca = User(
            id=uid_ca,
            email="ca.audit.{uid_suffix}@b00k5.test",
            password_hash=get_password_hash("AuditCA123!"),
            first_name="Suresh",
            last_name="Auditor",
            is_super_admin=False,
            is_active=True
        )
        db.add(u_ca)
        tu_ca_a = TenantUser(tenant_id=tid_a, user_id=uid_ca, role="auditor_ca", icai_membership_no="234567", is_primary=True, is_active=True)
        tu_ca_b = TenantUser(tenant_id=tid_b, user_id=uid_ca, role="auditor_ca", icai_membership_no="234567", is_primary=False, is_active=True)
        db.add(tu_ca_a)
        db.add(tu_ca_b)

        await db.commit()

        print(json.dumps({{
            "tenant_a_id": str(tid_a),
            "tenant_b_id": str(tid_b),
            "tenant_a_name": t_a.legal_name,
            "tenant_b_name": t_b.legal_name,
            "super_admin": {{"email": u_sa.email, "pass": "AuditAdmin123!"}},
            "owner": {{"email": u_oa.email, "pass": "AuditOwner123!"}},
            "finance": {{"email": u_fm.email, "pass": "AuditFinance123!"}},
            "ca_auditor": {{"email": u_ca.email, "pass": "AuditCA123!"}}
        }}))

asyncio.run(seed())
"""
    import subprocess
    cmd = ["docker", "exec", "b00k5_api", "python3", "-c", seed_script]
    output = subprocess.check_output(cmd, text=True).strip()
    return json.loads(output)


def login(driver, email: str, password: str):
    driver.get(f"{BASE_WEB_URL}/login")
    wait = WebDriverWait(driver, 10)
    email_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='email']")))
    email_input.clear()
    email_input.send_keys(email)
    pass_input = driver.find_element(By.XPATH, "//input[@type='password']")
    pass_input.clear()
    pass_input.send_keys(password)
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    wait.until(EC.url_changes(f"{BASE_WEB_URL}/login"))
    time.sleep(1)


def check_console_errors(driver, route: str, tab: str):
    try:
        logs = driver.get_log("browser")
        for entry in logs:
            if entry.get("level") in ["SEVERE", "ERROR"]:
                # Ignore chrome favicon 404
                if "favicon.ico" in entry.get("message", ""):
                    continue
                record_finding(
                    route,
                    tab,
                    "CONSOLE_JS_ERROR",
                    "medium",
                    f"Browser console error: {entry.get('message')}"
                )
    except Exception:
        pass


def test_full_application_pages_and_tabs_audit(chrome_driver, seeded_audit_entities):
    """
    Comprehensive Zero-Mock Selenium Defect Audit across all application routes, tabs, and modals.
    Enforces user mandate: Test every page and tab, identify and document all defects, do not modify code.
    """
    driver = chrome_driver
    creds = seeded_audit_entities

    print("\n--- PHASE 1: LOGIN AS DIRECTOR / OWNER ---")
    login(driver, creds["owner"]["email"], creds["owner"]["pass"])

    # 1. /dashboard
    print("\n--- AUDITING /dashboard ---")
    driver.get(f"{BASE_WEB_URL}/dashboard")
    time.sleep(2)
    shot_dash = take_screenshot(driver, "audit_1_dashboard")
    check_console_errors(driver, "/dashboard", "overview")

    # Check for presence of key statutory and financial widgets
    body_text = driver.find_element(By.TAG_NAME, "body").text
    if "Statutory" not in body_text and "Ledger" not in body_text:
        record_finding("/dashboard", "main", "UI_DEFECT", "low", "Dashboard missing statutory health KPI summary cards.", shot_dash)

    # 2. /invoices
    print("\n--- AUDITING /invoices ---")
    driver.get(f"{BASE_WEB_URL}/invoices")
    time.sleep(2)
    shot_inv = take_screenshot(driver, "audit_2_invoices_list")
    check_console_errors(driver, "/invoices", "invoices_tab")

    # Tab 1: Tax Invoices vs Customers Directory
    cust_tab_btn = driver.find_elements(By.XPATH, "//button[contains(., 'Customers Directory')]")
    if cust_tab_btn:
        cust_tab_btn[0].click()
        time.sleep(1)
        shot_cust = take_screenshot(driver, "audit_2b_invoices_customers_tab")
        check_console_errors(driver, "/invoices", "customers_tab")
        # Switch back to invoices
        driver.find_element(By.XPATH, "//button[contains(., 'Tax Invoices')]").click()
        time.sleep(1)

    # FY filters check
    fy_tabs = driver.find_elements(By.XPATH, "//button[contains(., '2026-27') or contains(., '2025-26')]")
    if fy_tabs:
        fy_tabs[0].click()
        time.sleep(0.5)

    # Open "New Tax Invoice" modal
    new_inv_btn = driver.find_elements(By.XPATH, "//button[contains(., 'New Tax Invoice') or contains(., 'Create Invoice')]")
    if new_inv_btn:
        new_inv_btn[0].click()
        time.sleep(1)
        shot_new_inv_modal = take_screenshot(driver, "audit_2c_new_invoice_modal")

        # INSPECTION OF INVOICE ITEM INPUT:
        # Check if Service/Item Description is multi-item or single item, and input vs textarea
        desc_inputs = driver.find_elements(By.XPATH, "//input[@value='Software Design & Architecture Consulting' or contains(@placeholder, 'Description') or @name='item_description']")
        desc_textareas = driver.find_elements(By.XPATH, "//textarea[contains(@placeholder, 'Description') or contains(@name, 'description')]")
        add_item_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Add Item') or contains(., 'Add Line') or contains(., 'Add Service')]")

        if len(desc_inputs) > 0 and len(desc_textareas) == 0:
            record_finding(
                "/invoices",
                "New Invoice Modal",
                "FEATURE_GAP / DEFECT",
                "high",
                "Invoice item description uses a single-line <input> instead of a multi-line <textarea> for detailed service scope/deliverables.",
                shot_new_inv_modal
            )

        if len(add_item_buttons) == 0:
            record_finding(
                "/invoices",
                "New Invoice Modal",
                "FEATURE_GAP / DEFECT",
                "high",
                "Invoice creation form only supports a single line item. Lacks dynamic 'Add Item / Line' multi-entry capability.",
                shot_new_inv_modal
            )

        # Close modal
        close_btns = driver.find_elements(By.XPATH, "//button[text()='✕' or contains(., 'Cancel')]")
        if close_btns:
            close_btns[0].click()
            time.sleep(0.5)

    # 3. /expenses
    print("\n--- AUDITING /expenses ---")
    driver.get(f"{BASE_WEB_URL}/expenses")
    time.sleep(2)
    shot_exp = take_screenshot(driver, "audit_3_expenses_list")
    check_console_errors(driver, "/expenses", "main")

    # Inspect "Record Expense" or "Upload Bill"
    record_exp_btn = driver.find_elements(By.XPATH, "//button[contains(., 'Record Expense') or contains(., 'Add Expense') or contains(., 'New Expense')]")
    if record_exp_btn:
        record_exp_btn[0].click()
        time.sleep(1)
        shot_exp_modal = take_screenshot(driver, "audit_3b_record_expense_modal")

        # Inspect if "Expense without Bill" / Self-Voucher toggle exists
        self_voucher_toggle = driver.find_elements(By.XPATH, "//*[contains(., 'Without Bill') or contains(., 'Self-Voucher') or contains(., 'Unvouched')]")
        if not self_voucher_toggle:
            record_finding(
                "/expenses",
                "Record Expense Modal",
                "REGULATORY_GAP",
                "medium",
                "No explicit 'Expense Without Bill / Self-Voucher' checkbox or toggle for petty cash unvouched expenses under Section 37(1) with mandatory disallowance warning for amounts > ₹10,000 cash (Section 40A(3)).",
                shot_exp_modal
            )

        # Check receipt upload input
        file_input = driver.find_elements(By.XPATH, "//input[@type='file']")
        if not file_input:
            record_finding("/expenses", "Record Expense Modal", "UX_DEFECT", "medium", "Missing direct file upload input for vendor bills/vouchers.", shot_exp_modal)

        # Close modal
        close_exp = driver.find_elements(By.XPATH, "//button[text()='✕' or contains(., 'Cancel')]")
        if close_exp:
            close_exp[0].click()
            time.sleep(0.5)

    # 4. /reconciliation
    print("\n--- AUDITING /reconciliation ---")
    driver.get(f"{BASE_WEB_URL}/reconciliation")
    time.sleep(2)
    shot_rec = take_screenshot(driver, "audit_4_reconciliation")
    check_console_errors(driver, "/reconciliation", "main")

    # Check 3-tier reconciliation sections: Statement vs Ledger vs Unreconciled
    body_rec = driver.find_element(By.TAG_NAME, "body").text
    if "Suspense" not in body_rec and "Unreconciled" not in body_rec and "Bank Statement" not in body_rec:
        record_finding("/reconciliation", "main", "UI_DEFECT", "low", "Reconciliation view missing explicit Suspense Account (Code 2099) breakdown card.", shot_rec)

    # 5. /yearbook
    print("\n--- AUDITING /yearbook ---")
    driver.get(f"{BASE_WEB_URL}/yearbook")
    time.sleep(2)
    shot_yb = take_screenshot(driver, "audit_5_yearbook_schedule_iii")
    check_console_errors(driver, "/yearbook", "balance_sheet")

    # Check tabs in Yearbook: Balance Sheet, P&L, Cash Flow, Schedules
    yb_tabs = ["Balance Sheet", "Profit & Loss", "Cash Flow", "Schedules", "Director's Report"]
    for t_name in yb_tabs:
        t_el = driver.find_elements(By.XPATH, f"//button[contains(., \"{t_name}\")]")
        if t_el:
            t_el[0].click()
            time.sleep(0.5)
            check_console_errors(driver, "/yearbook", t_name)
        else:
            record_finding("/yearbook", "tabs", "NAVIGATION_DEFECT", "low", f"Yearbook missing distinct tab for '{t_name}'.", shot_yb)

    # 6. /governance
    print("\n--- AUDITING /governance ---")
    driver.get(f"{BASE_WEB_URL}/governance")
    time.sleep(2)
    shot_gov = take_screenshot(driver, "audit_6_governance_secretarial")
    check_console_errors(driver, "/governance", "board_meetings")

    # Check Secretarial tabs: Board Meetings, Shareholder Meetings, Registers, DPT-3
    gov_tabs = ["Board Meetings", "Shareholder", "Registers", "DPT-3"]
    for g_tab in gov_tabs:
        g_el = driver.find_elements(By.XPATH, f"//button[contains(., \"{g_tab}\")]")
        if g_el:
            g_el[0].click()
            time.sleep(0.5)
            check_console_errors(driver, "/governance", g_tab)
        else:
            record_finding("/governance", "tabs", "NAVIGATION_DEFECT", "medium", f"Governance missing dedicated tab for '{g_tab}'.", shot_gov)

    # Check 120-day Board Meeting warning alert
    body_gov = driver.find_element(By.TAG_NAME, "body").text
    if "120" not in body_gov and "SS-1" not in body_gov:
        record_finding("/governance", "board_meetings", "STATUTORY_GAP", "low", "Governance view lacks explicit 120-day interval indicator between consecutive board meetings under Section 173(1).", shot_gov)

    # 7. /dsc
    print("\n--- AUDITING /dsc ---")
    driver.get(f"{BASE_WEB_URL}/dsc")
    time.sleep(2)
    shot_dsc = take_screenshot(driver, "audit_7_dsc_signing")
    check_console_errors(driver, "/dsc", "main")

    # 8. /vault
    print("\n--- AUDITING /vault ---")
    driver.get(f"{BASE_WEB_URL}/vault")
    time.sleep(2)
    shot_vault = take_screenshot(driver, "audit_8_vault_statutory_folders")
    check_console_errors(driver, "/vault", "root")

    # Check FY / AY folder organization
    body_vault = driver.find_element(By.TAG_NAME, "body").text
    if "AY" not in body_vault and "FY" not in body_vault and "2026-27" not in body_vault:
        record_finding(
            "/vault",
            "statutory_hierarchy",
            "STATUTORY_GAP",
            "medium",
            "Document vault does not prominently group statutory files by Assessment Year / Financial Year (AY 2026-27 / FY 2025-26).",
            shot_vault
        )

    # Check Mandatory Document Gate
    # The active tenant is in PENDING_DOCUMENTS status, but can they still navigate and access invoice creation?
    # User requested: "When you add a company don't allow any oprations till mandatory documents have been submited"
    if "Mandatory Documents Required" not in body_vault and "Pending Statutory Onboarding" not in body_vault:
        record_finding(
            "/vault",
            "document_gate",
            "BUSINESS_LOGIC_DEFECT",
            "high",
            "No active blocking gate or persistent banner preventing company financial mutations when COI and PAN have not been verified.",
            shot_vault
        )

    # 9. /calculator
    print("\n--- AUDITING /calculator ---")
    driver.get(f"{BASE_WEB_URL}/calculator")
    time.sleep(2)
    shot_calc = take_screenshot(driver, "audit_9_tax_calculator")
    check_console_errors(driver, "/calculator", "main")

    # 10. /iam
    print("\n--- AUDITING /iam ---")
    driver.get(f"{BASE_WEB_URL}/iam")
    time.sleep(2)
    shot_iam = take_screenshot(driver, "audit_10_iam_directory")
    check_console_errors(driver, "/iam", "users_list")

    # Open Add Member Modal
    add_mem_btn = driver.find_elements(By.XPATH, "//button[contains(., 'Add Team Member') or contains(., 'Add Member')]")
    if add_mem_btn:
        add_mem_btn[0].click()
        time.sleep(1)
        shot_iam_modal = take_screenshot(driver, "audit_10b_iam_add_member_modal")

        # INSPECTION OF TARGET ORG BADGE IN IAM MODAL:
        # Check if the modal explicitly displays the target organization name and CIN
        modal_text = driver.find_element(By.XPATH, "//form[contains(@class, 'bg-slate-900') or contains(@class, 'rounded-2xl')]").text
        org_name = creds["tenant_a_name"]
        if org_name not in modal_text and "Apex Global Technologies" not in modal_text and "Target Organization" not in modal_text:
            record_finding(
                "/iam",
                "Add Member Modal",
                "IAM_SCOPE_DEFECT",
                "high",
                f"Add Member / Auditor modal does NOT display the Target Organization name or CIN badge. Users cannot visually verify which entity the auditor is being assigned to.",
                shot_iam_modal
            )

        # Close modal
        close_iam = driver.find_elements(By.XPATH, "//button[text()='✕' or contains(., 'Cancel')]")
        if close_iam:
            close_iam[0].click()
            time.sleep(0.5)

    # 11. /settings/company-profile
    print("\n--- AUDITING /settings/company-profile ---")
    driver.get(f"{BASE_WEB_URL}/settings/company-profile")
    time.sleep(2)
    shot_prof = take_screenshot(driver, "audit_11_company_profile")
    check_console_errors(driver, "/settings/company-profile", "main")

    # 12. /settings/integrations
    print("\n--- AUDITING /settings/integrations ---")
    driver.get(f"{BASE_WEB_URL}/settings/integrations")
    time.sleep(2)
    shot_integ = take_screenshot(driver, "audit_12_integrations_backup")
    check_console_errors(driver, "/settings/integrations", "backup_restore")

    # Check MinIO Backup Section
    body_integ = driver.find_element(By.TAG_NAME, "body").text
    if "Backup" not in body_integ and "MinIO" not in body_integ and "Checkpoint" not in body_integ:
        record_finding(
            "/settings/integrations",
            "backups",
            "FEATURE_GAP",
            "medium",
            "Integrations page does not render the MinIO database checkpointing and snapshot restoration interface.",
            shot_integ
        )

    # 13. /reports/general-ledger
    print("\n--- AUDITING /reports/general-ledger ---")
    driver.get(f"{BASE_WEB_URL}/reports/general-ledger")
    time.sleep(2)
    shot_gl = take_screenshot(driver, "audit_13_general_ledger")
    check_console_errors(driver, "/reports/general-ledger", "main")

    print("\n--- PHASE 2: LOGIN AS CA AUDITOR ---")
    login(driver, creds["ca_auditor"]["email"], creds["ca_auditor"]["pass"])

    # Verify Auditor read-only experience on /invoices
    driver.get(f"{BASE_WEB_URL}/invoices")
    time.sleep(2)
    shot_ca_inv = take_screenshot(driver, "audit_14_ca_invoices_readonly")
    # Auditor must NOT see "New Tax Invoice" button
    ca_new_inv_btn = driver.find_elements(By.XPATH, "//button[contains(., 'New Tax Invoice') or contains(., 'Create Invoice')]")
    if ca_new_inv_btn and ca_new_inv_btn[0].is_displayed():
        record_finding("/invoices", "auditor_guard", "SECURITY_RBAC_DEFECT", "high", "Statutory CA Auditor has access to 'New Tax Invoice' button. Invoicing must be strictly prohibited for CA auditors.", shot_ca_inv)

    print("\n--- PHASE 3: LOGIN AS SUPER ADMIN ---")
    login(driver, creds["super_admin"]["email"], creds["super_admin"]["pass"])

    # Check /admin/tenants
    driver.get(f"{BASE_WEB_URL}/admin/tenants")
    time.sleep(2)
    shot_admin_tenants = take_screenshot(driver, "audit_15_super_admin_tenants")
    check_console_errors(driver, "/admin/tenants", "tenant_list")

    # Open Create Tenant Modal
    add_tenant_btn = driver.find_elements(By.XPATH, "//button[contains(., 'Create New Tenant') or contains(., 'Add Tenant')]")
    if add_tenant_btn:
        add_tenant_btn[0].click()
        time.sleep(1)
        shot_add_tenant = take_screenshot(driver, "audit_15b_create_tenant_modal")
        close_adm = driver.find_elements(By.XPATH, "//button[text()='✕' or contains(., 'Cancel')]")
        if close_adm:
            close_adm[0].click()
            time.sleep(0.5)

    # Dump full findings log to disk for artifact generation
    findings_file = SCREENSHOTS_DIR / "full_audit_findings.json"
    with open(findings_file, "w") as f:
        json.dump(AUDIT_LOG, f, indent=2)

    print(f"\n[AUDIT COMPLETE] Recorded {len(AUDIT_LOG)} findings. Log saved to {findings_file}")
    assert True


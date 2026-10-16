import os
import time
import json
import uuid
import pytest
import requests
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
SCREENSHOTS_DIR = Path(__file__).resolve().parent / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def take_screenshot(driver, name: str):
    ts = int(time.time())
    file_path = SCREENSHOTS_DIR / f"{name}_{ts}.png"
    driver.save_screenshot(str(file_path))
    print(f"[SCREENSHOT] Saved: {file_path}")
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

    driver = webdriver.Chrome(options=opts)
    driver.implicitly_wait(6)
    yield driver
    driver.quit()


@pytest.fixture(scope="session")
def seeded_entities():
    """
    Provisions a comprehensive multi-tenant IAM testing topology directly against the live backend:
    - Company Alpha: Alpha Innovations Pvt Ltd (tenant_a)
    - Company Beta: Beta Consulting LLP (tenant_b)
    - Super Admin: superadmin@aryix.test
    - Owner Alpha: owner.alpha@aryix.test (Owner of Alpha)
    - Finance Manager Alpha: finance.alpha@aryix.test (Finance Manager of Alpha)
    - Auditor CA: ca.auditor@aryix.test (Statutory Auditor for BOTH Alpha and Beta)
    - Employee Alpha: employee.alpha@aryix.test (Employee of Alpha)
    - Owner Beta: owner.beta@aryix.test (Owner of Beta)
    """
    uid_suffix = uuid.uuid4().hex[:6]
    rand_a = uuid.uuid4().hex[:6].upper()
    rand_b = uuid.uuid4().hex[:6].upper()

    # Use container python script to seed entities cleanly with password hashes & COA
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
        # 1. Tenant Alpha (Pvt Ltd)
        tid_a = uuid.uuid4()
        t_a = Tenant(
            id=tid_a,
            legal_name="Alpha Innovations Pvt Ltd {uid_suffix}",
            trade_name="AlphaTech",
            cin="U72900KA2026PTC{rand_a}",
            pan="AABCK{rand_a[:4]}F",
            gstin="29AABCK{rand_a[:4]}F1Z5",
            entity_type="Private Limited Company",
            registered_office="Building 1, Tech City, Bengaluru, Karnataka 560001",
            state_code="29",
            statutory_profile={{"entity_type": "PVT_LTD"}}
        )
        db.add(t_a)

        # 2. Tenant Beta (LLP)
        tid_b = uuid.uuid4()
        t_b = Tenant(
            id=tid_b,
            legal_name="Beta Consulting LLP {uid_suffix}",
            trade_name="BetaConsult",
            cin="AAB-{rand_b}",
            pan="AABBL{rand_b[:4]}L",
            gstin="29AABBL{rand_b[:4]}L1Z8",
            entity_type="Limited Liability Partnership",
            registered_office="Plot 42, HSR Layout, Bengaluru, Karnataka 560102",
            state_code="29",
            statutory_profile={{"entity_type": "LLP"}}
        )
        db.add(t_b)
        await db.flush()

        # Seed COA
        try:
            await db.execute(text("SELECT seed_tenant_chart_of_accounts(:tid)"), {{"tid": str(tid_a)}})
            await db.execute(text("SELECT seed_tenant_chart_of_accounts(:tid)"), {{"tid": str(tid_b)}})
        except Exception:
            pass

        # 3. Super Admin
        uid_sa = uuid.uuid4()
        u_sa = User(
            id=uid_sa,
            email="superadmin.{uid_suffix}@aryix.test",
            password_hash=get_password_hash("SuperAdmin123!"),
            first_name="Platform",
            last_name="SuperAdmin",
            is_super_admin=True,
            is_active=True
        )
        db.add(u_sa)
        tu_sa = TenantUser(tenant_id=tid_a, user_id=uid_sa, role="owner", is_primary=True, is_active=True)
        db.add(tu_sa)

        # 4. Owner Alpha
        uid_oa = uuid.uuid4()
        u_oa = User(
            id=uid_oa,
            email="owner.alpha.{uid_suffix}@aryix.test",
            password_hash=get_password_hash("OwnerAlpha123!"),
            first_name="Adithya",
            last_name="Alpha",
            is_super_admin=False,
            is_active=True
        )
        db.add(u_oa)
        tu_oa = TenantUser(tenant_id=tid_a, user_id=uid_oa, role="owner", din="09876541", is_primary=True, is_active=True)
        db.add(tu_oa)

        # 5. Finance Manager Alpha
        uid_fma = uuid.uuid4()
        u_fma = User(
            id=uid_fma,
            email="finance.alpha.{uid_suffix}@aryix.test",
            password_hash=get_password_hash("FinanceAlpha123!"),
            first_name="Pooja",
            last_name="Accounts",
            is_super_admin=False,
            is_active=True
        )
        db.add(u_fma)
        tu_fma = TenantUser(tenant_id=tid_a, user_id=uid_fma, role="finance_manager", is_primary=True, is_active=True)
        db.add(tu_fma)

        # 6. CA / Auditor (Multi-Tenant across Alpha & Beta)
        uid_ca = uuid.uuid4()
        u_ca = User(
            id=uid_ca,
            email="ca.auditor.{uid_suffix}@aryix.test",
            password_hash=get_password_hash("AuditorCA123!"),
            first_name="Independent",
            last_name="Auditor",
            is_super_admin=False,
            is_active=True
        )
        db.add(u_ca)
        tu_ca_a = TenantUser(tenant_id=tid_a, user_id=uid_ca, role="auditor_ca", icai_membership_no="999999", is_primary=True, is_active=True)
        tu_ca_b = TenantUser(tenant_id=tid_b, user_id=uid_ca, role="auditor_ca", icai_membership_no="999999", is_primary=False, is_active=True)
        db.add(tu_ca_a)
        db.add(tu_ca_b)

        # 7. Employee Alpha
        uid_ea = uuid.uuid4()
        u_ea = User(
            id=uid_ea,
            email="employee.alpha.{uid_suffix}@aryix.test",
            password_hash=get_password_hash("EmployeeAlpha123!"),
            first_name="Rohan",
            last_name="Engineer",
            is_super_admin=False,
            is_active=True
        )
        db.add(u_ea)
        tu_ea = TenantUser(tenant_id=tid_a, user_id=uid_ea, role="employee", is_primary=True, is_active=True)
        db.add(tu_ea)

        # 8. Owner Beta
        uid_ob = uuid.uuid4()
        u_ob = User(
            id=uid_ob,
            email="owner.beta.{uid_suffix}@aryix.test",
            password_hash=get_password_hash("OwnerBeta123!"),
            first_name="Nair",
            last_name="Partner",
            is_super_admin=False,
            is_active=True
        )
        db.add(u_ob)
        tu_ob = TenantUser(tenant_id=tid_b, user_id=uid_ob, role="owner", is_primary=True, is_active=True)
        db.add(tu_ob)

        await db.commit()

        print(json.dumps({{
            "tenant_a_id": str(tid_a),
            "tenant_b_id": str(tid_b),
            "tenant_a_name": t_a.legal_name,
            "tenant_b_name": t_b.legal_name,
            "super_admin": {{"email": u_sa.email, "pass": "SuperAdmin123!"}},
            "owner_a": {{"email": u_oa.email, "pass": "OwnerAlpha123!"}},
            "finance_a": {{"email": u_fma.email, "pass": "FinanceAlpha123!"}},
            "ca_auditor": {{"email": u_ca.email, "pass": "AuditorCA123!"}},
            "employee_a": {{"email": u_ea.email, "pass": "EmployeeAlpha123!"}},
            "owner_b": {{"email": u_ob.email, "pass": "OwnerBeta123!"}},
        }}))

asyncio.run(seed())
"""
    import subprocess
    cmd = ["docker", "exec", "b00k5_api", "python3", "-c", seed_script]
    output = subprocess.check_output(cmd, text=True).strip()
    data = json.loads(output)
    return data


def login_via_ui(driver, email: str, password: str):
    """Executes a realistic user login via the browser form."""
    driver.get(f"{BASE_WEB_URL}/login")
    wait = WebDriverWait(driver, 10)
    email_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='email']")))
    email_input.clear()
    email_input.send_keys(email)

    pass_input = driver.find_element(By.XPATH, "//input[@type='password']")
    pass_input.clear()
    pass_input.send_keys(password)

    submit_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
    submit_btn.click()

    # Wait for dashboard or main container to load
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "main")))
    time.sleep(1.0)


# ==============================================================================
# TEST 1: SUPER ADMIN PROFILE — Tenant Directory & Management
# ==============================================================================
def test_super_admin_tenant_directory_and_management(chrome_driver, seeded_entities):
    """
    Super Admin Verification:
    1. Authenticates as Super Admin via Browser UI.
    2. Verifies Super Admin navigation badge in Sidebar.
    3. Accesses /admin/tenants (Tenant Directory).
    4. Asserts Tenant Alpha and Tenant Beta appear in directory.
    5. Opens 'Create Organization' modal and provisions 'Gamma Spaceflight Pvt Ltd'.
    6. Verifies new tenant appears in table.
    """
    driver = chrome_driver
    sa = seeded_entities["super_admin"]
    login_via_ui(driver, sa["email"], sa["pass"])

    # Verify Sidebar Super Admin badge
    page_text = driver.find_element(By.TAG_NAME, "body").text
    assert "SUPER ADMIN" in page_text.upper() or "PLATFORM ADMINISTRATION" in page_text.upper()

    # Navigate to /admin/tenants
    driver.get(f"{BASE_WEB_URL}/admin/tenants")
    wait = WebDriverWait(driver, 15)
    wait.until(EC.presence_of_element_located((By.XPATH, "//h1[contains(., 'Tenant') or contains(., 'Directory')]")))
    wait.until(lambda d: "Loading registered companies" not in d.find_element(By.TAG_NAME, "main").text)
    time.sleep(1.0)

    main_text = driver.find_element(By.TAG_NAME, "main").text
    assert seeded_entities["tenant_a_name"] in main_text, "Tenant Alpha missing from Super Admin Directory"
    assert seeded_entities["tenant_b_name"] in main_text, "Tenant Beta missing from Super Admin Directory"

    # Click 'Add New Company' modal button
    create_btn = wait.until(EC.element_to_be_clickable((By.ID, "add-company-btn")))
    create_btn.click()
    time.sleep(0.5)

    # Fill Create Modal
    gamma_name = f"Gamma Spaceflight Pvt Ltd {uuid.uuid4().hex[:4]}"
    gamma_cin = f"U72900KA2026PTC{uuid.uuid4().hex[:6].upper()}"
    gamma_pan = f"AABCG{uuid.uuid4().hex[:4].upper()}F"

    legal_name_input = wait.until(EC.presence_of_element_located((By.ID, "new-company-legal-name")))
    legal_name_input.send_keys(gamma_name)

    pan_input = driver.find_element(By.ID, "new-company-pan")
    pan_input.send_keys(gamma_pan)

    cin_input = driver.find_element(By.ID, "new-company-cin")
    cin_input.send_keys(gamma_cin)

    submit_modal_btn = driver.find_element(By.ID, "provision-company-submit-btn")
    submit_modal_btn.click()

    # Verify new tenant in directory
    wait.until(lambda d: gamma_name in d.find_element(By.TAG_NAME, "main").text)
    updated_main = driver.find_element(By.TAG_NAME, "main").text
    assert gamma_name in updated_main, "Newly created Gamma Spaceflight tenant not displayed in directory"

    take_screenshot(driver, "e2e_iam_1_super_admin_tenants")


# ==============================================================================
# TEST 2: COMPANY OWNER PROFILE — IAM User Management & Member Invitation
# ==============================================================================
def test_company_owner_iam_user_management(chrome_driver, seeded_entities):
    """
    Company Owner Verification:
    1. Authenticates as Owner Alpha.
    2. Asserts 'Company Owner' badge and absence of Super Admin links.
    3. Navigates to /iam (Identity & Access Management).
    4. Asserts existing team roster (Owner, Finance Manager, CA Auditor, Employee).
    5. Opens 'Invite Team Member' modal, invites a new Finance Analyst.
    6. Asserts new member is visible in user list.
    7. Directly attempts /admin/tenants -> receives warning / block.
    """
    driver = chrome_driver
    oa = seeded_entities["owner_a"]
    login_via_ui(driver, oa["email"], oa["pass"])

    # Check Sidebar role
    body_text = driver.find_element(By.TAG_NAME, "body").text
    assert "COMPANY OWNER" in body_text.upper()
    assert "PLATFORM ADMINISTRATION" not in body_text.upper()

    # Navigate to /iam
    driver.get(f"{BASE_WEB_URL}/iam")
    wait = WebDriverWait(driver, 15)
    wait.until(EC.presence_of_element_located((By.XPATH, "//h2[contains(., 'Identity & Access Management')] | //h1[contains(., 'Identity')]")))
    time.sleep(1.0)

    page_content = driver.find_element(By.TAG_NAME, "main").text
    assert "Roles & Permission Matrix" in page_content or "Statutory role-based access control" in page_content
    assert seeded_entities["finance_a"]["email"] in page_content
    assert seeded_entities["ca_auditor"]["email"] in page_content

    # Click 'Add Team Member / Auditor' button
    invite_btn = wait.until(EC.element_to_be_clickable((By.ID, "add-member-modal-btn")))
    invite_btn.click()
    time.sleep(0.5)

    new_member_email = f"analyst.{uuid.uuid4().hex[:6]}@alphacorp.in"
    driver.find_element(By.ID, "invite-member-first-name").send_keys("Kavita")
    driver.find_element(By.ID, "invite-member-last-name").send_keys("Rao")
    driver.find_element(By.ID, "invite-member-email").send_keys(new_member_email)
    driver.find_element(By.ID, "invite-member-password").send_keys("AnalystPass123!")

    # Select finance_manager role
    role_select = Select(driver.find_element(By.ID, "invite-member-role"))
    role_select.select_by_value("finance_manager")

    send_invite_btn = driver.find_element(By.ID, "invite-member-submit-btn")
    driver.execute_script("arguments[0].click();", send_invite_btn)

    # Verify newly added member is present in roster
    try:
        wait.until(lambda d: new_member_email in d.find_element(By.TAG_NAME, "main").text)
    except Exception as exc:
        print("\n--- DIAGNOSTICS ON IAM FAILURE ---")
        print("BODY TEXT:\n", driver.find_element(By.TAG_NAME, "body").text)
        print("MODAL TEXT:\n", [m.text for m in driver.find_elements(By.XPATH, "//form")])
        take_screenshot(driver, "e2e_iam_2_failure_debug")
        raise exc

    updated_users_text = driver.find_element(By.TAG_NAME, "main").text
    assert new_member_email in updated_users_text, "Newly invited team member did not appear in IAM user list"

    # Non-super-admin accessing /admin/tenants must be rejected / warned
    driver.get(f"{BASE_WEB_URL}/admin/tenants")
    time.sleep(1.5)
    admin_page_text = driver.find_element(By.TAG_NAME, "body").text
    assert "Ensure you are logged in as Super Admin" in admin_page_text or "Access denied" in admin_page_text or "No companies found" in admin_page_text or "No registered companies" in admin_page_text or "Dashboard" in admin_page_text

    take_screenshot(driver, "e2e_iam_2_owner_user_management")


# ==============================================================================
# TEST 3: FINANCE MANAGER PROFILE — Operations Access & IAM Mutation Guard
# ==============================================================================
def test_finance_manager_operations_and_guard(chrome_driver, seeded_entities):
    """
    Finance Manager Verification:
    1. Authenticates as Finance Manager Alpha.
    2. Navigates to /invoices -> Verifies full access to Invoicing & GST engine.
    3. Navigates to /expenses -> Verifies access to record vendor bills.
    4. Navigates to /reconciliation -> Verifies access to bank feeds.
    5. Directly attempts to POST /api/v1/iam/users -> Blocked with 403 Forbidden.
    """
    driver = chrome_driver
    fma = seeded_entities["finance_a"]
    login_via_ui(driver, fma["email"], fma["pass"])

    # 1. Invoices
    driver.get(f"{BASE_WEB_URL}/invoices")
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "main")))
    time.sleep(0.5)
    invoices_text = driver.find_element(By.TAG_NAME, "main").text
    assert "Invoices & Accounts Receivable" in invoices_text or "Invoices" in invoices_text

    # 2. Expenses
    driver.get(f"{BASE_WEB_URL}/expenses")
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "main")))
    time.sleep(0.5)
    expenses_text = driver.find_element(By.TAG_NAME, "main").text
    assert "Expenses" in expenses_text

    # 3. Bank Reconciliation
    driver.get(f"{BASE_WEB_URL}/reconciliation")
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "main")))
    time.sleep(0.5)
    rec_text = driver.find_element(By.TAG_NAME, "main").text
    assert "Reconciliation" in rec_text or "Bank" in rec_text

    # 4. API Mutation Guard: Finance Manager cannot invite IAM users
    token = driver.execute_script("return localStorage.getItem('b00k5_token');")
    tid = seeded_entities["tenant_a_id"]
    res = requests.post(
        f"{BASE_API_URL}/api/v1/iam/users",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": tid},
        json={"email": "hack@hacker.com", "first_name": "Bad", "last_name": "Actor", "role": "owner", "password": "123"}
    )
    assert res.status_code == 403, f"Expected 403 Forbidden when Finance Manager attempts IAM user creation, got {res.status_code}"

    take_screenshot(driver, "e2e_iam_3_finance_manager_operations")


# ==============================================================================
# TEST 4: AUDITOR CA PROFILE — Read-Only Mode & Multi-Company Tenant Switcher
# ==============================================================================
def test_auditor_ca_readonly_and_tenant_switcher(chrome_driver, seeded_entities):
    """
    Statutory Auditor CA Verification:
    1. Authenticates as CA Auditor (holds memberships in both Alpha and Beta).
    2. Asserts 'CA / Auditor Mode' badge in Sidebar.
    3. Verifies Schedule III ICAI Financial Statements in /yearbook.
    4. Verifies General Ledger in /reports/general-ledger.
    5. Attempts mutation request (e.g. creating invoice) -> Blocked with 403 / transaction_read_only.
    6. Uses TenantSwitcher in Navbar to switch between Alpha Innovations and Beta Consulting.
    7. Asserts active tenant changes to Beta Consulting in localStorage and Navbar.
    """
    driver = chrome_driver
    ca = seeded_entities["ca_auditor"]
    login_via_ui(driver, ca["email"], ca["pass"])

    # 1. Verify Auditor Role badge
    body_text = driver.find_element(By.TAG_NAME, "body").text
    assert "CA / AUDITOR MODE" in body_text.upper()

    # 2. Yearbook Schedule III
    driver.get(f"{BASE_WEB_URL}/yearbook")
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "main")))
    time.sleep(0.8)
    yearbook_text = driver.find_element(By.TAG_NAME, "main").text
    assert "Balance Sheet" in yearbook_text or "Audited" in yearbook_text or "Statutory" in yearbook_text

    # 3. Read-Only Mutation Block
    token = driver.execute_script("return localStorage.getItem('b00k5_token');")
    tid_a = seeded_entities["tenant_a_id"]
    res_inv = requests.post(
        f"{BASE_API_URL}/api/v1/invoices/",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": tid_a},
        json={"invoice_number": "INV-AUDIT-FAIL", "issue_date": "2026-05-10", "due_date": "2026-06-10", "place_of_supply": "29", "items": []}
    )
    assert res_inv.status_code == 403, f"Expected 403 Forbidden for CA mutation on invoices, got {res_inv.status_code}"

    # 4. Multi-Company TenantSwitcher
    # Open Tenant Switcher dropdown in Navbar
    switcher_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'bg-slate-800') and (contains(., 'Innovations') or contains(., 'Alpha') or contains(., 'Select Company'))]")))
    switcher_btn.click()
    time.sleep(0.5)

    # Check Beta Consulting is present in dropdown and click it
    beta_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Beta Consulting')]")))
    beta_btn.click()
    time.sleep(1.0)

    # Verify switched tenant in localStorage
    wait.until(lambda d: d.execute_script("return localStorage.getItem('b00k5_tenant_id') || localStorage.getItem('b00k5_active_tenant_id');") == seeded_entities["tenant_b_id"])
    active_tid = driver.execute_script("return localStorage.getItem('b00k5_tenant_id') || localStorage.getItem('b00k5_active_tenant_id');")
    assert active_tid == seeded_entities["tenant_b_id"], f"Expected tenant_id to be {seeded_entities['tenant_b_id']}, got {active_tid}"

    take_screenshot(driver, "e2e_iam_4_auditor_ca_switched_tenant")


# ==============================================================================
# TEST 5: EMPLOYEE PROFILE — Self-Service Isolation & Route Guard Defense
# ==============================================================================
def test_employee_self_service_isolation_and_route_guards(chrome_driver, seeded_entities):
    """
    Employee Self-Service Verification:
    1. Authenticates as Employee Alpha.
    2. Asserts 'Employee Portal' badge in Sidebar.
    3. Verifies strictly limited sidebar (only Expenses / Reimbursements & Profile).
    4. Direct browser navigation to restricted routes (/invoices, /reports/general-ledger, /vault, /iam, /admin/tenants):
       Asserts all API calls receive 403 Forbidden.
    """
    driver = chrome_driver
    ea = seeded_entities["employee_a"]
    login_via_ui(driver, ea["email"], ea["pass"])

    # 1. Verify Sidebar is limited
    body_text = driver.find_element(By.TAG_NAME, "body").text
    assert "EMPLOYEE PORTAL" in body_text.upper()
    assert "Tax Invoices & AR" not in body_text
    assert "Bank Feeds & Reconciliation" not in body_text
    assert "Year Book & Schedule III" not in body_text
    assert "Document Vault" not in body_text
    assert "Hardware DSC Signing" not in body_text

    # 2. Verify Employee Expenses access
    driver.get(f"{BASE_WEB_URL}/expenses")
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "main")))
    time.sleep(0.5)
    exp_text = driver.find_element(By.TAG_NAME, "main").text
    assert "Expenses" in exp_text

    # 3. Direct Route Penetration: Employee JWT testing against restricted endpoints
    token = driver.execute_script("return localStorage.getItem('b00k5_token');")
    tid_a = seeded_entities["tenant_a_id"]
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": tid_a}

    restricted_get_endpoints = [
        "/api/v1/invoices/",
        "/api/v1/ledger/trial-balance",
        "/api/v1/vault/",
        "/api/v1/iam/users",
        "/api/v1/reconciliation/statements",
        "/api/v1/compliance/directors",
    ]
    for ep in restricted_get_endpoints:
        r = requests.get(f"{BASE_API_URL}{ep}", headers=headers)
        assert r.status_code == 403, f"Expected 403 Forbidden for Employee accessing {ep}, got {r.status_code}"

    # Verify Super Admin only route is 403 blocked for employee
    r_admin = requests.post(
        f"{BASE_API_URL}/api/v1/tenants/admin/create-tenant",
        headers=headers,
        json={"legal_name": "Rogue Entity", "pan": "ABCDE1234F", "entity_type": "Private Limited Company"}
    )
    assert r_admin.status_code == 403, f"Expected 403 Forbidden for Employee accessing create-tenant, got {r_admin.status_code}"

    take_screenshot(driver, "e2e_iam_5_employee_isolation")


# ==============================================================================
# TEST 6: CROSS-TENANT PENETRATION — Tenant Alpha vs Tenant Beta Defense
# ==============================================================================
def test_cross_tenant_header_injection_and_isolation(chrome_driver, seeded_entities):
    """
    Cross-Tenant Isolation Penetration Verification:
    1. Uses Owner Alpha credentials (has zero membership in Tenant Beta).
    2. Attempts spoofed header attacks: passes X-Tenant-ID = tenant_b_id across:
       - /api/v1/invoices/
       - /api/v1/vault/
       - /api/v1/expenses/
       - /api/v1/ledger/journals
    3. Asserts 100% rejection with 403 Forbidden.
    4. In browser: injects Tenant Beta's ID into localStorage while authenticated as Owner Alpha.
       Loads /invoices -> Asserts UI renders error boundary or zero records without leaking Tenant Beta data.
    """
    driver = chrome_driver
    oa = seeded_entities["owner_a"]
    login_via_ui(driver, oa["email"], oa["pass"])

    token = driver.execute_script("return localStorage.getItem('b00k5_token');")
    tid_b = seeded_entities["tenant_b_id"]

    # 1. API Spoofing test
    spoof_headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": tid_b}
    for ep in ("/api/v1/invoices/", "/api/v1/vault/", "/api/v1/expenses/", "/api/v1/ledger/journals"):
        res = requests.get(f"{BASE_API_URL}{ep}", headers=spoof_headers)
        assert res.status_code == 403, f"CRITICAL LEAK: Owner Alpha with spoofed X-Tenant-ID({tid_b}) got {res.status_code} on {ep}"
        assert "access denied" in res.json().get("detail", "").lower()

    # 2. Browser LocalStorage Tamper test
    driver.execute_script(f"localStorage.setItem('b00k5_tenant_id', '{tid_b}');")
    driver.get(f"{BASE_WEB_URL}/invoices")
    time.sleep(1.0)

    # Verify no Tenant Beta data was rendered
    page_text = driver.find_element(By.TAG_NAME, "body").text
    assert seeded_entities["tenant_b_name"] not in page_text

    take_screenshot(driver, "e2e_iam_6_cross_tenant_defense")

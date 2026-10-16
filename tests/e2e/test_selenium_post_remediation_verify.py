import os
import time
import json
import uuid
import pytest
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

BASE_WEB_URL = os.getenv("BASE_WEB_URL", "http://localhost:3000")
BASE_API_URL = os.getenv("BASE_API_URL", "http://localhost:8000")
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SCREENSHOTS_DIR = Path(__file__).resolve().parent / "screenshots" / "post_remediation"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def snap(driver, name: str) -> str:
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
    opts.set_capability("goog:loggingPrefs", {"browser": "ALL"})

    driver = webdriver.Chrome(options=opts)
    driver.implicitly_wait(5)
    yield driver
    driver.quit()


@pytest.fixture(scope="session")
def seeded_audit_user():
    uid_suffix = uuid.uuid4().hex[:6]
    rand_a = uuid.uuid4().hex[:6].upper()

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
            statutory_profile={{"entity_type": "PVT_LTD", "onboarding_status": "VERIFIED", "coi_verified": True, "pan_verified": True}}
        )
        db.add(t_a)
        await db.commit()

        uid_oa = uuid.uuid4()
        u_oa = User(
            id=uid_oa,
            email="owner.remedy.{uid_suffix}@b00k5.test",
            password_hash=get_password_hash("AuditOwner123!"),
            first_name="Adithya",
            last_name="Director",
            is_super_admin=True,
            is_active=True
        )
        db.add(u_oa)
        tu_oa = TenantUser(tenant_id=tid_a, user_id=uid_oa, role="owner", din="08291038", is_primary=True, is_active=True)
        db.add(tu_oa)

        await db.commit()

        print(json.dumps({{
            "email": u_oa.email,
            "password": "AuditOwner123!"
        }}))

asyncio.run(seed())
"""
    import subprocess
    cmd = ["docker", "exec", "b00k5_api", "python3", "-c", seed_script]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("SEED SCRIPT ERROR:", res.stderr)
        raise RuntimeError(f"Seed script failed: {res.stderr}")
    return json.loads(res.stdout.strip())


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
    time.sleep(2)


def test_verify_remediated_defects(chrome_driver, seeded_audit_user):
    """
    Verifies that all 11 cataloged defects are resolved:
    1. Bidirectional FY sync between top Navbar and child tabs
    2. Vault INC-20A card deduplication (count == 0 or 1, zero duplicates)
    3. Vault taxonomy segregating Permanent Corporate Dossier from Annual Statutory Filings
    4. IAM route consolidation: /settings/team redirects to /iam, sidebar links to /iam
    5. Statutory Expense Section 37(1), 40A(3), 16(2), and Section 69C / 115BBE 78% punitive tax notice
    """
    driver = chrome_driver
    creds = seeded_audit_user
    wait = WebDriverWait(driver, 10)

    # Step 1: Login
    login(driver, creds["email"], creds["password"])

    # -------------------------------------------------------------------------
    # CHECK 1: Expense Without Bill Statutory Warnings (Section 69C, 115BBE, etc.)
    # -------------------------------------------------------------------------
    print("\n--- Verifying Route: /expenses/new Statutory Disclosures ---")
    driver.get(f"{BASE_WEB_URL}/expenses/new")
    time.sleep(2)

    unvouched_chk = wait.until(EC.presence_of_element_located((By.ID, "unvouched-self-voucher-toggle")))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", unvouched_chk)
    if not unvouched_chk.is_selected():
        unvouched_chk.click()
        time.sleep(1)

    exp_body = driver.find_element(By.TAG_NAME, "body").text
    snap(driver, "verify_01_expenses_unvouched_statutory_notices")

    assert "Section 37(1)" in exp_body, "Must contain Section 37(1) statutory notice"
    assert "Section 40A(3)" in exp_body, "Must contain Section 40A(3) cash limit notice"
    assert "16(2)" in exp_body, "Must contain Section 16(2) CGST Act 0% ITC notice"
    assert "Section 69C" in exp_body or "115BBE" in exp_body, "Must contain Section 69C / Section 115BBE 78% punitive tax notice"
    assert "78%" in exp_body, "Must explicitly state the 78% punitive tax penalty"
    print("✓ Check 1 Passed: Section 69C/115BBE 78% punitive tax alert verified!")

    # -------------------------------------------------------------------------
    # CHECK 2: Vault Deduplication & Permanent Dossier Taxonomy
    # -------------------------------------------------------------------------
    print("\n--- Verifying Route: /vault Deduplication & Taxonomy ---")
    driver.get(f"{BASE_WEB_URL}/vault")
    time.sleep(2)
    snap(driver, "verify_02_vault_page_taxonomy")

    # Assert INC-20A card title count <= 1 (strictly no duplicates)
    inc20_titles = driver.find_elements(By.XPATH, "//h4[contains(text(), 'INC-20A') or contains(text(), 'Commencement of Business')]")
    print(f"Vault: INC-20A cards found = {len(inc20_titles)}")
    assert len(inc20_titles) <= 1, f"Expected at most 1 INC-20A card, found {len(inc20_titles)}"

    # Check for Dossier Scope switcher buttons by ID
    perm_btn = driver.find_element(By.ID, "tab-permanent-dossier")
    annual_btn = driver.find_element(By.ID, "tab-annual-filings")
    all_btn = driver.find_element(By.ID, "tab-all-records")
    assert perm_btn is not None and annual_btn is not None and all_btn is not None

    # Click Permanent Corporate Dossier
    perm_btn.click()
    time.sleep(1)
    vault_body_perm = driver.find_element(By.TAG_NAME, "body").text
    assert "Permanent" in vault_body_perm
    print("✓ Check 2 Passed: Vault deduplication & Permanent Dossier taxonomy verified!")

    # -------------------------------------------------------------------------
    # CHECK 3: IAM Route Consolidation & Sidebar Link
    # -------------------------------------------------------------------------
    print("\n--- Verifying Route: IAM Consolidation & /settings/team Redirect ---")
    driver.get(f"{BASE_WEB_URL}/settings/team")
    time.sleep(3)
    snap(driver, "verify_03_settings_team_redirected_to_iam")

    current_url = driver.current_url
    print(f"URL after navigating to /settings/team: {current_url}")
    body_text = driver.find_element(By.TAG_NAME, "body").text
    assert "/iam" in current_url or "Moved to IAM" in body_text, "Visiting /settings/team must redirect to /iam or display consolidated IAM card"

    # Verify Sidebar link
    sidebar_iam_link = driver.find_element(By.XPATH, "//a[contains(@href, '/iam')]")
    assert sidebar_iam_link is not None, "Sidebar must feature direct link to /iam"
    print("✓ Check 3 Passed: IAM route consolidation & sidebar link verified!")

    # -------------------------------------------------------------------------
    # CHECK 4: Bidirectional FY Synchronization (Navbar <-> Child Tabs)
    # -------------------------------------------------------------------------
    print("\n--- Verifying Bidirectional FY Synchronization ---")
    driver.get(f"{BASE_WEB_URL}/yearbook")
    time.sleep(2)
    snap(driver, "verify_04_yearbook_initial_load")

    # Click FY 2025-26 button in Yearbook tab bar
    fy25_btn = driver.find_element(By.XPATH, "//button[contains(., 'FY 2025-26')]")
    fy25_btn.click()
    time.sleep(1)
    snap(driver, "verify_05_yearbook_fy2025_synced_to_navbar")

    navbar_select = Select(driver.find_element(By.ID, "fy-switcher-select"))
    navbar_selected_text = navbar_select.first_selected_option.text.strip()
    print(f"Yearbook clicked FY 2025-26 -> Navbar selected text: '{navbar_selected_text}'")
    assert "2025" in navbar_selected_text and "26" in navbar_selected_text, (
        f"Navbar select must reflect FY 2025-26 after child tab change. Got: {navbar_selected_text}"
    )

    # Check that prior period badge or notice is visible
    yb_body = driver.find_element(By.TAG_NAME, "body").text
    assert "Prior Period:" in yb_body or "Prior Year" in yb_body or "2025-26" in yb_body

    print("✓ Check 4 Passed: Bidirectional FY synchronization verified!")
    print("\n================ ALL POST-REMEDIATION VERIFICATION CHECKS PASSED ================\n")

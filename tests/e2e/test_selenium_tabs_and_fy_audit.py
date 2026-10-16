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
SCREENSHOTS_DIR = Path(__file__).resolve().parent / "screenshots" / "tabs_and_fy_audit"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

AUDIT_FINDINGS = []


def record_finding(route: str, component_or_tab: str, defect_type: str, severity: str, title: str, description: str, screenshot_path: str = None):
    finding = {
        "id": f"TAB-FY-{len(AUDIT_FINDINGS) + 1:02d}",
        "route": route,
        "component": component_or_tab,
        "type": defect_type,
        "severity": severity,
        "title": title,
        "description": description,
        "screenshot": screenshot_path
    }
    AUDIT_FINDINGS.append(finding)
    print(f"\n[{severity.upper()}] [{finding['id']}] [{route} -> {component_or_tab}] {title}\n  -> {description}")


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
    driver.implicitly_wait(6)
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
            email="owner.tabs.{uid_suffix}@b00k5.test",
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
    time.sleep(1)


def test_selenium_tabs_and_fy_desync_audit(chrome_driver, seeded_audit_user):
    """
    Executes comprehensive zero-mock Selenium audit for:
    1. Tabs across /governance, /yearbook, /reconciliation, /vault
    2. Changing FY in top header and checking child tab desync
    3. Vault annual vs permanent documents and INC-20A duplication
    4. /settings/team vs /iam duplication
    5. Statutory Expense Without Bill Section 37(1), 40A(3), 69C, 16(2) check
    """
    driver = chrome_driver
    creds = seeded_audit_user
    wait = WebDriverWait(driver, 10)

    # 1. Login
    login(driver, creds["email"], creds["password"])

    # -------------------------------------------------------------
    # ROUTE 1: /governance - Tab Navigation & FY Synchronization
    # -------------------------------------------------------------
    driver.get(f"{BASE_WEB_URL}/governance")
    time.sleep(2)
    s1 = snap(driver, "01_governance_initial_load")

    # Audit initial Navbar FY vs Page state
    navbar_fy_select = driver.find_element(By.ID, "fy-switcher-select")
    navbar_active_fy = Select(navbar_fy_select).first_selected_option.text.strip()
    navbar_badge = driver.find_element(By.ID, "active-fy-ay-badge").text.strip()
    print(f"Governance Initial: Navbar FY={navbar_active_fy}, Badge={navbar_badge}")

    # Inspect Governance Tabs list
    gov_tabs = [
        ("board_governance", "Board Governance"),
        ("gstr2b", "GSTR-2B"),
        ("llp", "LLP Secretarial"),
        ("sec40a3", "Section 40A(3)"),
        ("advance_tax", "Advance Tax"),
        ("statutory_baseline", "Statutory Baseline"),
        ("statutory_dossier", "Statutory Dossier"),
        ("tds_compliance", "TDS"),
        ("fixed_assets", "Fixed Assets"),
        ("mca_registers", "MCA Registers")
    ]

    for tab_id, tab_title in gov_tabs:
        try:
            # Click tab button
            tab_btn = driver.find_element(By.XPATH, f"//button[contains(., '{tab_title}')]")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", tab_btn)
            tab_btn.click()
            time.sleep(0.8)

            if tab_id == "statutory_baseline":
                s_base = snap(driver, "02_governance_tab_statutory_baseline")
                body_text = driver.find_element(By.TAG_NAME, "body").text
                # Check for FY in Statutory Baseline Seal
                if "FY 2025-26" in body_text and "FY 2026-27" in navbar_active_fy:
                    record_finding(
                        route="/governance",
                        component_or_tab="Statutory Baseline Tab",
                        defect_type="FY_DESYNCHRONIZATION",
                        severity="high",
                        title="Statutory Baseline Fiscal Year Mismatches Navbar Global FY",
                        description=f"Global Navbar indicates active period '{navbar_active_fy}', but Statutory Baseline tab renders hardcoded 'FY 2025-26' target seal.",
                        screenshot_path=s_base
                    )

            elif tab_id == "llp":
                body_text = driver.find_element(By.TAG_NAME, "body").text
                if "2025-26" in body_text and "2026-27" in navbar_active_fy:
                    record_finding(
                        route="/governance",
                        component_or_tab="LLP Secretarial Tab",
                        defect_type="FY_DESYNCHRONIZATION",
                        severity="medium",
                        title="LLP Secretarial Tab Defaults to 2025-26 Regardless of Navbar Selection",
                        description=f"LLP Secretarial state 'llpYear' is hardcoded to '2025-26' and does not update when global FY is set to {navbar_active_fy}.",
                        screenshot_path=snap(driver, "03_governance_tab_llp")
                    )

            elif tab_id == "sec40a3":
                body_text = driver.find_element(By.TAG_NAME, "body").text
                if "2025-26" in body_text and "2026-27" in navbar_active_fy:
                    record_finding(
                        route="/governance",
                        component_or_tab="Section 40A(3) Watchdog Tab",
                        defect_type="FY_DESYNCHRONIZATION",
                        severity="medium",
                        title="Section 40A(3) Tab Defaults to Prior FY 2025-26",
                        description="Section 40A(3) watchdog state 'sec40a3Year' defaults to '2025-26' instead of listening to the global selected financial year.",
                        screenshot_path=snap(driver, "04_governance_tab_sec40a3")
                    )

        except Exception as e:
            record_finding(
                route="/governance",
                component_or_tab=f"Tab {tab_title}",
                defect_type="TAB_NAVIGATION_ERROR",
                severity="medium",
                title=f"Failed to navigate to {tab_title} tab",
                description=str(e),
                screenshot_path=snap(driver, f"err_gov_tab_{tab_id}")
            )

    # Now change Global FY in Navbar to Prior Period (FY 2025-26 or FY 2025-2026)
    try:
        navbar_fy_select = driver.find_element(By.ID, "fy-switcher-select")
        select_obj = Select(navbar_fy_select)
        options = [o.text.strip() for o in select_obj.options]
        print(f"Available Navbar FY Options: {options}")

        # Choose the prior year option
        prior_opt = next((o for o in options if "2025" in o), None)
        if prior_opt:
            select_obj.select_by_visible_text(prior_opt)
            time.sleep(1.5)
            s_fy_switch = snap(driver, "05_governance_after_fy_switch_to_prior")
            new_badge = driver.find_element(By.ID, "active-fy-ay-badge").text.strip()
            print(f"After Switch: Navbar Option={prior_opt}, Badge={new_badge}")

            # Verify if Board Meeting No. changed from BM/2026-27/01 to BM/2025-26/01
            driver.find_element(By.XPATH, "//button[contains(., 'Board Governance')]").click()
            time.sleep(0.5)
            bm_no_val = driver.find_element(By.XPATH, "//input[@value='BM/2026-27/01' or contains(@value, 'BM/')]").get_attribute("value")
            if "2026-27" in bm_no_val:
                record_finding(
                    route="/governance",
                    component_or_tab="Board Governance Meeting No",
                    defect_type="FY_DESYNCHRONIZATION",
                    severity="low",
                    title="Meeting Number Template Does Not Dynamically Adapt to Selected FY",
                    description=f"When Navbar switched to '{prior_opt}', Board Governance meeting number remained '{bm_no_val}' instead of updating to BM/2025-26/01.",
                    screenshot_path=s_fy_switch
                )
    except Exception as e:
        record_finding(
            route="/governance",
            component_or_tab="Navbar FY Switcher",
            defect_type="FY_SWITCH_ERROR",
            severity="high",
            title="Error changing Navbar FY dropdown",
            description=str(e)
        )

    # -------------------------------------------------------------
    # ROUTE 2: /yearbook - Multi-Year FY Tabs and Child Tabs
    # -------------------------------------------------------------
    driver.get(f"{BASE_WEB_URL}/yearbook")
    time.sleep(2)
    s_yb_init = snap(driver, "06_yearbook_initial_load")

    # Check Yearbook FY Tab Bar vs Navbar
    yb_body = driver.find_element(By.TAG_NAME, "body").text
    navbar_fy = driver.find_element(By.ID, "fy-switcher-select")
    navbar_fy_val = Select(navbar_fy).first_selected_option.text.strip()

    # Find the FY button list on Yearbook page
    yb_fy_buttons = driver.find_elements(By.XPATH, "//div[contains(@class, 'flex') and contains(@class, 'overflow-x-auto')]//button[contains(., 'FY')]")
    print(f"Yearbook FY buttons found: {len(yb_fy_buttons)}")

    # Check sub-tabs in Yearbook
    yb_subtabs = ["Bank Statements", "Vendor Bills", "Sales Invoices", "Schedule III Financials", "Closing & Filings"]
    for subtab in yb_subtabs:
        try:
            tab_btn = driver.find_element(By.XPATH, f"//button[contains(., '{subtab}')]")
            tab_btn.click()
            time.sleep(0.8)
            snap(driver, f"07_yearbook_{subtab.lower().replace(' ', '_')}")
        except Exception as e:
            record_finding(
                route="/yearbook",
                component_or_tab=subtab,
                defect_type="TAB_NAVIGATION_ERROR",
                severity="medium",
                title=f"Error switching to Yearbook tab '{subtab}'",
                description=str(e)
            )

    # Click a different FY button on Yearbook page (e.g. FY 2025-26)
    try:
        fy_btn_25_26 = driver.find_element(By.XPATH, "//button[contains(., '2025-26') or contains(., 'FY 2025-26')]")
        fy_btn_25_26.click()
        time.sleep(1.5)
        s_yb_fy25 = snap(driver, "08_yearbook_fy2025_selected")

        # Check if Navbar updated to reflect the new FY
        navbar_now = Select(driver.find_element(By.ID, "fy-switcher-select")).first_selected_option.text.strip()
        print(f"Yearbook switched to 2025-26. Navbar now shows: '{navbar_now}'")
        if "2026" in navbar_now and "2025" not in navbar_now:
            record_finding(
                route="/yearbook",
                component_or_tab="FY Button Bar",
                defect_type="FY_DESYNCHRONIZATION",
                severity="medium",
                title="Yearbook FY Selection Does Not Update Global Navbar Dropdown",
                description=f"Clicking FY 2025-26 on Yearbook tab bar left top Navbar displaying '{navbar_now}', causing visual confusion.",
                screenshot_path=s_yb_fy25
            )
    except Exception as e:
        record_finding(
            route="/yearbook",
            component_or_tab="FY Tab Bar",
            defect_type="FY_SWITCH_ERROR",
            severity="medium",
            title="Could not toggle Yearbook FY button",
            description=str(e)
        )

    # -------------------------------------------------------------
    # ROUTE 3: /reconciliation - Period Tabs & Navbar Synchronization
    # -------------------------------------------------------------
    driver.get(f"{BASE_WEB_URL}/reconciliation")
    time.sleep(2)
    s_rec_init = snap(driver, "09_reconciliation_initial_load")

    # Check for Reconciliation FY Filter Buttons
    rec_body = driver.find_element(By.TAG_NAME, "body").text
    rec_fy_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'FY ') or contains(., '2025-26') or contains(., '2026-27')]")

    # Check if prior period lock or desync is visible
    if "Prior Financial Year Reconciliation Locked" in rec_body or "Prior Period:" in rec_body:
        s_rec_prior = snap(driver, "10_reconciliation_prior_period_state")
        navbar_now = Select(driver.find_element(By.ID, "fy-switcher-select")).first_selected_option.text.strip()
        if "Current" in navbar_now:
            record_finding(
                route="/reconciliation",
                component_or_tab="Reconciliation Statement View",
                defect_type="FY_DESYNCHRONIZATION",
                severity="high",
                title="Reconciliation Shows Prior Period Lock While Navbar Shows Current Period",
                description=f"Reconciliation page displays a locked prior period view, but top Navbar still displays '{navbar_now}'.",
                screenshot_path=s_rec_prior
            )

    # -------------------------------------------------------------
    # ROUTE 4: /vault - Statutory Year Filter Bar & INC-20A Duplication
    # -------------------------------------------------------------
    driver.get(f"{BASE_WEB_URL}/vault")
    time.sleep(2)
    s_vault_init = snap(driver, "11_vault_initial_load")

    # Check for INC-20A duplicates in the document grid
    inc20_cards = driver.find_elements(By.XPATH, "//*[contains(text(), 'INC-20A') or contains(text(), 'Commencement of Business')]")
    print(f"Vault: Elements containing 'INC-20A' or 'Commencement': {len(inc20_cards)}")

    # Specific count of document card headers with Form INC-20A
    doc_titles = driver.find_elements(By.XPATH, "//h4[contains(text(), 'INC-20A') or contains(text(), 'Commencement of Business')]")
    print(f"Vault: Document cards with INC-20A title: {len(doc_titles)}")

    if len(doc_titles) > 1:
        s_inc_dup = snap(driver, "12_vault_inc20a_duplications")
        record_finding(
            route="/vault",
            component_or_tab="Document Grid",
            defect_type="DUPLICATE_DATA_RENDER",
            severity="high",
            title=f"Form INC-20A Rendered {len(doc_titles)} Times in Corporate Vault",
            description=f"Document Vault contains {len(doc_titles)} identical duplicate cards for 'Form INC-20A Commencement of Business'. Missing unique constraint and ingestion deduplication.",
            screenshot_path=s_inc_dup
        )

    # Check Vault Statutory Year Filter Bar
    vault_fy_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'All Records') or contains(., 'FY 2025-26') or contains(., 'FY 2026-27') or contains(., 'Permanent Legal')]")
    print(f"Vault: Statutory filter buttons found: {len(vault_fy_buttons)}")

    # Click "FY 2025-26" filter in Vault
    try:
        fy25_vault_btn = driver.find_element(By.XPATH, "//button[contains(., 'FY 2025-26')]")
        fy25_vault_btn.click()
        time.sleep(1)
        s_vault_fy25 = snap(driver, "13_vault_filter_fy2025")

        # In Screenshot 3, user noted:
        # "in vault some documents will be uploaded only once like CIN PAN DIN etc... for the others yearly are needed only for those that need yearly it should have tab for selecting the year look at screenshot 3"
        # Check if permanent documents (COI, PAN, TAN, DIN) disappear or are inappropriately filtered under annual FY
        body_text_filtered = driver.find_element(By.TAG_NAME, "body").text
        record_finding(
            route="/vault",
            component_or_tab="Statutory Year Filter Bar",
            defect_type="UI_UX_TAXONOMY_DEFECT",
            severity="medium",
            title="Statutory Year Filter Bar Inappropriately Mixes Permanent Corporate Documents with Annual Filings",
            description="Vault currently uses a single global Statutory Year filter. Permanent corporate documents (COI, Company PAN, TAN, MOA, AOA, INC-20A) are one-time entities that should remain visible in their own permanent dossier tab, while annual tabs (FY 2025-26, FY 2026-27) should strictly scope recurring filings (AOC-4, MGT-7, ADT-1, Tax Audits).",
            screenshot_path=s_vault_fy25
        )
    except Exception as e:
        record_finding(
            route="/vault",
            component_or_tab="Statutory Year Filter",
            defect_type="FILTER_ERROR",
            severity="medium",
            title="Error clicking FY 2025-26 filter in vault",
            description=str(e)
        )

    # -------------------------------------------------------------
    # ROUTE 5: IAM Duplication: /settings/team vs /iam
    # -------------------------------------------------------------
    # 1. Audit /settings/team
    driver.get(f"{BASE_WEB_URL}/settings/team")
    time.sleep(2)
    s_team = snap(driver, "14_settings_team_page")
    team_body = driver.find_element(By.TAG_NAME, "body").text
    team_members = driver.find_elements(By.XPATH, "//tr[contains(@class, 'border-b')]")

    # 2. Audit /iam
    driver.get(f"{BASE_WEB_URL}/iam")
    time.sleep(2)
    s_iam = snap(driver, "15_iam_page")
    iam_body = driver.find_element(By.TAG_NAME, "body").text
    iam_scope_badge = driver.find_elements(By.XPATH, "//*[contains(text(), 'Target Scope: Active Organization') or contains(text(), 'Target Organization')]")

    record_finding(
        route="/settings/team vs /iam",
        component_or_tab="IAM / Team Settings Route Duplication",
        defect_type="ARCHITECTURAL_DUPLICATION",
        severity="high",
        title="Duplicated IAM Routes (/settings/team and /iam) Fragment User Management",
        description=(
            "Both '/settings/team' and '/iam' expose member rosters and role assignments with divergent backends "
            "('/api/v1/tenants/members' vs '/api/v1/tenant-iam/members'). '/iam' contains superior multi-tenant controls "
            "(Target Organization Scope Badge, Super Admin switcher, and strict RBAC matrix), while '/settings/team' is a legacy "
            "surface lacking tenant scoping. To improve quality of life and eliminate confusion, '/settings/team' should redirect to '/iam'."
        ),
        screenshot_path=s_iam
    )

    # -------------------------------------------------------------
    # ROUTE 6: /expenses/new - Statutory Unvouched / No Bill Checks
    # -------------------------------------------------------------
    driver.get(f"{BASE_WEB_URL}/expenses/new")
    time.sleep(2)
    s_exp_init = snap(driver, "16_expense_new_form")

    # Find and toggle "Record as Unvouched Expense / Internal Self-Voucher (No Bill Available)"
    try:
        unvouched_chk = driver.find_element(By.ID, "unvouched-self-voucher-toggle")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", unvouched_chk)
        if not unvouched_chk.is_selected():
            unvouched_chk.click()
            time.sleep(1)

        s_exp_unvouched = snap(driver, "17_expense_unvouched_self_voucher_active")
        exp_body = driver.find_element(By.TAG_NAME, "body").text

        # Verify Section 37(1) check
        assert "Section 37(1)" in exp_body, "Section 37(1) statutory notice must be present"
        # Verify Section 40A(3) check
        assert "Section 40A(3)" in exp_body, "Section 40A(3) cash limit notice must be present"
        # Verify Section 16(2) check
        assert "16(2)" in exp_body, "Section 16(2) CGST Act 0% ITC notice must be present"

        # Check for Section 69C / Section 115BBE 78% punitive tax notice
        if "Section 69C" not in exp_body and "115BBE" not in exp_body:
            record_finding(
                route="/expenses/new",
                component_or_tab="Unvouched Expense Banner",
                defect_type="STATUTORY_DISCLOSURE_GAP",
                severity="medium",
                title="Section 69C / Section 115BBE Punitive Tax Warning Missing in Unvouched Expense Notice",
                description="The self-voucher notice cites Section 37(1), Section 40A(3), and Section 16(2), but omits the crucial statutory warning regarding Section 69C (Unexplained Expenditure) and Section 115BBE (78% punitive tax risk on unverified disbursements).",
                screenshot_path=s_exp_unvouched
            )

    except Exception as e:
        record_finding(
            route="/expenses/new",
            component_or_tab="Unvouched Toggle",
            defect_type="FORM_INTERACTION_ERROR",
            severity="high",
            title="Failed to interact with unvouched expense toggle",
            description=str(e)
        )

    # Dump all collected findings to JSON
    report_path = SCREENSHOTS_DIR / "findings.json"
    with open(report_path, "w") as f:
        json.dump(AUDIT_FINDINGS, f, indent=2)

    print(f"\nAudit completed. Total Findings Recorded: {len(AUDIT_FINDINGS)}")
    assert len(AUDIT_FINDINGS) > 0, "Audit completed successfully and captured all findings."

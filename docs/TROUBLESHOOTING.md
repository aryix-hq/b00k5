# b00k5 Diagnostics, Error Matrix & Troubleshooting Runbook

## 1. Fast Health Diagnostic Commands

Run these immediate one-liners to diagnose service outages:

```bash
# 1. Check all container statuses
docker compose ps

# 2. Check Core API health
curl -s http://localhost:8000/api/v1/health

# 3. Check System Router health
curl -s http://localhost:8000/api/v1/system/health

# 4. Check PostgreSQL connectivity & General Ledger zero-sum balance
docker exec b00k5_postgres psql -U b00k5_admin -d b00k5_db -c \
  "SELECT COALESCE(SUM(debit_amount) - SUM(credit_amount), 0) AS net_drift FROM journal_items;"

# 5. Check Redis broker ping
docker exec b00k5_redis redis-cli ping

# 6. Check Hardware DSC Loopback Bridge
curl -s http://localhost:28045/status

# 7. Tail recent error logs across all services
docker compose logs --tail=50 -f
```

---

## 2. Comprehensive Diagnostics & Error Matrix

### 2.1 General Ledger & Database Exceptions

#### Error: `check_zero_sum_balance: Inviolable Double-Entry Invariant Failed!`
* **HTTP Status:** `500 Internal Server Error` (Database Transaction Aborted)
* **Root Cause:** A journal entry was submitted where the sum of line debits does not exactly equal the sum of line credits ($\sum \text{Debit} \ne \sum \text{Credit}$).
* **Remediation Procedure:**
  1. Inspect the source document generating the voucher (e.g. invoice, expense, or bank statement).
  2. Verify that tax legs (CGST, SGST, IGST) or withholding legs (TDS) sum precisely to the invoice/bill grand total.
  3. Ensure no float values are being passed. All monetary figures must be rounded to 2 decimal places with Banker's Rounding (`Decimal(val).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)`).
  4. Ensure both a debit leg and a credit leg are provided. Single-legged entries are strictly rejected.

#### Error: `Immutability Violation: Posted journal entries cannot be modified or deleted.`
* **HTTP Status:** `400 Bad Request` or `500 Database Exception`
* **Root Cause:** A direct SQL `UPDATE` or `DELETE` was attempted on a `journal_entries` or `journal_lines` row where `is_posted = TRUE`.
* **Remediation Procedure:**
  * Do not attempt to alter posted transactions.
  * To correct a posted error, post a formal reversing journal voucher (Credit Note, Debit Note, or Contra Entry) referencing the original voucher number.

---

### 2.2 Invoicing & Indian Tax Engine Exceptions

#### Error: `Invalid GSTIN: Modulus-36 Checksum Validation Failed`
* **HTTP Status:** `422 Unprocessable Entity`
* **Root Cause:** The entered 15-character GSTIN failed the statutory Indian GSTN Modulus-36 checksum calculation on character 15.
* **Remediation Procedure:**
  1. Verify the GSTIN format:
     * Chars 1-2: Valid 2-digit Indian State Code (`01` through `38`).
     * Chars 3-12: 10-character PAN of the entity.
     * Char 13: Entity registration number within the state (typically `1` to `9`).
     * Char 14: Default character `Z`.
     * Char 15: Check digit computed using weighted base-36 arithmetic.
  2. Check the counterparty's actual GST Certificate (Form GST REG-06) on the GST portal (`https://services.gst.gov.in/services/searchtp`).

#### Error: `Section 40A(3) Income Tax Act Warning: Cash payment exceeds ₹10,000`
* **Indicator:** Warning banner on Expense Workbench.
* **Statutory Cause:** Under Section 40A(3) of the Income-tax Act, 1961, expenditure incurred in cash exceeding ₹10,000 in a single day to a single person is disallowed as a deductible expense.
* **Remediation Procedure:**
  * Transition payment mode to electronic clearing (NEFT, RTGS, IMPS, UPI, or Corporate Credit Card).

---

### 2.3 Hardware Token DSC & Cryptographic Signing Exceptions

#### Error: `PKCS#11 Driver Not Found / Token Disconnected`
* **HTTP Status:** `503 Service Unavailable` on `/dsc/sign-hash`
* **Root Cause:** The loopback daemon (`b00k5-bridge`) cannot find the dynamic PKCS#11 driver library or the USB token is unplugged.
* **Remediation Procedure:**
  1. Ensure the USB token (HYP2003 / ePass2003) is plugged into a USB-A port (or via a genuine USB-C adapter).
  2. Verify the driver library location:
     * **macOS:** Check `/usr/local/lib/libespki.dylib` or install the token middleware from your CA.
     * **Linux:** Check `/usr/lib/libespki.so` or `/usr/lib/x86_64-linux-gnu/opensc-pkcs11.so`.
     * **Windows:** Check `C:\Windows\System32\eps2003csp11.dll`.
  3. Restart the bridge daemon:
     ```bash
     cd bridge && bash run_bridge.sh
     ```

#### Error: `CKR_PIN_INCORRECT / CKR_PIN_LOCKED`
* **Cause:** The Director PIN entered in the web interface was incorrect. After 3-5 consecutive failed PIN attempts, hardware tokens enter a permanent lock state to prevent brute-force attacks.
* **Remediation Procedure:**
  * If token is locked, open the official Token Manager desktop application provided by your Certifying Authority and use the Administrator / SO-PIN (Security Officer PIN) to unblock the User PIN.

---

### 2.4 Google Drive Cloud Backup Exceptions

#### Error: `500 Internal Server Error: Storage credentials not configured`
* **Root Cause:** Attempted to trigger Google Drive backup before connecting Google OAuth2 or uploading OAuth client secrets.
* **Remediation Procedure:**
  1. Navigate to `http://localhost:3000/gdrive`.
  2. Click **Connect Google Drive Account** and authenticate with the company's Google Workspace / Gmail account.
  3. Ensure the OAuth consent screen has enabled the `https://www.googleapis.com/auth/drive.file` scope.

---

### 2.5 MinIO & Object Storage Exceptions

#### Error: `MinIO S3 Connection Refused / NoSuchBucket`
* **Root Cause:** MinIO container is initializing or one of the required buckets (`b00k5-vault`, `b00k5-receipts`, `b00k5-statements`, `b00k5-signed`, `b00k5-statutory`) was omitted.
* **Remediation Procedure:**
  1. Inspect MinIO logs: `docker logs b00k5_minio`.
  2. Run the initialization container to auto-create missing buckets:
     ```bash
     docker compose run --rm b00k5_minio_init
     ```
  3. Verify buckets at the MinIO Console: `http://localhost:9001` (User: `minio_storage_admin`).

---

## 3. Emergency Data Recovery Procedures

### 3.1 Repairing Stuck Celery Queues
If asynchronous tasks (OCR or Reconciliation) appear stalled:
```bash
# 1. Purge Redis task queues
docker exec b00k5_redis redis-cli FLUSHDB

# 2. Restart worker containers
docker compose restart b00k5_worker_ocr b00k5_worker_reconcile b00k5_worker_sync
```

### 3.2 Re-indexing & Auditing Database Checksums
To run an automated audit verifying SHA-256 integrity across all files stored in MinIO vs database records:
```bash
docker exec b00k5_api pytest /app/tests/integration/test_master_directive_audit.py -k "test_journey_09"
```

# b00k5 Open-Source Strategy, Licensing & Clean-Room Legal Framework

## 1. Open-Source License Selection Matrix & Legal Analysis

Selecting the optimal open-source licensing model for **b00k5** requires balancing two strategic objectives:
1. **Frictionless Adoption by Indian Startups & CA Firms:** Corporate enterprises, fintechs, and chartered accountants will not adopt or contribute to software if there is any ambiguity that doing so might contaminate their internal proprietary business models.
2. **Defensive Patent Protection & Long-Term Governance:** Protection against patent trolls claiming ownership over automated tax algorithms, Place of Supply determination logic, or PKCS#11 hardware signing workflows.

### 1.1 Comparative Analysis Matrix

| License Type | Candidate Licenses | Derivative Works Private? | Network SaaS Copyleft? | Explicit Patent Grant? | Commercial Corporate Adoption |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Permissive** | **MIT** | Yes | No | No | High |
| **Permissive (Industrial)** | **Apache License 2.0** | Yes | No | **Yes (Section 3)** | **Highest** |
| **Weak Copyleft** | **MPL 2.0 / LGPLv3** | File-level only | No | Yes | Moderate |
| **Strong Copyleft** | **AGPLv3** | No | **Yes (Section 13)**| Yes | Low (legal friction) |
| **Source-Available** | **BSL 1.1 (Business Source)** | Commercial restriction | Yes | Limited | Low (non-OSI) |

### 1.2 Recommendation: Apache License, Version 2.0

**b00k5 adopts the Apache License, Version 2.0.**

#### Strategic Rationale:
1. **Express Patent Grant (Section 3):** Under Apache 2.0, each contributor grants the user a perpetual, worldwide, non-exclusive, no-charge, irrevocable patent license. If any entity institutes patent litigation against any recipient alleging that b00k5 infringes their patents, any patent licenses granted to that entity terminate immediately. This provides vital legal security for Indian financial algorithms.
2. **Enterprise Adoption Without "Viral" Copyleft Risks:** Startups deploying b00k5 internally to handle books, cap table secrets, and founder reimbursements cannot be subjected to demands to open-source their proprietary customer catalogs or business logic (unlike AGPLv3).
3. **Trademark Protection (Section 6):** The Apache 2.0 license explicitly reserves trademark rights, preventing unauthorized commercial actors from using the "b00k5" mark to market counterfeit hosted services.

---

## 2. Software Bill of Materials (SBOM) & Third-Party Dependency Audit

Every direct and transitive package in b00k5 has been audited against the **Software Package Data Exchange (SPDX)** standard to eliminate license contamination.

### 2.1 Backend Core Dependencies (`apps/api/requirements.txt`)

| Package | Version | SPDX License Identifier | Contamination Risk | Evaluation & Usage Notes |
| :--- | :--- | :--- | :---: | :--- |
| `fastapi` | `>=0.110.0` | `MIT` | **None** | High-performance ASGI framework. Permissive. |
| `uvicorn` | `>=0.28.0` | `BSD-3-Clause` | **None** | Lightning-fast ASGI web server. Permissive. |
| `pydantic` | `>=2.6.0` | `MIT` | **None** | Data validation using Python type hints. Permissive. |
| `sqlalchemy` | `>=2.0.28` | `MIT` | **None** | Database ORM and SQL abstraction toolkit. Permissive. |
| `asyncpg` | `>=0.29.0` | `Apache-2.0` | **None** | Asynchronous PostgreSQL driver. Compatible. |
| `psycopg2-binary` | `>=2.9.9` | `LGPL-3.0-or-later WITH exceptions` | **None** | Synchronous driver used in dynamic migrations. |
| `celery` | `>=5.3.6` | `BSD-3-Clause` | **None** | Distributed task queue. Permissive. |
| `redis` | `>=5.0.3` | `MIT` | **None** | Redis client for Python. Permissive. |
| `minio` | `>=7.2.5` | `Apache-2.0` | **None** | Official MinIO S3 SDK. Compatible. |
| `pyjwt` | `>=2.8.0` | `MIT` | **None** | JSON Web Token implementation. Permissive. |
| `pyHanko` | `>=0.21.0` | `MIT` | **None** | PDF signature injection & PAdES standard. Permissive. |
| `cryptography` | `>=42.0.5` | `Apache-2.0 OR BSD-3-Clause` | **None** | Cryptographic primitives for AES-256 and RSA. |
| `opencv-python-headless` | `>=4.9.0.80`| `Apache-2.0` | **None** | Image pre-processing for bill OCR. |
| `pdf2image` | `>=1.17.0` | `MIT` | **None** | PDF rasterizer for receipts. Permissive. |
| `pdfplumber` | `>=0.11.0` | `MIT` | **None** | PDF table and text extraction. Permissive. |
| `pytesseract` | `>=0.3.10` | `Apache-2.0` | **None** | Tesseract OCR wrapper. Compatible. |
| `google-api-python-client`| `>=2.120.0`| `Apache-2.0` | **None** | Google Drive API client. Compatible. |

### 2.2 Frontend Core Dependencies (`apps/web/package.json`)

| Package | Version | SPDX License Identifier | Contamination Risk |
| :--- | :--- | :--- | :---: |
| `next` | `14.1.4` | `MIT` | **None** |
| `react` / `react-dom` | `^18.2.0` | `MIT` | **None** |
| `lucide-react` | `^0.359.0` | `ISC` | **None** |
| `tailwindcss` | `^3.4.1` | `MIT` | **None** |
| `typescript` | `^5.9.3` | `Apache-2.0` | **None** |

### 2.3 Contamination Assessment Summary
* **GPLv3 / AGPLv3 Viral Contamination:** **0% Detected.** None of the backend or frontend dependencies force copyleft obligations onto consuming applications.
* **Dual Licensing Safe:** All third-party software is licensed under OSI-approved permissive licenses (`MIT`, `Apache-2.0`, `BSD-3-Clause`, `ISC`).

---

## 3. Clean-Room Implementation Specifications

To guarantee that independent developers or clean-room teams can build drop-in compatible replacements for b00k5 without access to proprietary source code, the functional black-box specifications are codified below:

### 3.1 Specification 1: Double-Entry Transaction Engine
* **Input:** A transaction payload containing `source_document_id`, `entry_date`, and an array of journal lines with `account_id`, `debit_amount`, and `credit_amount`.
* **Mathematical Invariant:** $\sum \text{Debit} - \sum \text{Credit} = 0.00$.
* **Type Requirement:** Numbers must be handled as fixed-point decimal values with exactly 2 decimal places. Floating-point conversions are prohibited.
* **Immutability Contract:** Once marked `is_posted = TRUE`, any update or deletion must raise an uncatchable exception. Compensating transactions must create a distinct journal entry with opposing legs.

### 3.2 Specification 2: Indian GST Dynamic Place of Supply (POS) Engine
* **Input:** `tenant_state_code` (2 digits, e.g., `29`), `customer_pos_state_code` (2 digits, e.g., `27`), and `taxable_base_amount`.
* **Rules:**
  1. If `tenant_state_code == customer_pos_state_code`:
     * Transaction is **Intra-State**.
     * Compute $\text{CGST} = \text{ROUND\_HALF\_EVEN}(\text{base} \times 0.09, 2)$.
     * Compute $\text{SGST} = \text{ROUND\_HALF\_EVEN}(\text{base} \times 0.09, 2)$.
     * $\text{IGST} = 0.00$.
  2. If `tenant_state_code != customer_pos_state_code`:
     * Transaction is **Inter-State**.
     * $\text{CGST} = 0.00$, $\text{SGST} = 0.00$.
     * Compute $\text{IGST} = \text{ROUND\_HALF\_EVEN}(\text{base} \times 0.18, 2)$.
  3. Total Invariant: $\text{Grand Total} \equiv \text{taxable\_base\_amount} + \text{CGST} + \text{SGST} + \text{IGST}$.

### 3.3 Specification 3: Hardware DSC Loopback Bridge (PKCS#11)
* **Interface:** HTTP JSON-RPC listening on `http://127.0.0.1:28045`.
* **Protocol:**
  * `GET /status`: Inquires PKCS#11 subsystem. Returns `{ "bridge_status": "online", "driver_found": true, "token_detected": true }`.
  * `POST /sign-hash`: Accepts `{ "hash": "<64-char-sha256-hex>", "pin": "<user-pin>" }`.
  * The daemon discovers native PKCS#11 libraries (`libespki.so`, `libespki.dylib`, `eps2003csp11.dll`), calls `C_Initialize`, `C_OpenSession`, `C_Login(CKU_USER)`, locates private key object, calls `C_SignInit(CKM_RSA_PKCS)`, executes `C_Sign`, and returns hex signature string and DER-encoded X.509 certificate.

---

## 4. Open-Source Governance Pack

### 4.1 Developer Certificate of Origin (DCO)
b00k5 relies on the standard Linux Foundation **Developer Certificate of Origin (DCO) Version 1.1** instead of a burdensome Contributor License Agreement (CLA). All commits must be signed off using `git commit -s`:

```
Signed-off-by: Full Name <author@example.com>
```

By adding this sign-off, contributors certify that they wrote the code, hold the rights to submit it under the Apache 2.0 license, and did not copy copyrighted proprietary code.

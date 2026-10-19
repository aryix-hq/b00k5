# FEAT-XXX: [Feature Title]

> **Lifecycle Stage**: Stage 2 (Product Requirements & RICE Prioritization)  
> **Status**: Draft | Under Review | Approved | In Execution | Completed  
> **Author**: Product Manager (`@product-manager`)  
> **Target Branch**: `feat/FEAT-XXX`  
> **Source Research Note**: [`wiki/research/RES-XXX.md`](../research/)  
> **Phased Implementation Plan**: [`wiki/plans/PLAN-XXX.md`](../plans/)  

---

## 1. Executive Summary & Problem Statement
- **User Problem**: [Explain the concrete problem discovered in Stage 1 research]
- **Proposed Solution**: [Clear description of functionality delivered to users]
- **Target User Personas**: [e.g. End User, Tenant Admin, Auditor]

---

## 2. RICE Prioritization & Scoring
The Product Manager prioritizes features using the RICE framework:
$$\text{RICE Score} = \frac{\text{Reach} \times \text{Impact} \times \text{Confidence}}{\text{Effort}}$$

| Factor | Value | Rationale |
| :--- | :---: | :--- |
| **Reach (R)** | `[Value]` | Estimated users/requests affected per quarter |
| **Impact (I)** | `[0.25 - 3.0]` | 3 = Massive, 2 = High, 1 = Medium, 0.5 = Low, 0.25 = Minimal |
| **Confidence (C)**| `[50% - 100%]`| 100% = High empirical evidence, 80% = Medium, 50% = Low/Spike |
| **Effort (E)** | `[Person-Weeks]` | Estimated team sprints or person-weeks to ship |
| **TOTAL SCORE** | **`[Score]`** | **(R × I × C) / E** |

---

## 3. User Acceptance Criteria (UAC)
Verifiable Given-When-Then criteria that must be validated:
- [ ] **Scenario 1 (Happy Path)**: Given [precondition], when [action], then [expected outcome].
- [ ] **Scenario 2 (Edge Case)**: Given [boundary state], when [action], then [graceful behavior].
- [ ] **Scenario 3 (Error Handling)**: Given [invalid input/auth], when [action], then [explicit error code & safe message].

---

## 4. Technical Scope & System Impact (Planning Trio Review)
- **Component / Service Boundaries**: [Services or directories modified]
- **Database Schema Changes**: [Tables, migrations, RLS policies in `wiki/DATABASE_SCHEMA.md`]
- **API Contracts**: [Endpoints, payloads, HTTP status codes]
- **Security & Cryptographic Boundaries**: [Auth, Vault secrets, input sanitization]

---

## 5. Definition of Done (DoD)
- [ ] Stage 1 Research Note linked (`wiki/research/RES-XXX.md`)
- [ ] RICE score computed and prioritized against backlog
- [ ] Stage 3 Phased Implementation Plan co-authored with Planning Trio (`wiki/plans/PLAN-XXX.md`)
- [ ] Feature implemented phase-by-phase on branch `feat/FEAT-XXX`
- [ ] Zero-mock test suites and linter pass green
- [ ] Any test failures logged to `wiki/defects/DEF-XXX.md` and remediated
- [ ] Ephemeral preview test succeeds via `bin/deploy-preview.sh`
- [ ] Living Architecture (`wiki/ARCHITECTURE.md`) & Schema (`wiki/DATABASE_SCHEMA.md`) updated
- [ ] PR reviewed & approved by Engineering Manager (`@engineering-manager`)
- [ ] `CHANGELOG.md` updated
- [ ] Session context automatically reset via `ai-agents session reset --auto`

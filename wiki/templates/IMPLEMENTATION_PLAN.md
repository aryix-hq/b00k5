# PLAN-{{ID}}: {{TITLE}}

> **Initiative**: {{INITIATIVE_NAME}}  
> **Status**: [PENDING / IN_PROGRESS / COMPLETED]  
> **Target Branch**: `feat/{{BRANCH_NAME}}`  
> **Created**: {{DATE}}  
> **Planning Trio Sign-off**:
> - [ ] Product Manager (`@product-manager`)
> - [ ] System Architect (`@architect`)
> - [ ] Technical Project Manager (`@project-manager`)

---

## 1. Executive Summary & Objective
Brief summary of the business goal, user impact, and technical scope.

---

## 2. Living Phase & Milestone Tracker

| Phase | Description | Owner | Target Date | Status | PR Link |
| :---: | :--- | :--- | :---: | :---: | :---: |
| **Phase 1** | Contract Definition, ADR & DB Schema | `@architect`, `@database-architect` | YYYY-MM-DD | `[PENDING]` | - |
| **Phase 2** | Core API & Backend Implementation | `@fullstack-developer` | YYYY-MM-DD | `[PENDING]` | - |
| **Phase 3** | Frontend Components & UI/UX | `@ui-ux`, `@fullstack-developer` | YYYY-MM-DD | `[PENDING]` | - |
| **Phase 4** | Zero-Mock Testing & Defect Remediation | `@qa` | YYYY-MM-DD | `[PENDING]` | - |
| **Phase 5** | Ephemeral Preview Deploy & EM Gate | `@devops-sre`, `@engineering-manager`| YYYY-MM-DD | `[PENDING]` | - |

---

## 3. Associated Living Artifacts
All linked artifacts must be kept continuously up to date as phases progress:
- **Feature Specification**: [`wiki/features/FEAT-{{ID}}.md`](../features/)
- **System Architecture**: [`wiki/ARCHITECTURE.md`](../ARCHITECTURE.md)
- **Database Schema**: [`wiki/DATABASE_SCHEMA.md`](../DATABASE_SCHEMA.md)
- **Active Defects**: [`wiki/defects/`](../defects/)

---

## 4. Phase Execution Details & Deliverables

### Phase 1: Foundation & Contracts
- [ ] Requirements validated against RICE priority.
- [ ] ADR authored in `wiki/adr/` if new patterns or dependencies are introduced.
- [ ] Schema changes documented in `wiki/DATABASE_SCHEMA.md`.

### Phase 2: Implementation (Local Ollama Worker)
- [ ] Local Ollama (`qwen2.5-coder:14b`) executes code drafting via `bin/local-coder.sh`.
- [ ] Syntax check passed (`tsc --noEmit`, `node --check`).

### Phase 3: Testing & Defect Logging
- [ ] Live zero-mock test suite passed.
- [ ] Any test failures logged to `wiki/defects/DEF-XXX.md`.

### Phase 4: Preview Build & Sign-off
- [ ] Ephemeral container build verified via `./bin/deploy-preview.sh`.
- [ ] Changelog updated in `CHANGELOG.md`.
- [ ] Final EM sign-off granted.

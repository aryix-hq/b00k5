# FEAT-XXX: [Feature Title]

- **Status**: Draft | Under Review | In Progress | Ready for QA | Completed
- **Author**: [Product Manager / Developer Name]
- **Target Branch**: `feat/FEAT-XXX`
- **RICE Score**: Reach: [X] | Impact: [X] | Confidence: [X] | Effort: [X] -> Score: [Total]

## 1. Problem Statement & User Value
[Explain the concrete problem this solves for the user, business, or system.]

## 2. User Acceptance Criteria (UAC)
- [ ] Given [precondition], when [action], then [expected outcome].
- [ ] Given [invalid state], when [action], then [error handling outcome].

## 3. Technical & Architectural Specification
- **Affected Services / Files**:
- **Database Schema Changes**:
- **API Endpoints**:
- **Security Considerations**:

## 4. Definition of Done (DoD)
- [ ] Implementation complete on branch `feat/FEAT-XXX`
- [ ] Local syntax check passes (`node --check` / `tsc --noEmit` / `py_compile`)
- [ ] Ephemeral preview test succeeds via `bin/deploy-preview.sh`
- [ ] PR submitted with `PULL_REQUEST_TEMPLATE.md`
- [ ] Engineering Manager approval granted
- [ ] `CHANGELOG.md` updated
- [ ] Session state reset cleanly via `ai-agents session reset --feature FEAT-XXX`


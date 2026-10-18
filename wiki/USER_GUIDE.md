# Living User Guide & Feature Manual

> **Custodians**: Client & Customer Advocate (`@client-advocate`) & Product Manager (`@product-manager`)  
> **Status**: Living User Manual  
> **Last Synchronized**: 2026-10-17  

This document provides user-facing documentation, feature walkthroughs, command references, and best practices for developing with the `ai-agents` enterprise system.

---

## 1. Quick Navigation & Daily Workflows

### Starting Work on a New Ticket
1. **Check the Sprint Board**: Review `wiki/TASK_BOARD.md` for prioritized tickets.
2. **Review Feature Spec**: Read the specification in `wiki/features/FEAT-XXX.md`.
3. **Create Branch**: `git checkout -b feat/FEAT-XXX`.
4. **Trigger Architectural Review** (if modifying schemas or contracts):
   > *"@orchestrator-debate run an adversarial review on FEAT-XXX with @architect and @ciso"*

---

## 2. Testing & Verification Guide
Before requesting Engineering Manager approval:
```bash
# Run isolated branch preview verification (syntax, secrets, container health)
./bin/deploy-preview.sh feat/FEAT-XXX 8080 --test-and-exit
```

---

## 3. Submitting a Pull Request
1. Ensure `CHANGELOG.md` is updated following Keep a Changelog standards.
2. Ensure live docs (`wiki/ARCHITECTURE.md`, `wiki/DATABASE_SCHEMA.md`, `wiki/DEPLOYMENT.md`) reflect any structural changes.
3. Open a PR using `PULL_REQUEST_TEMPLATE.md`.
4. Request review:
   > *"@engineering-manager please review PR for FEAT-XXX and grant merge approval."*

---

## 4. Resetting Session Context
When a ticket is merged:
```bash
ai-agents session reset --feature FEAT-XXX
```
Open a fresh chat window for the next ticket to maintain maximum model reasoning precision.


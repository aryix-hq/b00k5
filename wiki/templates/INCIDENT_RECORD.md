# INC-XXX: [Incident Title]

- **Status**: Investigating | Identified | Mitigated | Resolved | Post-Mortem Complete
- **Severity**: SEV-1 (Critical Outage) | SEV-2 (Major Impairment) | SEV-3 (Minor Degrade)
- **Incident Commander / Lead**: [DevOps / SRE / EM]
- **Impacted Services**: [API / Database / Frontend / Worker]
- **Date & Duration**: [YYYY-MM-DD | Duration: XX mins]

## 1. Incident Summary & User Impact
- **What Happened**: [Concise non-technical description of the event.]
- **Customer Blast Radius**: [Percentage of tenants/users impacted, failed transactions, error rates.]

## 2. Incident Timeline (UTC)
- `HH:MM` - Anomaly detected via telemetry alert or customer report.
- `HH:MM` - Incident response channel opened; lead assigned.
- `HH:MM` - First diagnostic mitigation attempted.
- `HH:MM` - Root cause identified.
- `HH:MM` - Fix deployed or traffic rerouted; service restored.
- `HH:MM` - Incident closed; monitoring in place.

## 3. Root Cause Analysis (5 Whys)
1. **Why did the failure occur?**
2. **Why was that component compromised?**
3. **Why did the safeguard / alert not catch it earlier?**
4. **Why was the configuration or code committed?**
5. **Why was the root invariant missing?**

## 4. Remediation & Preventive Action Items
| Action Item | Owner | Target Date | Status | Linked Ticket |
| :--- | :--- | :--- | :--- | :--- |
| Add circuit breaker to upstream API | Fullstack | YYYY-MM-DD | Open | `fix/DEF-XXX` |
| Add container memory limit alerts | DevOps SRE | YYYY-MM-DD | In Progress | `wiki/features/FEAT-XXX.md` |
| Update deployment runbook | Scribe | YYYY-MM-DD | Completed | `wiki/DEPLOYMENT.md` |

## 5. Audit & Sign-off History
- [ ] Post-mortem approved by Engineering Manager (`@engineering-manager`)
- [ ] Security impact reviewed by CISO (`@ciso`)
- [ ] Incident logged in historical ledger and `CHANGELOG.md`


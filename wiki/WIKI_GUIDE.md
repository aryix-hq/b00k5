# Project Wiki & Tracking Guide

> **Core Principle**: Zero Random Coding. Every line of code written in this repository must map to a tracked Feature Spec (`wiki/features/`), Defect Record (`wiki/defects/`), Incident Report (`wiki/incidents/`), or Vulnerability Disclosure (`wiki/vulnerabilities/`).

## Wiki Directory Structure
```
wiki/
├── ARCHITECTURE.md       # Live system topology & invariants (Maintained by @architect)
├── DATABASE_SCHEMA.md    # Live entity schemas, migrations & RLS (Maintained by @database-architect)
├── DEPLOYMENT.md         # Live container runbooks & preview deploy guide (Maintained by @devops-sre)
├── FAQS.md               # Live troubleshooting & operational FAQs (Maintained by @documentation-manager)
├── USER_GUIDE.md         # Live user flows, API usage & manuals (Maintained by @client-advocate & @pm)
├── TASK_BOARD.md         # Active Sprint & Kanban Status
├── features/             # Feature specs with full history (FEAT-001.md, FEAT-002.md...)
├── defects/              # Defect investigations with RCA & verification (DEF-001.md...)
├── incidents/            # Outage reports, 5-Whys post-mortems & timeline (INC-001.md...)
├── vulnerabilities/      # Security disclosures & CISO remediation proof (VULN-001.md...)
├── adr/                  # Architecture Decision Records (ADR-001.md...)
├── ops/                  # Infrastructure operational runbooks
└── templates/            # Standard templates for all records
```

## Workflow: From Idea to Merged Code
1. **Spec Creation**: Product Manager or developer creates `wiki/features/FEAT-XXX.md` using the Feature Spec template.
2. **Review & Debate**: Orchestrator runs adversarial debate; Architect signs off in `wiki/adr/`.
3. **Branching**: Developer creates branch `feat/FEAT-XXX` or `fix/DEF-XXX`.
4. **Implementation & Preview Test**: Local Ollama / Flash worker implements code; runs `./bin/deploy-preview.sh`.
5. **Live Documentation Sync**: Appropriate agents update `ARCHITECTURE.md`, `DATABASE_SCHEMA.md`, `DEPLOYMENT.md`, `FAQS.md`, or `USER_GUIDE.md`.
6. **PR & EM Approval**: Full `PULL_REQUEST_TEMPLATE.md` submitted; EM reviews and approves.
7. **Session Reset & Wiki Closeout**: Ticket marked completed, changelog updated, session reset.

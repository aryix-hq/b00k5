# Living Deployment & Operations Runbook

> **Custodian**: DevOps & Site Reliability Engineer (`@devops-sre`)  
> **Status**: Living Deployment Specification  
> **Last Synchronized**: 2026-10-17  

This document details container configurations, preview deployment lifecycles, healthchecks, environment variables, and zero-downtime release procedures.

---

## 1. Safe Branch Preview Deploy Strategy

The deployment engine (`bin/deploy-preview.sh`) guarantees that feature work is built and verified in ephemeral containers without touching `main`.

### Usage
```bash
# Preview current branch on default port (8080)
./bin/deploy-preview.sh

# Deploy specific branch on custom port
./bin/deploy-preview.sh feat/FEAT-042 8090

# Test-and-exit mode (used in CI/CD and pre-PR verification)
./bin/deploy-preview.sh feat/FEAT-042 8090 --test-and-exit
```

---

## 2. Environment & Container Naming Convention

Container names are strictly differentiated to prevent collisions between production and branch previews:

| Environment | Branch | Container Name Pattern | Example |
| :--- | :--- | :--- | :--- |
| **Production** | `main` / `master` | `<project>-main-<port>` | `ai-agents-main-8080` |
| **Branch Preview** | `feat/*`, `fix/*` | `<project>-preview-<branch-slug>-<port>` | `ai-agents-preview-feat-feat-042-8090` |

---

## 3. Environment Variables & Secret Management

| Variable Name | Purpose | Required In | Default / Example |
| :--- | :--- | :---: | :--- |
| `PORT` | HTTP Server port | All | `8080` |
| `NODE_ENV` | Runtime environment (`production` / `development`) | All | `production` |
| `DATABASE_URL` | PostgreSQL connection string | Prod & Preview | `postgresql://app:pass@db:5432/app` |
| `OLLAMA_HOST` | Local Ollama inference daemon endpoint | Worker / Dev | `http://127.0.0.1:11434` |

---

## 4. Healthcheck & Rollback Runbook
* **Health Endpoint**: `GET /healthz` (Must respond within 200ms with HTTP 200).
* **Rollback Trigger**: If healthcheck fails 3 consecutive times post-deploy, trigger automatic rollback to previous container tag.


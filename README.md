<p align="center">
  <img src="frontend/public/syn_logo_traced.svg" alt="syn logo" width="120" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat&logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/FastAPI-0.115%2B-009688?style=flat&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=flat&logo=react&logoColor=white" alt="React 19" />
  <img src="https://img.shields.io/badge/TypeScript-6-3178C6?style=flat&logo=typescript&logoColor=white" alt="TypeScript 6" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white" alt="Docker" />
  <img src="https://img.shields.io/badge/license-MIT-yellow?style=flat" alt="MIT License" />
  <img src="https://img.shields.io/badge/AMD_ACT_II-Unicorn_Track-ED1C24?style=flat&logo=amd&logoColor=white" alt="AMD ACT II Hackathon" />
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat" alt="PRs Welcome" />
</p>

# syn — AI Action Firewall

**Deterministic, session-aware governance for AI agent tool calls.**

syn sits between an AI agent and the tools it calls, intercepting every action and scoring it against six risk factors. Each tool call is **approved**, **escalated** (to a human), or **blocked** — with a full audit trail, plain-English explanation, and regulatory tagging.

The LLM **never** makes or influences decisions. It only generates explanations from abstracted numeric scores.

---

## The Problem

Every AI agent today can call real-world tools — send payments, delete files, query databases. There is no security checkpoint. If the agent is compromised, confused, or simply wrong, the damage is instant.

Existing governance tools evaluate one call at a time. They cannot correlate individually-low-risk actions into a dangerous sequence (e.g., `check_balance` → `check_balance` → `check_balance` → `send_payment`). This is a known unsolved gap in the field.

**syn's thesis:** Governance must be **deterministic** (not an LLM judgment call), **session-aware** (not per-action-only), and **privacy-preserving** (the AI sees only abstracted scores, never raw content).

---

## Architecture

```
Agent / Client
    │
    │ POST /intercept
    ▼
┌─────────────────────┐
│  FastAPI Gateway     │  (port 8000)
│                      │
│  ┌─────────────────┐ │
│  │  Risk Engine     │ │  6 deterministic factors
│  │  (evaluate.py)   │ │  + decision tree floors
│  │                  │ │  + session pattern matching
│  └─────────────────┘ │  + weighted blend → final decision
│                      │
│  ┌─────────────────┐ │
│  │  Audit Store     │ │  SQLite-backed audit trail
│  │  (audit.py)      │ │
│  └─────────────────┘ │
│                      │
│  ┌─────────────────┐ │
│  │  LLM Client      │ │  Mock / OpenAI / Groq / Fireworks
│  │  (llm.py)        │ │  (explanations only, no decisions)
│  └─────────────────┘ │
│                      │
│  ┌─────────────────┐ │
│  │  Slack Notifier  │ │  Webhook for escalated actions
│  │  (slack.py)      │ │
│  └─────────────────┘ │
└──────┬──────────────┘
       │
       ▼
┌─────────────────┐
│  React Frontend  │  (port 5173 dev / 3000 prod)
│  TrustReceipt    │  Decision result UI
│  BootstrapReview │  AI-generated policy review UI
│  Timeline        │  Audit trail explorer
└─────────────────┘
```

---

## Decision Pipeline

Applied in **strict order** so critical violations can never be averaged away:

### 1. Decision Tree Floors
| Condition | Result |
|-----------|--------|
| severity > 90 | BLOCKED |
| policy >= 100 | BLOCKED |
| data_sensitivity >= 70 | ESCALATED |
| confidence < 40 | ESCALATED |

### 2. Session Branches
| Condition | Result |
|-----------|--------|
| N-action risky sequence matched | ESCALATED |
| Cumulative severity > 70 (30-min window) | ESCALATED |

### 3. Weighted Blend (if no trigger above)
| Score | Result |
|-------|--------|
| < 30 | APPROVED |
| 30 – 55 | ESCALATED |
| ≥ 55 | BLOCKED |

**Weights:** severity 0.30, policy 0.20, tool_trust 0.20, data_sensitivity 0.15, anomaly 0.10, confidence 0.05

---

## Key Features

- **Six deterministic factors** — severity, policy, anomaly (z-score), data sensitivity (regex), confidence (history), tool trust (tier-based)
- **Session-aware risk scoring** — N-action subsequence matching (e.g., `check_balance` → `send_payment`), sliding-window cumulative severity, gateway-issued session IDs with time-bucket fallback
- **Decision tree floors** — hard thresholds applied before any blend, preventing critical violations from being averaged away
- **AI Bootstrap** — auto-generates security policy rules from tool schemas via LLM, with a review/diff/approve UI; unknown tools trigger background rule generation
- **Regulatory tagging** — EU AI Act tiers (Unacceptable/High/Limited/Minimal Risk) + US regime flags (FINRA, SEC)
- **Config-swappable LLM** — Mock / Local / OpenAI / Groq / Fireworks via single env var
- **Audit trail** — SQLite-backed timeline with outcome filtering
- **Slack notifications** — escalated actions posted to Slack with rollback plan
- **Dockerized** — two containers (gateway + frontend), one `docker compose up`

---

## Quick Start

### Prerequisites
- Python ≥ 3.11, Node.js, or Docker

### Docker
```bash
docker compose up --build
```
- Gateway: `http://localhost:8000`
- Frontend: `http://localhost:3000`

### Local (backend)
```bash
cp .env.example .env
python -m venv venv
venv\Scripts\activate     # Windows
pip install -r requirements.txt
uvicorn gateway.main:app --host 0.0.0.0 --port 8000
```

### Local (frontend)
```bash
cd frontend
npm install
npm run dev
```

### Tests
```bash
pytest tests/ -v
```

### Environment Variables
| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_PROVIDER` | `mock` | Provider: mock / local / openai / groq / fireworks |
| `LLM_BASE_URL` | per-provider | API base URL |
| `LLM_API_KEY` | — | API key |
| `LLM_MODEL` | per-provider | Model name |
| `LLM_TIMEOUT` | per-provider | Timeout in seconds |
| `SYN_SLACK_WEBHOOK_URL` | — | Slack webhook for escalations |
| `SYN_RATE_LIMIT` | 100 | Max req/min/IP |
| `SYN_AUDIT_RETENTION_DAYS` | 90 | Audit log retention |

---

## Demo: Four Actions That Tell the Story

```http
POST /intercept
```

| # | Tool | Params | Result | Why |
|---|------|--------|--------|-----|
| 1 | `check_balance` | `{"account_id": "123"}` | ✅ Approved | Low severity, no policy issue |
| 2 | `check_balance` | `{"account_id": "123"}` | ✅ Approved | Same — individually fine |
| 3 | `check_balance` | `{"account_id": "123"}` | ✅ Approved | Still fine on its own |
| 4 | `send_payment` | `{"amount": 500, "currency": "USD"}` | ⚠️ **Escalated** | Session pattern matched: `check_balance` → `send_payment` |

Each of the first three actions is low-risk. Together they form a dangerous reconnaissance-to-execution pattern that only **session-aware** governance can catch.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python + FastAPI + Uvicorn |
| Risk Engine | Pure Python (deterministic, no ML) |
| Database | SQLite |
| Frontend | React 19 + TypeScript + Vite |
| LLM Providers | OpenAI, Groq, Fireworks, Local, Mock |
| Container | Docker + Docker Compose + nginx |

---

## License

MIT — see `LICENSE`.

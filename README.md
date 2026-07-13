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

**Project reference:** AMD ACT II Hackathon, Unicorn Track · Submitted July 13, 2026

---

## AMD Infrastructure Usage

This project uses AMD-approved compute in two distinct places, not just as a checkbox:

- **Local inference on AMD Developer Cloud, via ROCm.** The anomaly-detection factor — one of the six risk factors below — is scored by a Qwen model served locally on an AMD Developer Cloud GPU instance using ROCm. This is real local inference contributing to the actual risk decision, not a demo-only integration. If the local model is ever unavailable, the system falls back to a statistical z-score scorer so the pipeline never has a single point of failure.
- **Fireworks AI (hosted on AMD hardware) for explanation and remediation.** After the deterministic engine reaches a decision, Fireworks generates the plain-English explanation and remediation text shown in the Trust Receipt UI. Fireworks never sees raw action content — only abstracted numeric scores (see [Privacy-preserving by design](#design-decisions) below) — and never influences the decision itself.

**Where to look in the code:** `engine/anomaly.py` (local model + statistical fallback), `engine/llm.py` (Fireworks client), `engine/llm_config.yaml` (provider config — set `provider: fireworks` for the judged/demo configuration; `mock`/`groq` are for local development only, to avoid burning API quota while iterating).

---

## The Problem

Every AI agent today can call real-world tools — send payments, delete files, query databases. There is no security checkpoint. If the agent is compromised, confused, or simply wrong, the damage is instant.

Most governance tools score one action at a time. That misses sequences where individually low-risk actions add up to something dangerous — three balance checks followed by a large payment, for instance. syn scores both the individual action and the session pattern, and it does the whole thing with deterministic code, not an LLM judgment call.

**syn's thesis:** governance must be **deterministic** (not an LLM decision), **session-aware** (not per-action-only), and **privacy-preserving** (the AI sees only abstracted scores, never raw content).

---

## Architecture

```
Agent / Client
    │
    │ POST /intercept
    ▼
                     ┌──────────────────────┐
                     │  Qwen on ROCm         │
                     │  (AMD Developer Cloud)│
                     │  anomaly reasoning    │
                     └──────────┬───────────┘
                                │ feeds the anomaly factor
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

The decision never leaves the machine. The anomaly factor is computed by Qwen, served locally on AMD Developer Cloud via ROCm — real local GPU inference contributing to the actual decision, not just a required-stack checkbox. Fireworks (or whichever LLM provider is configured for explanations) only ever receives abstracted numeric scores after the decision is already made — never raw action content, amounts, recipients, or file paths.

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

- **Six deterministic factors** — severity, policy, anomaly (Qwen running locally on AMD Developer Cloud via ROCm, with a statistical z-score fallback), data sensitivity (regex), confidence (history), tool trust (tier-based)
- **Session-aware risk scoring** — N-action subsequence matching (e.g., `check_balance` → `send_payment`), sliding-window cumulative severity, gateway-issued session IDs with time-bucket fallback
- **Decision tree floors** — hard thresholds applied before any blend, preventing critical violations from being averaged away
- **AI Bootstrap** — auto-generates security policy rules from tool schemas via LLM, with a review/diff/approve UI; unknown tools trigger background rule generation
- **Regulatory tagging** — EU AI Act tiers (Unacceptable/High/Limited/Minimal Risk) + US regime flags (FINRA, SEC)
- **Config-swappable LLM** — Mock / Local / OpenAI / Groq / Fireworks via a single env var
- **Audit trail** — SQLite-backed timeline with outcome filtering
- **Slack notifications** — escalated actions posted to Slack with a rollback plan
- **Dockerized** — two containers (gateway + frontend), one `docker compose up`

---

## Where to Look

| What | File |
|---|---|
| Risk engine orchestration | `engine/evaluate.py` |
| Decision tree floors + session branches + weighted blend | `engine/decision_tree.py` |
| Session pattern matching | `engine/session.py` |
| Anomaly factor (local Qwen model + statistical fallback) | `engine/anomaly.py` |
| Regulatory tier mapping | `engine/regulatory.py`, `engine/regulatory_mapping.yaml` |
| Fireworks / LLM client (explanations only) | `engine/llm.py`, `engine/llm_config.yaml` |
| Gateway API (intercept, bootstrap, resolve, timeline) | `gateway/main.py` |
| Audit trail | `engine/audit.py` |
| Trust Receipt UI | `frontend/src/TrustReceipt.tsx` |

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
# source venv/bin/activate  # Linux/Mac
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
| `LLM_PROVIDER` | `fireworks` | Provider: mock / local / openai / groq / fireworks — set to `fireworks` for submission/judging so the required AMD-hosted stack is actually used |
| `LLM_BASE_URL` | per-provider | API base URL |
| `LLM_API_KEY` | — | API key |
| `LLM_MODEL` | per-provider | Model name |
| `LLM_TIMEOUT` | per-provider | Timeout in seconds |
| `SYN_SLACK_WEBHOOK_URL` | — | Slack webhook for escalations |
| `SYN_RATE_LIMIT` | 100 | Max req/min/IP |
| `SYN_AUDIT_RETENTION_DAYS` | 90 | Audit log retention |

> **Note:** `mock` and `groq` are convenient for local development and iterating without burning API quota, but the submitted/judged deployment should run with `LLM_PROVIDER=fireworks` — that's what satisfies the hackathon's required-stack rule, since Fireworks hosts models on AMD hardware.

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

Each of the first three actions is low-risk on its own. Together they form a reconnaissance-to-execution pattern that only session-aware governance catches.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python + FastAPI + Uvicorn |
| Risk Engine | Pure Python (deterministic, no ML) |
| Database | SQLite |
| Frontend | React 19 + TypeScript + Vite |
| LLM Providers | Fireworks (AMD-hosted, required stack), OpenAI, Groq, Local, Mock |
| Local Inference | Qwen on AMD Developer Cloud (ROCm) — powers the anomaly factor |
| Container | Docker + Docker Compose + nginx |

---

## Design Decisions

### Deterministic over LLM-based decisions
Every risk factor is computed with pure Python — no ML, no LLM judgment calls. The LLM only generates plain-English explanations from already-computed numeric scores. This gives reproducible, auditable decisions that don't shift with model updates or prompt injection: in a safety-critical governance layer, the thing that decides whether an action executes should be predictable, not probabilistic.

### Session-aware, not just per-call
Scoring individual actions in isolation misses multi-step patterns — e.g., three balance checks followed by a large payment. syn tracks sessions via gateway-issued IDs with a time-bucket fallback, enabling N-action subsequence matching and sliding-window cumulative severity. This isn't a claim that no other tool does anything like it — some governance and security platforms do correlate agent behavior across actions. What syn does differently is make that correlation a native, always-on field on every decision object from day one, sitting directly alongside the deterministic per-action score, rather than a separate module bolted on later.

### Local inference for anomaly detection, with a statistical fallback
The anomaly factor is scored by Qwen running locally on AMD Developer Cloud via ROCm, comparing each incoming action against recent history for that agent. This is deliberately kept off the critical path for the rest of the pipeline: severity, policy, data sensitivity, confidence, and tool trust are all pure rule-based code with zero GPU dependency, and a statistical z-score scorer is built and tested as the working default before the local model is wired in. That means the anomaly factor is never a single point of failure for the demo — if the local model is unavailable for any reason, the system falls back to the statistical version and every other factor is unaffected.

### Decision tree floors before weighted blend
Hard thresholds (severity > 90 → BLOCKED, data_sensitivity ≥ 70 → ESCALATED) are applied before the weighted blend. This prevents a critical violation from being averaged away by low scores on other factors — some rules should be absolute, not blended into a nuanced score.

### Privacy-preserving by design
The LLM never sees raw action parameters — only abstracted numeric scores (e.g., `severity:82, policy:70, anomaly:30`) and an action-type category. Sensitive data (account IDs, amounts, recipient names) never leaves the gateway. This is a concrete, verifiable claim: read `fireworks_layer/explain_and_remediate.py` and confirm for yourself that raw parameters never enter the prompt.

### SQLite over PostgreSQL
A single-file database keeps deployment trivial (no external DB server) and is sufficient for the audit-trail workload at hackathon scale. The schema is designed so migration to PostgreSQL is a one-line connection-string change.

### Separate gateway + frontend
The gateway exposes a REST API that any agent framework can call directly. The frontend is a separate consumer of that API, not a monolith — syn can sit in front of LangChain, CrewAI, AutoGen, or any custom agent without a browser in the loop.

---

## Why This Matters

AI agents are being deployed in production today — banking, healthcare, DevOps, customer support — with no runtime security layer for the actions they take, not just the text they generate.

**Grounding for the problem statement:**
- OWASP's Top 10 for LLM Applications (2025) includes **Excessive Agency (LLM06)** as a top-tier risk: agents granted more functionality, permissions, or autonomy than their task requires. OWASP's companion **Top 10 for Agentic Applications** (December 2025) adds **Tool Misuse & Exploitation (ASI02)** specifically for the tool-calling attack surface this project addresses.
- The EU AI Act's high-risk AI system obligations take effect **August 2026** — organizations deploying agents in finance, healthcare, and HR have a matter of weeks, not months, to demonstrate governance controls.
- A Cloud Security Alliance survey of 228 IT and security professionals (published March 2026) found that 68% of organizations cannot clearly distinguish between human and AI agent activity, and only 18% are confident their identity and access systems can handle agent identities.

syn is a small, fully legible implementation of that governance layer: deterministic scoring, session awareness, and privacy-preserving explanations, all readable end-to-end in a single sitting.

---

## Future Plans

### Near-term
- Real-time Slack approval workflows — interactive buttons to approve/escalate/block, with a configurable timeout
- PostgreSQL backend for production-scale audit trails
- Policy-as-code — version-controlled YAML policies with CI/CD validation
- Additional regulatory regime flags — GDPR, SOX, HIPAA, PCI-DSS

### Medium-term
- Multi-signal session detection — combine rule-based sequence matching with statistical and learned detectors to catch a wider range of patterns
- Agent framework SDKs — drop-in middleware for LangChain, CrewAI, AutoGen, and the OpenAI Assistants API
- Distributed audit store for multi-instance deployments

### Long-term
- Policy-as-code registry with diff preview and rollback
- Federated, opt-in sharing of anonymized risk patterns across organizations
- On-device governance for air-gapped environments
- Adversarial sequence testing to probe for blind spots in session pattern coverage

---

## Repo Structure

```
syn/
├── docker-compose.yml
├── gateway/              # FastAPI app: health, intercept, bootstrap, resolve, timeline
├── engine/               # Risk factors, decision tree, session logic, LLM client, audit store
├── frontend/             # React + Vite + TypeScript UI
├── tests/                # pytest suite
└── docs/                 # PRD, decision log, project reference
```

---

## License

MIT

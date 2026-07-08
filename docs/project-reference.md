# syn — AI Action Firewall

**Project reference**

- **Track:** AMD ACT II Hackathon — Unicorn Track
- **Submission deadline:** July 11, 2026, 15:00 UTC
- **Repo:** `https://github.com/not3zra/syn`

---

## Overview

syn is a **deterministic, session-aware governance layer** that sits between an AI agent and the tools it calls. Every tool call is intercepted, scored against six risk factors, checked against session history for risky patterns, and either **approved**, **escalated** (to a human), or **blocked** — with a full audit trail and plain-English explanation.

**Key principle:** The LLM never makes or influences decisions. It only generates explanations from abstracted numeric scores.

---

## Architecture

```
AI Agent / Client
       │
       │ POST /intercept
       ▼
┌─────────────────┐
│   gateway/       │  FastAPI server (port 8000)
│   main.py        │
│                  │
│  ┌─────────────┐ │
│  │  engine/     │ │  6 risk factors + decision tree
│  │  evaluate.py │ │
│  └─────────────┘ │
│         │        │
│  ┌─────────────┐ │
│  │  audit.py    │ │  SQLite audit store (data/audit.db)
│  └─────────────┘ │
│         │        │
│  ┌─────────────┐ │
│  │  llm.py      │ │  Mock / Groq / Fireworks (config-swappable)
│  └─────────────┘ │
│         │        │
│  ┌─────────────┐ │
│  │  slack.py    │ │  Slack webhook for escalations
│  └─────────────┘ │
└─────────────────┘
         │
         │ Vite proxy (dev) or nginx (prod)
         ▼
┌─────────────────┐
│  frontend/       │  React + Vite + TypeScript (port 5173 / 3000)
│  TrustReceipt    │  Decision result UI
│  BootstrapReview │  AI Bootstrap workflow UI
└─────────────────┘
```

---

## Project Structure

```
syn/
├── .env                    # Local env vars (gitignored)
├── .env.example            # Template
├── .gitignore
├── docker-compose.yml      # Gateway + Frontend containers
├── pyproject.toml           # Python deps + config
├── requirements.txt         # pip install
├── README.md
├── handoff.md               # Agent handoff notes
│
├── gateway/
│   ├── __init__.py
│   ├── main.py              # FastAPI app (health, intercept, bootstrap, resolve, timeline)
│   └── Dockerfile           # Python 3.12-slim
│
├── engine/
│   ├── __init__.py
│   ├── evaluate.py           # Risk engine orchestrator
│   ├── models.py             # Dataclasses: Decision, FactorScores, SessionData, RiskEngineResult
│   ├── severity.py           # Severity scoring per tool type
│   ├── policy.py             # Policy rule matching
│   ├── anomaly.py            # z-score anomaly detection
│   ├── data_sensitivity.py   # Regex-based sensitivity scoring
│   ├── confidence.py         # Historical confidence scoring
│   ├── tool_trust.py         # Trust tier scoring
│   ├── decision_tree.py      # Hard floors + weighted blend
│   ├── session.py            # Session IDs, sequence detection, cumulative severity
│   ├── regulatory.py         # EU AI Act tier + US regime flags
│   ├── audit.py              # SQLite audit store
│   ├── llm.py                # LLM client abstraction (Mock, Fallback/Groq, Fireworks)
│   ├── bootstrap.py          # AI Bootstrap: introspection, generation, YAML, validation
│   ├── execution.py          # Tool execution stub
│   ├── slack.py              # Slack webhook notifier
│   ├── policy_config.yaml          # Base tool security profiles
│   ├── policy_config.bootstrap.yaml # Bootstrap-generated rules (gitignored)
│   ├── regulatory_mapping.yaml      # EU AI Act + US regime triggers
│   ├── risky_sequences.yaml         # Ordered pair session patterns
│   └── llm_config.yaml              # LLM provider config
│
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── Dockerfile           # Multi-stage: node build → nginx serve
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx           # Main app (Intercept mode + Bootstrap mode)
│   │   ├── App.css
│   │   ├── index.css
│   │   ├── types.ts          # TS interfaces
│   │   ├── TrustReceipt.tsx   # Decision result UI
│   │   ├── RiskGauge.tsx     # Visual risk gauge
│   │   ├── FactorBreakdown.tsx  # 6-factor breakdown
│   │   ├── BootstrapReview.tsx  # AI Bootstrap workflow
│   │   ├── ExpiryTimer.tsx   # Escalation countdown
│   │   └── assets/
│   └── public/
│
├── data/
│   └── audit.db              # SQLite audit database (gitignored)
│
├── tests/
│   ├── test_audit.py
│   ├── test_bootstrap.py
│   ├── test_docker.py
│   ├── test_e2e_smoke.py
│   ├── test_factors.py
│   ├── test_gateway.py
│   ├── test_live_api_verification.py
│   ├── test_llm.py
│   ├── test_regulatory.py
│   ├── test_risk_engine.py
│   ├── test_session.py
│   └── test_slack.py
│
└── docs/
    ├── prd.md                 # Product Requirements Document
    ├── decision-log.md        # Design decision log
    └── project-reference.md   # This file
```

---

## Setup & Running

### Prerequisites

- Python >= 3.11
- Node.js (for frontend)
- Docker (optional, for containerized run)

### Environment Variables

```bash
# Copy and edit
cp .env.example .env
```

```ini
# LLM provider — pick one:
FIREWORKS_API_KEY="fw_..."
GROQ_API_KEY="gsk_..."

# Optional — Slack webhook for escalations:
SYN_SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
```

### LLM Provider Config

Edit `engine/llm_config.yaml`:

```yaml
# Options: mock | groq | fireworks
provider: groq
model: llama-3.3-70b-versatile
```

| Provider | API Key Env Var | Free Tier |
|----------|----------------|-----------|
| `mock`   | None needed    | Unlimited |
| `groq`   | `GROQ_API_KEY` | 100K tokens/day |
| `fireworks` | `FIREWORKS_API_KEY` | Higher limits |

### Run with Docker

```bash
docker compose up --build
```

- Gateway: `http://localhost:8000`
- Frontend: `http://localhost:3000`

### Run without Docker

**Backend:**

```bash
python -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
uvicorn gateway.main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend** (separate terminal):

```bash
cd frontend
npm install
npm run dev
```

Vite dev server on `http://localhost:5173` (proxies `/intercept`, `/tools`, `/health` to port 8000).

### Run Tests

```bash
venv\Scripts\activate
pytest tests/ -v
```

---

## API Reference

### `GET /health`

Health check. Returns `{"status": "ok"}`.

### `GET /tools`

List registered tools with their schemas.

```json
[
  {
    "name": "send_payment",
    "description": "Send a payment to a recipient",
    "parameters": {
      "amount": {"type": "number", "description": "Payment amount"},
      "currency": {"type": "string", "description": "Currency code"},
      "recipient": {"type": "string", "description": "Recipient identifier"}
    }
  }
]
```

### `POST /intercept`

Main endpoint — evaluate a tool call.

**Request:**

```json
{
  "action_type": "send_payment",
  "parameters": { "amount": 100, "currency": "USD", "recipient": "alice" },
  "agent_id": "demo-123",
  "mode": "live"
}
```

- `mode`: `"live"` (executes, writes to SQLite, sends Slack) or `"simulation"` (evaluates only)

**Response:**

```json
{
  "decision": "approved",
  "trigger": "weighted_score:approved:18.5",
  "factor_scores": { "severity": 20, "policy": 0, "anomaly": 0, "data_sensitivity": 0, "confidence": 50, "tool_trust": 100 },
  "session_data": { "session_id": "demo-123:172000", "cumulative_severity": 0, "pattern_matched": false },
  "regulatory_tier": "minimal_risk",
  "us_regime_flags": ["FINRA", "SEC"],
  "action_type": "send_payment",
  "parameters_abstracted": { "amount_category": "low", "recipient_type": "internal" },
  "timestamp": "2026-07-08T22:00:00Z",
  "explanation": "...",
  "remediation": "...",
  "simulation": false,
  "execution": { "action": "send_payment", "params": {...}, "status": "success" },
  "rollback_plan": null,
  "expires_at": null
}
```

### `POST /bootstrap/introspect`

AI Bootstrap — introspect tools and generate policy rules.

**Request:**

```json
{
  "manual_schemas": [
    {
      "name": "send_email",
      "description": "Send an email",
      "parameters": { "to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"} }
    }
  ]
}
```

Alternatively, provide `api_base` to auto-fetch from MCP `tools/list`.

**Response:**

```json
{
  "schemas": [...],
  "rules": [...],
  "yaml": "tools:\n  send_email:\n    ...",
  "valid": true,
  "errors": []
}
```

### `POST /bootstrap/approve`

Approve and write generated YAML to disk.

**Request:**

```json
{
  "yaml_content": "tools:\n  send_email:\n    ...",
  "target_path": null
}
```

If `target_path` is null, defaults to `engine/policy_config.bootstrap.yaml`.

**Response:**

```json
{ "success": true, "path": "C:\\...\\policy_config.bootstrap.yaml" }
```

### `POST /resolve/{entry_id}`

Resolve an escalated action.

**Request:**

```json
{ "outcome": "approved" }
```

or `"denied"`. If approved, the tool is executed.

### `GET /timeline`

List audit log entries. Optional `?outcome=approved|escalated|blocked` filter.

---

## Risk Engine

### Six Factors

| Factor | Range | Description |
|--------|-------|-------------|
| **severity** | 0-100 | Inherent risk of the action (amount, path, query type) |
| **policy** | 0-100 | Violation of explicit policy rules |
| **anomaly** | 0-100 | Deviation from historical patterns (z-score) |
| **data_sensitivity** | 0-100 | Sensitivity of data accessed (regex patterns) |
| **confidence** | 0-100 | How often this action has been seen before |
| **tool_trust** | 0-100 | Trust tier of the tool (official/verified/unknown/unsigned) |

### Decision Tree (Hard Floors)

Applied before weighted scoring — these override everything:

| Condition | Decision |
|-----------|----------|
| `severity > 90` | **BLOCKED** |
| `policy >= 100` | **BLOCKED** |
| `confidence < 40` | **ESCALATED** |

### Session Branches

| Condition | Decision |
|-----------|----------|
| Pattern match (e.g., `check_balance` → `send_payment`) | **ESCALATED** |
| Cumulative severity > 70 | **ESCALATED** |

### Weighted Scoring

If no hard floor or session branch triggers:

| Weighted Score | Decision |
|----------------|----------|
| < 30 | **APPROVED** |
| 30 - 55 | **ESCALATED** |
| >= 55 | **BLOCKED** |

Weights: `severity: 0.30, policy: 0.20, tool_trust: 0.20, data_sensitivity: 0.15, anomaly: 0.10, confidence: 0.05`

### Decision Priority

```
Session branches (pattern match / cumulative threshold)
  → Decision tree floors (severity / policy / confidence)
    → Weighted score
```

---

## Demo Scenarios

### Beat 4 — Session Pattern Matching (the core differentiator)

Run these 4 calls in sequence in **LIVE** mode with the same `agent_id`:

| # | Tool | Parameters | Expected |
|---|------|-----------|----------|
| 1 | `check_balance` | `{"account_id": "123"}` | ✅ approved |
| 2 | `check_balance` | `{"account_id": "123"}` | ✅ approved |
| 3 | `check_balance` | `{"account_id": "123"}` | ✅ approved |
| 4 | `send_payment` | `{"amount": 500, "currency": "USD", "recipient": "alice"}` | ⚠️ escalated (trigger: `session:pattern_matched:check_balance_send_payment`) |

### Basic Scenarios

| Scenario | Tool | Parameters | Expected |
|----------|------|-----------|----------|
| Low-risk approval | `send_payment` | `{"amount": 100, "currency": "USD", "recipient": "alice"}` | ✅ approved |
| Policy violation | `send_payment` | `{"amount": 10000, "currency": "USD", "recipient": "bob"}` | 🚫 blocked |
| Severity floor | `send_payment` | `{"amount": 99999, "currency": "USD", "recipient": "bob"}` | 🚫 blocked |
| Destructive query | `query_database` | `{"query": "DROP TABLE users"}` | 🚫 blocked |
| Low confidence | `delete_file` | `{"file_path": "/etc/shadow"}` | ⚠️ escalated |
| Unknown tool | `unknown_tool` | `{}` | 🚫 blocked |

### AI Bootstrap

1. Select **Bootstrap** mode in the frontend
2. Click **Introspect** (uses mock schemas or custom JSON)
3. Review generated rules in the table
4. Edit YAML if needed
5. Click **Approve** → writes `policy_config.bootstrap.yaml`
6. Switch to **Intercept** mode → the bootstrapped tool is no longer blocked

---

## Configuration Files

### `engine/llm_config.yaml`

```yaml
provider: groq       # mock | groq | fireworks
model: llama-3.3-70b-versatile
```

### `engine/policy_config.yaml` (Base Tool Profiles)

```yaml
tools:
  send_payment:
    severity_rules:
      - max_amount: 1000; score: 20
      - max_amount: 5000; score: 50
      - max_amount: 50000; score: 80
      - max_amount: null; score: 95
    policy_rules:
      - description: "No payments above $5,000 to external recipients"
        condition: { field: amount, operator: ">", value: 5000 }
        score: 100
    tool_trust_tier: official
    anomaly_lookback: 20

thresholds:
  weighted_score:
    approve_max: 30.0
    escalate_min: 30.0
    escalate_max: 55.0
    block_min: 55.0

decision_tree:
  severity_floor: 90.0
  confidence_floor: 40.0

weights:
  severity: 0.30
  policy: 0.20
  anomaly: 0.10
  data_sensitivity: 0.15
  confidence: 0.05
  tool_trust: 0.20
```

### `engine/risky_sequences.yaml`

```yaml
sequences:
  - pair: ["check_balance", "send_payment"]
    severity: 80
  - pair: ["query_database", "delete_file"]
    severity: 90
  - pair: ["query_database", "send_payment"]
    severity: 85
  - pair: ["read_file", "send_email"]
    severity: 75
  - pair: ["query_database", "update_database"]
    severity: 70
```

### `engine/regulatory_mapping.yaml`

Maps EU AI Act Articles (Article 5 prohibited practices, Article 6 high-risk, Article 52 limited-risk) and US regime flags (FINRA, SEC) to action types and risk scores.

---

## Regulatory Tiers

| Tier | EU AI Act | Trigger |
|------|-----------|---------|
| `unacceptable_risk` | Article 5 | Exhaustive list (social scoring, biometric categorization, subliminal manipulation, exploitation) |
| `high_risk` | Article 6 | Unknown tool + high severity, high data sensitivity, or financial/biometric action types |
| `limited_risk` | Article 52 | Chatbot, emotion recognition, deepfake action types |
| `minimal_risk` | Default | Everything else |

Plus US regime flags: `FINRA`, `SEC` for financial action types.

---

## Decision Log Summary

| # | Decision | Hackathon Choice | Ideal |
|---|----------|-----------------|-------|
| 1 | Session ID source | Auto-generated time buckets (10-min) | Agent-provided explicit IDs |
| 2 | Sequence matching | Ordered pairs (A→B) | N-action chains with gap tolerance |
| 3 | Cumulative severity | Simple sum, threshold=70 | Decay-weighted sum |
| 4 | AI Bootstrap input | One-time introspection | Continuous auto-registration |
| 5 | Bootstrap prompt | Hardcoded fintech context | Dynamic context from vector store |
| 6 | Bootstrap review | Minimal table + "Approve All" | Per-tool staged approval with diff |
| 7 | Slack integration | Incoming webhook (post-only) | Full Slack app with interactive buttons |
| 8 | Database | SQLite | PostgreSQL |

Full details in `docs/decision-log.md`.

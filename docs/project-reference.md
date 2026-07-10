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
│  │  llm.py      │ │  Mock / Groq / Fireworks / Local (config-swappable)
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
│   ├── main.py              # FastAPI app (health, /health/llm, intercept, bootstrap, resolve, timeline)
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
│   ├── policy_config.bootstrap.yaml # Bootstrap-generated rules (tracked; reset to `tools: {}` between demos via `POST /admin/reset`)
│   ├── regulatory_mapping.yaml      # EU AI Act + US regime triggers
│   ├── risky_sequences.yaml         # Ordered pair session patterns
│   └── llm_config.yaml              # LLM provider config
│
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── Dockerfile           # Multi-stage: node build → nginx serve
│   ├── nginx.conf          # Nginx config: serves static build, proxies `/intercept`, `/tools`, `/health`, `/bootstrap`, `/resolve`, `/admin`, `/timeline` to `gateway:8000`
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
│   ├── test_admin_reset.py
│   ├── test_audit.py
│   ├── test_bootstrap.py
│   ├── test_demo_auth.py
│   ├── test_docker.py
│   ├── test_e2e_smoke.py
│   ├── test_factors.py
│   ├── test_frontend_demo_token.py
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
    ├── project-reference.md   # This file
    └── slide-deck.md          # Pitch presentation slide deck
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
# LLM provider — all providers use the same LLM_* env vars
LLM_PROVIDER=mock
# LLM_BASE_URL=http://localhost:8000/v1
# LLM_API_KEY=...
# LLM_MODEL=...
# LLM_TIMEOUT=15
# LLM_MAX_RETRIES=2
# LLM_TEMPERATURE=0.3
# LLM_MAX_TOKENS=3000

# Optional — Slack webhook for escalations:
SYN_SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
```

### Runtime Security / Hardening (env vars)

These controls were added in the post-submission hardening pass:

| Env Var | Default | Purpose |
|----------|---------|---------|
| `SYN_RATE_LIMIT` | `100` | Max requests per IP per window (`SYN_RATE_LIMIT_WINDOW_SECONDS`, default 60s). Rate-limited on all paths except `GET /health`. Keyed on the real TCP peer, **not** client-supplied `X-Forwarded-For`/`X-Real-IP`. |
| `SYN_MAX_BODY_SIZE` | `1048576` (1 MB) | Max request body. Enforced for both `Content-Length` and chunked transfer encoding. |
| `SYN_ALLOW_ORIGINS` | `*` | CORS allowed origins. Returned as-is; `Access-Control-Allow-Credentials` is **disabled** (do not enable with `*`). |
| `SYN_AUDIT_RETENTION_DAYS` | `90` | Audit rows older than this are purged automatically on each `/intercept`. |
| `SYN_AUDIT_DB_PATH` | `data/audit.db` | SQLite audit DB location. |

Other behaviors:
- **Startup health probe:** the gateway probes the LLM on startup via `client.models.list()` (OpenAI SDK), caching `LLMStatus` with latency. `GET /health` exposes the cached status; `GET /health/llm` forces a fresh probe.
- **LLM timeout + fail-fast:** LLM calls time out after `timeout_seconds` (per-provider default, overridable via `LLM_TIMEOUT`). Bootstrap generation is token-heavy (~2500 tokens) and the `local` provider defaults to 120s. LLM calls run in a thread pool so the event loop is not blocked.
- **Request IDs:** every request gets a UUID `X-Request-ID` and structured logs are tagged with it.
- **Bootstrap path sanitization:** `POST /bootstrap/approve` resolves `target_path` inside the engine config directory and rejects directory traversal.
- **Prompt sanitization:** user-influenced values (`action_type`, `trigger`, `tool_name`) are JSON-escaped before LLM prompt interpolation to block prompt injection.
- **SSRF guard:** `POST /bootstrap/introspect` rejects an `api_base` that is non-HTTP(S) or resolves to a private/loopback/link-local/reserved/multicast address. Use `manual_schemas` for localhost or internal MCP servers.

### Known residual risks (pre-production)

- **No authentication/RBAC** on any endpoint, including `/resolve/{entry_id}` (executes a tool on approval) and `/bootstrap/approve*` (writes policy files). Acceptable for the hackathon; required before production. A throwaway `X-Demo-Token` tripwire gates mutating endpoints but is not real auth.
- **Fresh `agent_id` evasion:** rotating `agent_id` per action bypasses session/sequence tracking. Mitigated only by authentication. Per-visit randomized `agent_id` (#13) stops accidental cross-visit history bleed.
- **Behind a trusted proxy:** when deployed behind a reverse proxy, the rate limiter must be changed to trust `X-Forwarded-For` from that proxy only (currently it uses the raw peer).
- **Bootstrap persistence writes the committed baseline (deferred, #30):** approved bootstraps write to the git-tracked `policy_config.bootstrap.yaml`; use `POST /admin/reset` to restore `tools: {}` between demo sessions. A gitignored runtime override is planned.

### LLM Provider Config

All providers use the same `OpenAIAPIClient` class — only the defaults differ:

```yaml
# engine/llm_config.yaml — all values overridable via LLM_* env vars
provider: local
model: Qwen/Qwen3-8B
timeout_seconds: 120.0
```

| Provider | Default Base URL | Default Model | Use Case |
|----------|-----------------|---------------|----------|
| `mock` | N/A | N/A | Testing, offline demo |
| `local` | `http://localhost:8000/v1` | `Qwen/Qwen3-8B` | AMD Developer Cloud, vLLM, local |
| `openai` | `https://api.openai.com/v1` | `gpt-5` | Production OpenAI |
| `groq` | `https://api.groq.com/openai/v1` | `openai/gpt-oss-120b` | Low-volume, free tier |
| `fireworks` | `https://api.fireworks.ai/inference/v1` | `accounts/fireworks/models/glm-5p2` | Higher throughput |

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
uvicorn gateway.main:app --host 0.0.0.0 --port 8000
```

**Frontend** (separate terminal):

```bash
cd frontend
npm install
npm run dev
```

Vite dev server on `http://localhost:5173` (proxies `/intercept`, `/tools`, `/health`, `/bootstrap`, `/resolve`, `/admin`, `/timeline` to port 8000). In Docker, `nginx.conf` provides equivalent proxy rules for the production build.

### Run Tests

```bash
venv\Scripts\activate
pytest tests/ -v
```

---

## API Reference

### `GET /health`

Health check. Returns `{"status": "ok"}` with cached LLM status.

### `GET /health/llm`

Forces a fresh LLM probe. Returns live `LLMStatus` including `healthy`, `latency_ms`, and `provider`. Gateway status stays `"ok"` even when LLM is unreachable — the deterministic engine works without an LLM.

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

Applied **before session branches** — floors are checked first so policy violations cannot be downgraded by session context:

| Condition | Decision |
|-----------|----------|
| `severity > 90` | **BLOCKED** |
| `policy >= 100` | **BLOCKED** |
| `data_sensitivity >= 70` | **ESCALATED** |
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
Decision tree floors (severity / policy / confidence / data_sensitivity)
  → Session branches (pattern match / cumulative threshold)
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
2. Click **Introspect tools** (uses registered tools) or **Manual JSON** (paste custom schemas in the inline textarea)
3. Review generated rules (policy descriptions bulleted, LLM reasoning shown)
4. Review **Diff vs current config** to see additions/changes
5. Edit the full YAML in the editable textarea if needed
6. Click **Approve and write config** → written to `policy_config.bootstrap.yaml`
7. Switch to **Intercept** mode → the bootstrapped tool is no longer blocked

**Unknown tools:** When an unknown tool is called in Live mode, the gateway blocks it and auto-generates rules in the background. Navigate to the **Pending approvals** tab to see generation status (`generating…` → edit/approve/reject when ready).

---

## Configuration Files

### `engine/llm_config.yaml`

```yaml
provider: fireworks       # mock | groq | fireworks
model: accounts/fireworks/models/glm-5p2
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
  data_sensitivity_floor: 70.0
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
  - actions: ["check_balance", "send_payment"]
    severity: 80
  - actions: ["query_database", "delete_file"]
    severity: 90
  - actions: ["query_database", "send_payment"]
    severity: 85
  - actions: ["read_file", "send_email"]
    severity: 75
  - actions: ["query_database", "update_database"]
    severity: 70
  - actions: ["check_balance", "query_database", "send_payment"]
    severity: 95
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
| 9 | Session ID source (revised) | Agent-managed lifecycle with gateway-issued IDs, time-bucket fallback | Same |
| 10 | Sequence matching (revised) | N-action subsequence matching, unlimited gap tolerance | Configurable gap tolerance |
| 11 | Cumulative severity (revised) | Agent-wide sliding time window (30 min), simple sum | Decay-weighted sum |
| 12 | AI Bootstrap input | Continuous auto-registration on unknown tool with pending review queue | Same, with auto-rollback |
| 13 | Bootstrap prompt | Dynamic context from `domain_config.yaml` | Vector store over policy docs |
| 27 | Session-id spoofability | Harmless — `session_id` is audit-only, scoring uses `agent_id` | Authenticate the agent |
| 28 | Data-sensitivity escalation floor | `data_sensitivity_floor: 70.0` in `decision_tree` | Per-factor floors on every axis |
| 29 | Confidence as non-decaying trust | `confidence` only increases, never decays within retention window | Decay-weighted, authenticated confidence |
| 30 | Bootstrap runtime override | Deferred — writes to tracked file; reset via `POST /admin/reset` | Separate gitignored override file |
| 32–38 | Bootstrap UX hardening | Inline textarea, generating status, rule descriptions, pending editing, LCS diff, increased LLM timeout, introspect fallback | Side-by-side diff, SSE push, streaming LLM |

Full details in `docs/decision-log.md`.

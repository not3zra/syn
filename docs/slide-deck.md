# syn — AI Action Firewall

## Slide Deck / Pitch Presentation

---

## Slide 1: Title

**syn: AI Action Firewall**

A deterministic, session-aware governance layer for AI agent tool calls.

_AMD ACT II Hackathon — Unicorn Track_

---

## Slide 2: The Problem

### AI Agents Operate Unchecked

Every AI agent today can call real-world tools:
- Send payments
- Delete files
- Query databases
- Access customer records

**There is no security checkpoint** between the agent's decision and the tool executing.

Existing governance tools evaluate one call at a time. They **cannot correlate** individually-low-risk actions into a dangerous sequence.

---

## Slide 3: The Solution

### syn Intercepts Every Tool Call

```
AI Agent ──▶ syn Gateway ──▶ Tool
                  │
          6 Risk Factors
          + Session History
          + Decision Tree
                  │
     ┌─────┬──────┴─────┬─────┐
   Approved        Escalated   Blocked
```

**Key principle:** The LLM never makes decisions — it only explains them.

---

## Slide 4: Architecture

```
┌──────────┐     POST /intercept     ┌──────────────┐
│  Client   │ ──────────────────────▶ │   Gateway     │
│  / Agent  │                        │  (FastAPI)    │
└──────────┘ ◀────────────────────── └──────┬───────┘
        Trust Receipt                        │
                                   ┌────────┴────────┐
                                   │    Engine/       │
                                   │ 6 Risk Factors   │
                                   │ Session Scorer   │
                                   │ Decision Tree    │
                                   ├─────────────────┤
                                     │    LLM Client    │
                                     │ (OpenAIAPIClient │
                                     │  — one class for │
                                     │  all providers)  │
                                   ├─────────────────┤
                                   │  Audit Store     │
                                   │  (SQLite)        │
                                   ├─────────────────┤
                                   │  Slack Notifier  │
                                   └─────────────────┘
```

### Components

| Component | Tech | Purpose |
|-----------|------|---------|
| **Gateway** | FastAPI (Python) | HTTP API, intercepts tool calls |
| **Engine** | Pure Python | 6-factor risk scoring + decision tree |
| **LLM Provider** | OpenAI-compatible | Generates explanations (not decisions) |
| **Frontend** | React + Vite + TypeScript | Trust Receipt UI, Bootstrap Review UI |
| **Audit** | SQLite | Full audit trail |
| **Infra** | Docker Compose | Gateway + Frontend containers |

---

## Slide 5: Six Risk Factors

| Factor | Range | Description | Example |
|--------|-------|-------------|---------|
| **Severity** | 0–100 | Inherent risk of the action | Amount thresholds, path patterns |
| **Policy** | 0–100 | Violation of explicit rules | Payment > $5,000 blocked |
| **Anomaly** | 0–100 | Deviation from historical patterns | z-score based |
| **Data Sensitivity** | 0–100 | Sensitivity of data accessed | Regex on query/path |
| **Confidence** | 0–100 | How often this action was seen | Ramp: 50→90 with use |
| **Tool Trust** | 0–100 | Trust tier of the tool | official / verified / unknown / unsigned |

### Decision Priority

```
Session branches (pattern match / cumulative threshold)
  → Decision tree floors (severity / policy / data_sensitivity / confidence)
    → Weighted score (severity: 0.30, policy: 0.20, tool_trust: 0.20,
                       data_sensitivity: 0.15, anomaly: 0.10, confidence: 0.05)
```

---

## Slide 6: Demo Scenarios

### Beat 4 — Session Pattern Matching (Primary Differentiator)

Run these 4 calls with the same `agent_id`:

| # | Tool | Params | Result |
|---|------|--------|--------|
| 1 | `check_balance` | `account_id: "123"` | ✅ Approved |
| 2 | `check_balance` | `account_id: "123"` | ✅ Approved |
| 3 | `check_balance` | `account_id: "123"` | ✅ Approved |
| 4 | `send_payment` | `amount: 500, USD, alice` | ⚠️ **Escalated** |

Trigger: `session:pattern_matched:check_balance->send_payment`

### Basic Risk Scenarios

| Scenario | Input | Decision |
|----------|-------|----------|
| Low-risk payment | `send_payment $100` | ✅ Approved |
| Policy violation | `send_payment $10,000` | 🚫 Blocked |
| Severity floor | `send_payment $99,999` | 🚫 Blocked |
| Destructive query | `DROP TABLE users` | 🚫 Blocked |
| Sensitive data | `SELECT * FROM users` | ⚠️ Escalated |
| Low confidence | `delete_file /etc/shadow` | ⚠️ Escalated |
| Unknown tool | `unknown_tool {}` | 🚫 Blocked + auto-generate |

---

## Slide 7: Risk Engine in Detail

### Decision Tree (Hard Floors — applied first)

| Condition | Decision |
|-----------|----------|
| `severity > 90` | **BLOCKED** |
| `policy >= 100` | **BLOCKED** |
| `data_sensitivity >= 70` | **ESCALATED** |
| `confidence < 40` | **ESCALATED** |

### Session Scoring

| Condition | Decision |
|-----------|----------|
| N-action pattern match (e.g., check_balance → send_payment) | **ESCALATED** |
| Cumulative severity > 70 in sliding window | **ESCALATED** |

### Weighted Score (fallback)

Weights: severity 0.30 · policy 0.20 · tool_trust 0.20 · data_sensitivity 0.15 · anomaly 0.10 · confidence 0.05

| Score Range | Decision |
|:-----------:|----------|
| < 30 | **APPROVED** |
| 30–55 | **ESCALATED** |
| >= 55 | **BLOCKED** |

### Regulatory Tier Mapping (EU AI Act)

| Tier | Article | Trigger |
|------|---------|---------|
| Unacceptable | 5 | Exhaustive prohibited practices only |
| High | 6 | Unknown tool + high severity |
| Limited | 52 | Chatbot, deepfake actions |
| Minimal | Default | Everything else |

Plus US financial regime flags: FINRA, SEC.

---

## Slide 8: AI Bootstrap

### Setup from Minutes, Not Days

```
Tool Schemas ──▶ LLM ──▶ Generated Rules ──▶ Review ──▶ Approve
```

1. **Introspect** — reads tool schemas (MCP `tools/list` or manual JSON)
2. **Generate** — LLM produces rules with severity thresholds, policy conditions, data sensitivity patterns, and trust tier
3. **Review** — rule cards with descriptions, diff view, editable YAML
4. **Approve** — written to `policy_config.bootstrap.yaml`, merged at request time

### Continuous Auto-Registration

- Unknown tool called? **Blocked immediately** + rules generated in background
- Pending approval queue with status tracking (generating → pending → approved/rejected)
- "Approve All" or per-tool approve/reject with inline editing

---

## Slide 9: Provider Abstraction

### One Client for All Providers

All providers (local, openai, groq, fireworks) instantiate the same `OpenAIAPIClient` — the only difference is default base URL and model.

```
        LLM_* env vars + YAML config
                  │
           create_llm_client()
                  │
        ┌─────────┴────────────┐
        │                      │
   MockLLMClient     OpenAIAPIClient
   (in-process)      (one class for all)
                         │
              ┌──────┬────┴────┬──────┐
             local  openai   groq  fireworks
```

| Provider | Default Base URL | Default Model | Use Case |
|----------|-----------------|---------------|----------|
| `mock` | N/A | N/A | Testing, offline demo |
| `local` | `http://localhost:8000/v1` | `Qwen/Qwen3-8B` | **AMD Developer Cloud**, vLLM, local |
| `openai` | `https://api.openai.com/v1` | `gpt-5` | Production OpenAI |
| `groq` | `https://api.groq.com/openai/v1` | `openai/gpt-oss-120b` | Low-volume, free tier |
| `fireworks` | `https://api.fireworks.ai/inference/v1` | `accounts/fireworks/models/glm-5p2` | Higher throughput |

### All Configuration Through `LLM_*` Env Vars

No provider-specific env vars. Every provider reads:
- `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`
- `LLM_TIMEOUT`, `LLM_MAX_RETRIES`, `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`

Precedence: **env var → YAML → provider default**.

```yaml
# engine/llm_config.yaml
provider: local
model: Qwen/Qwen3-8B
timeout_seconds: 120.0
```

```ini
# .env — same LLM_* vars for every provider
LLM_PROVIDER=local
LLM_BASE_URL=http://your-instance:8000/v1
LLM_API_KEY=EMPTY
LLM_MODEL=Qwen/Qwen3-8B
```

### Deprecation Compatibility

Old env vars (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `MODEL_NAME`, `GROQ_API_KEY`, `FIREWORKS_API_KEY`) still work with a `DeprecationWarning`. The `fallback` provider is an alias for `groq`.

### Rich Health Endpoint

`GET /health` returns cached LLM status with latency:

```json
{
  "status": "ok",
  "llm": {
    "healthy": true,
    "provider": "local",
    "model": "Qwen/Qwen3-8B",
    "endpoint": "http://your-instance:8000/v1",
    "latency_ms": 112,
    "checked_at": "2026-07-11T..."
  }
}
```

`GET /health/llm` forces a fresh probe. Gateway status stays `"ok"` even when LLM is degraded — the deterministic firewall works without an LLM.

---

## Slide 10: Test Suite

### 15 Test Files · 295 Tests · 95% Pass Rate

| File | Tests | What It Covers |
|------|:-----:|----------------|
| `test_risk_engine.py` | 13 | Full decision flow: factors → verdict |
| `test_factors.py` | 40 | All 6 risk factors in isolation |
| `test_gateway.py` | 58 | HTTP API, CORS, rate limits, bootstrap endpoints |
| `test_audit.py` | 38 | SQLite store, sessions, pending rules, retention |
| `test_session.py` | 20 | Pattern matching, cumulative severity |
| `test_bootstrap.py` | 28 | Introspection, generation, validation, YAML |
| `test_live_api_verification.py` | 23 | Live scenarios against running gateway |
| `test_regulatory.py` | 17 | EU AI Act tiers, US regime flags |
| `test_llm.py` | 30 | Provider factory, per-provider defaults, env override, connection check |
| `test_e2e_smoke.py` | 6 | End-to-end HTTP + SQLite verification |
| `test_demo_auth.py` | 8 | Demo-token tripwire gating |
| `test_admin_reset.py` | 4 | Admin reset endpoint |
| `test_slack.py` | 2 | Slack notifier noop behavior |
| `test_docker.py` | 4 | Docker infrastructure verification |
| `test_frontend_demo_token.py` | 4 | Frontend token wiring |

### Test Results Summary

```
295 tests · 95% pass rate (Windows: ~46 temp-file cleanup issues)
282 passed  ✅  Core logic, risk engine, API, bootstrap, LLM provider
 13 failed  ❌  All Windows-specific (file locking, encoding)
 38 errors  ⚠️  All Windows SQLite temp file cleanup
```

### Six Testing Seams

1. **Risk Engine Integration** — Full decision flow tests (highest-value)
2. **Deterministic Factor Unit Tests** — Each factor in isolation
3. **LLM Client Abstraction Tests** — Mock provider verifies prompt structure
4. **Session Scorer Unit Tests** — Pattern matching, cumulative severity
5. **Config Validation** — YAML schema compliance
6. **End-to-End Smoke Tests** — Live gateway + SQLite verification

---

## Slide 11: Security Hardening

### Implemented Controls (12 post-submission)

| Control | Implementation |
|---------|----------------|
| Path traversal sanitization | `_sanitize_bootstrap_path` rejects `..` |
| LLM prompt injection prevention | JSON-escaped user values |
| Startup validation | Fails if LLM API key missing |
| LLM timeout + fail-fast | `max_retries=0`, configurable timeout |
| Rate limiting | 100 req/min/IP |
| Max body size | 1 MB enforced |
| Audit retention | 90-day auto-purge |
| Request IDs | UUID per request, structured logs |
| Async LLM | Thread pool, event loop unblocked |
| CORS | Configurable origins, credentials disabled |
| SSRF guard | Rejects private/loopback addresses |
| No dev reload in container | Docker CMD without `--reload` |

### Demo-Safety Prereqs (July 2026)

| Control | Purpose |
|---------|---------|
| Randomized per-visit `agent_id` | Cross-visit history isolation |
| `X-Demo-Token` tripwire | Gates mutating endpoints on public demo |
| `POST /admin/reset` | Clean slate between demo sessions |
| Refuse-to-start check | `DEMO_TOKEN` required on Fly |

### Residual Risks (Pre-Production)

- No authentication/RBAC (partially mitigated by demo tripwire)
- Fresh `agent_id` evasion (requires auth)
- Bootstrap writes to committed file (deferred runtime override)

---

## Slide 12: Design Decisions

### Key Trade-Offs

| Decision | Hackathon Choice | Production Ideal |
|----------|-----------------|------------------|
| Session ID | Gateway-issued UUIDs + time-bucket fallback | Authenticated, per-agent |
| Sequence matching | N-action subsequence, unlimited gap | Configurable gap tolerance |
| Cumulative severity | Sliding window, simple sum | Decay-weighted sum |
| Bootstrap persistence | Writes to committed YAML | Gitignored runtime override |
| Database | SQLite | PostgreSQL |
| Slack | Incoming webhook | Interactive Block Kit app |
| Auth | Demo token (extractable) | Full RBAC |

### Key Insight

**20+ design decisions** separate the 5-day hackathon build from a production product.

---

## Slide 13: Getting Started

### Run with Docker
```bash
docker compose up --build
# Gateway: http://localhost:8000
# Frontend: http://localhost:3000
```

### Run without Docker

**Backend:**
```bash
pip install -r requirements.txt
uvicorn gateway.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### Run Tests
```bash
pip install -r requirements.txt pytest httpx
pytest tests/ -v -p no:dash
# (-p no:dash works around a local dash/flask conflict)
```

### Environment
```bash
cp .env.example .env
# Edit .env with your LLM provider, API key, Slack webhook
```

---

## Slide 14: Project Structure

```
syn/
├── gateway/           # FastAPI server
│   ├── main.py        # Routes: intercept, bootstrap, resolve, /health, /health/llm
│   └── Dockerfile
├── engine/            # Risk engine
│   ├── evaluate.py    # Orchestrator
│   ├── severity.py    # Factor scorers
│   ├── policy.py
│   ├── anomaly.py
│   ├── data_sensitivity.py
│   ├── confidence.py
│   ├── tool_trust.py
│   ├── decision_tree.py
│   ├── session.py     # Pattern matching, cumulative
│   ├── regulatory.py  # EU AI Act tiers
│   ├── audit.py       # SQLite store
│   ├── llm.py         # Provider abstraction (OpenAIAPIClient, LLMStatus)
│   ├── bootstrap.py   # AI auto-config
│   ├── slack.py       # Notifications
│   └── *.yaml          # Config files
├── frontend/          # React + Vite + TypeScript
├── tests/             # 15 test files, 295 tests
├── docs/              # PRD, decision log, project ref
├── docker-compose.yml
└── pyproject.toml
```

---

## Slide 15: The Ask

**syn** solves the unsolved problem in AI governance: **session-aware, cross-action risk correlation** with a **deterministic** decision engine.

- ✅ Session-pattern detection (no other governance tool does this)
- ✅ 6 deterministic risk factors (no LLM-in-the-loop decisions)
- ✅ Privacy-preserving (LLM sees abstracted scores only)
- ✅ AI Bootstrap (setup in minutes)
- ✅ Regulatory tagging (EU AI Act tiers)

**Try it:**
```bash
git clone https://github.com/not3zra/syn
cd syn
docker compose up
```

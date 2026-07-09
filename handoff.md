# Handoff — syn project

## Current state

Branch `post-hackathon-hardening` — 6 commits ahead of `main`, all core features implemented and live-verified. PRD and decision log in `docs/` accurately reflect what's built.

## Architecture at a glance

- **gateway/main.py** — FastAPI app, intercepts tool calls, routes to risk engine, serves frontend API
- **engine/** — six risk factors (severity, policy, anomaly, data_sensitivity, confidence, tool_trust), session scoring, decision tree, regulatory mapper, LLM client abstraction, AI Bootstrap, audit store, Slack notifier
- **frontend/** — React + Vite single-page app with Trust Receipt and Bootstrap Review UIs
- **tests/** — 203+ tests across 12 files (unit, integration, gateway, live-verification, e2e smoke)

## Key config files

| File | Purpose |
|------|---------|
| `engine/policy_config.yaml` | Base tool security profiles (never overwritten) |
| `engine/policy_config.bootstrap.yaml` | LLM-generated rules, merged at request time |
| `engine/domain_config.yaml` | Industry/regulatory context for AI Bootstrap prompts |
| `engine/risky_sequences.yaml` | N-action patterns for session risk scoring |
| `engine/regulatory_mapping.yaml` | EU AI Act tier triggers + US regime rules |
| `engine/llm_config.yaml` | Provider selection (mock / groq / fireworks) |
| `.env` | API keys (gitignored) |

## LLM provider

Default is **Fireworks** (`provider: fireworks`, model `accounts/fireworks/models/glm-5p2`). Switch to Groq by editing `engine/llm_config.yaml` and setting `GROQ_API_KEY` in `.env`. The mock provider (`provider: mock`) requires no API key and is used in tests.

## Known edges

- Sliding window for cumulative severity is hardcoded to 30 minutes
- The `local-model` (AMD ROCm) container was scoped but not built
- Interactive Slack approve/deny (Block Kit) requires a Slack app with OAuth — webhook-only for now
- `test_e2e_smoke.py` tests need a live uvicorn server (expected)
- `test_live_api_verification.py` tests check provider responsiveness — may time out if rate-limited

## Current working tree

10 files modified (uncommitted) in this session:
- Reasoning leak detection and tolerant JSON parsing in `engine/llm.py`
- Slack deduplication in `engine/slack.py`
- Unbounded history for confidence scoring in `engine/evaluate.py`
- N-action trigger formatting fix in `engine/session.py`
- Fireworks model config update in `engine/llm_config.yaml`
- Package discovery fix in `pyproject.toml`
- Frontend trigger display update in `frontend/src/TrustReceipt.tsx`
- Test updates for new trigger format in `tests/test_risk_engine.py`, `tests/test_live_api_verification.py`, `tests/test_audit.py`

These are ready to commit.

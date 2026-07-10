# Handoff — syn project

## Current state

Branch `main` — working tree clean and up to date with `origin/main`. All core features are implemented and verified; post-submission hardening (#1–#12) and the deploy-safety prereqs (#33–#36) are shipped and pushed. `docs/prd.md` and `docs/decision-log.md` (Rounds 1–7, #1–#31) reflect the built state and the planned/deferred decisions.

## Key decisions (decision log)

- **#19 / #20 / #27** — `agent_id` is unauthenticated and self-reported; real auth/RBAC is deferred to pre-production.
- **#28** — `data_sensitivity_floor: 70.0` added to the decision tree (PII/sensitive access escalates even when the blended weighted score is low).
- **#29** — `confidence` is an unbounded, non-decaying trust signal; slow-trust build-up is a consequence of #19, not a separate fix.
- **#30** — bootstrap approvals currently write the committed `policy_config.bootstrap.yaml`; a gitignored runtime override (`policy_config.bootstrap.runtime.yaml`) is the deferred fix.
- **#31 / #33–#36** — deploy-safety prereqs for the public demo: randomized per-visit `agent_id`, `X-Demo-Token` tripwire (no-op locally, gateway refuses to boot on Fly without `DEMO_TOKEN`), `POST /admin/reset`, and frontend token wiring.

## Architecture at a glance

- **gateway/main.py** — FastAPI app; intercepts tool calls, routes to risk engine, serves the frontend API. `require_demo_token` dependency gates mutating/introspect routes (no-op unless `DEMO_TOKEN` set; refuses boot on Fly without it). `SYN_AUDIT_DB_PATH` relocates the SQLite audit DB; `SYN_ALLOW_ORIGINS` controls CORS; `SYN_TRUSTED_PROXY` switches the rate limiter to trust `X-Forwarded-For`.
- **engine/** — six risk factors (severity, policy, anomaly, data_sensitivity, confidence, tool_trust), session scoring, decision tree, regulatory mapper, LLM client abstraction, AI Bootstrap, audit store, Slack notifier.
- **frontend/** — React + Vite SPA (Trust Receipt + Bootstrap Review UIs). `App.tsx` randomizes `agent_id` per page load; `api.ts` attaches `X-Demo-Token` from `VITE_DEMO_TOKEN`.
- **tests/** — unit, integration, gateway, live-verification, e2e smoke. `test_workflow.sh` is the end-to-end adversarial script (60 assertions passing).

## Key config files

| File | Purpose |
|------|---------|
| `engine/policy_config.yaml` | Base tool security profiles (never overwritten) |
| `engine/policy_config.bootstrap.yaml` | LLM-generated rules, merged at request time. **Must stay `tools: {}`** — committed baseline; runtime-override split deferred (#30) |
| `engine/domain_config.yaml` | Industry/regulatory context for AI Bootstrap prompts |
| `engine/risky_sequences.yaml` | N-action patterns for session risk scoring |
| `engine/regulatory_mapping.yaml` | EU AI Act tier triggers + US regime rules |
| `engine/llm_config.yaml` | Provider selection (mock / groq / fireworks); default `fireworks` / `glm-5p2` |
| `.env` | API keys (gitignored) |

## LLM provider

Default is **Fireworks** (`provider: fireworks`, model `accounts/fireworks/models/glm-5p2`). Switch to Groq by editing `engine/llm_config.yaml` and setting `GROQ_API_KEY` in `.env`. The mock provider (`provider: mock`) requires no API key and is used in tests.

## Known edges / deployment caveats

- The `X-Demo-Token` tripwire is **not** authentication: the token is baked into the static frontend bundle and is extractable by design. It only raises the bar for a public demo; real auth is #19.
- `agent_id` is still spoofable; per-visit randomization only isolates a normal user's history across visits (#13 / #20 / #29).
- Bootstrap approvals write the committed `policy_config.bootstrap.yaml`; reset via `POST /admin/reset` (#15) or the `test_workflow.sh` teardown. Do not commit an approved-bootstrap file (#30).
- Sliding window for cumulative severity is hardcoded to 30 minutes.
- Point `SYN_AUDIT_DB_PATH` at a mounted volume on Fly so `audit.db` survives restarts.
- Set `SYN_ALLOW_ORIGINS` to the frontend URL on deploy (CORS is wildcard by default, credentials disabled).
- The `local-model` (AMD ROCm) container was scoped but not built.
- Interactive Slack approve/deny (Block Kit) requires a Slack app with OAuth — webhook-only for now.
- `test_e2e_smoke.py` / `test_live_api_verification.py` need a live server / live provider (expected).

## Current working tree

Clean — no uncommitted changes. `git status` reports up to date with `origin/main`.

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
- **tests/** — unit, integration, gateway, live-verification, e2e smoke. `test_workflow.sh` is the end-to-end adversarial script (60 assertions passing). A realistic-usage scenario script, `scripts/syn_test_scenarios.py`, is planned (see *Pending work*) and is intentionally distinct from `test_workflow.sh`.

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

## Pending work — UI polish, explanation grounding, scenario script (branch `ui-product-identity`)

Status: implemented and verified (uncommitted) on `ui-product-identity`. The prior UI redesign (teal product identity, two-pane inputs|receipt, Audit Timeline, placeholder logo) is committed there (not yet merged to `main`). All four work items are done:

- `scripts/syn_test_scenarios.py` runs 19 assertions, all passing against a live gateway (real Fireworks LLM). Each scenario uses a unique per-run `agent_id` so sessions start clean.
- Engine note: a *fresh* agent starts at **neutral** confidence (50), so `confidence_floor` only escalates when the agent has history in other tools but is new to this one — the script demonstrates this accurately (it is not a "first action always needs review" rule).
- `reason` string threads through `severity`/`policy`/`data_sensitivity`/`confidence` (now `(score, reason)` tuples) → `evaluate.py` → `RiskEngineResult.reason` → `DecisionResponse` (gateway + frontend) → shown under the receipt's decision hero and in the timeline; `build_explanation_prompt`/`_get_mock_explanation` now ground the LLM explanation in `reason`.
- Timeline refetches on every intercept (not just Reset) via `refreshNonce`. Right column is split into a scrolling `output-main` and a pinned `~42vh` timeline panel so the audit trail stays visible beside a tall receipt.

### 1. Realistic scenario test script — `scripts/syn_test_scenarios.py`
Distinct from `test_workflow.sh` (an adversarial/edge-case fuzz suite: unique agent per section, injection/422/XSS/proto-pollution tests, auto-managed server, `jq`). The new script is a **behavioral / realistic-usage** suite:
- Python stdlib only (`urllib`); pure client against an already-running gateway (no server start, no DB wipe).
- Persona-based, session-correlated: one persistent `agent_id` per scenario flow, so session pattern/cumulative scoring is exercised (unlike `test_workflow.sh`'s per-section agents).
- Scenarios model plausible agent behavior: a finance agent (`finbot`) doing routine payments then a `check_balance → send_payment` fraud pair; a data agent (`dataops`) querying then deleting; a 3-step fraud chain; cumulative buildup; destructive `DROP`; unknown tool; close-out `GET /timeline` count.
- Asserts `decision` + `trigger` + grounded `reason` + `regulatory_tier`/`us_regime_flags` + (escalated) `rollback_plan`/`expires_at`.
- Run: `python scripts/syn_test_scenarios.py` (env `SYN_API_BASE` default `http://localhost:8000`, optional `DEMO_TOKEN`).

### 2. Audit Timeline live update
Timeline only refetches on mount and on Reset (its `refreshKey` = `resetNonce`). Fix: bump the nonce on successful intercept in `App.tsx` `handleSubmit` (rename `resetNonce`→`refreshNonce`; increment on both reset and intercept) so the trail updates without a page reload.

### 3. Audit trail visibility
Right column is one scrolling stack, so a tall receipt buries the timeline. Fix: split the column — wrap receipt/empty in `<div className="output-main">` and render `<Timeline>` as a sibling; `App.css` makes `.output` a flex column where `.output-main` scrolls and `.timeline-panel` is a fixed ~40vh region, keeping the trail visible beside a tall receipt.

### 4. Grounded explanations (thread a `reason` through the engine)
Explanations currently restate the scoring mechanism. Audit of the explain path:
- `severity.py` returns `95.0` for invalid `send_payment` amount with no reason; `data_sensitivity_floor` has no mock-explanation branch (falls to generic weighted text); `confidence_floor` is generic.
- Fix: `score_severity` / `score_data_sensitivity` / `score_confidence` return `(score, reason)` tuples naming the matched field/pattern or history count; `evaluate.py` sets `RiskEngineResult.reason` (add field in `models.py`) on the branch that produces the decision (session pair, severity/DS/confidence/policy floor); `gateway` + `frontend/types.ts` add `reason` to `DecisionResponse`; `TrustReceipt` shows it under the decision hero; `build_explanation_prompt` (`llm.py`) receives `reason` and instructs plain-language cause + fix (mock explanation uses it too). Applies the existing `session:pattern_matched` / `weighted_score:top_factor` standard to every trigger.

### Verification
- `python scripts/syn_test_scenarios.py` → realistic scenarios PASS; `reason` assertions validate #4.
- `npm run lint` + `build` in `frontend/`; manual check: timeline updates on intercept without reload, stays visible under a tall receipt, receipt shows grounded `reason`.

## Current working tree

Clean — no uncommitted changes. `git status` reports up to date with `origin/main`.

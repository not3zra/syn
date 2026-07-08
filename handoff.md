# Handoff — syn project

## Objective

Complete demo prep (Issue #13) for the hackathon submission. All four core issues (#14–#17) are implemented and live-verified. Bootstrap flow is also live-verified. The main risk is Groq API rate limits during the demo.

## Demo state

- **Beat 4** (3× check_balance → send_payment): verified live. Calls 1-3 approved, call 4 escalates on `session:pattern_matched:check_balance_send_payment`. Works with fresh `agent_id="demo-$(date +%s)"` per run.
- **Bootstrap** (3 acts): verified live.
  - Act 1: unknown tool → `blocked / gateway:unknown_tool`
  - Act 2: introspect → validate → approve → writes `policy_config.bootstrap.yaml`
  - Act 3: same tool → now governed by bootstrapped rules (no longer blocked)
- **Slack webhook**: confirmed working, now shows trigger-aware label (Cumulative Risk / Weighted Score / Driving Factor instead of always "Risk Score")
- **Execution stub**: fires on live approvals and post-escalation resolution; no real side effects
- **Rollback + expiry**: on escalation responses; `expire_old()` runs per request

## Test state

- **145/164 unit tests pass** (all non-LLM-dependent)
- **19 tests fail due to Groq rate limit** (429 RateLimitError, 100K TPD free tier exhausted)
- Rate limit resets ~midnight UTC; or switch to Fireworks provider

## Groq rate limit

Free tier: 100K tokens/day. Heavy development/testing today burned through it. The `FallbackLLMClient` in `engine/llm.py:210` uses Groq (`llama-3.3-70b-versatile`). A `FireworksLLMClient` has been added as an alternative — switch `provider` in `engine/llm_config.yaml` to `fireworks` and set `FIREWORKS_API_KEY` in `.env`.

## Changed files (from this session)

| File | What changed | Key lines |
|------|-------------|-----------|
| `engine/llm.py` | Added `FireworksLLMClient` class; `create_llm_client()` handles `"fireworks"` provider | 296-334 |
| `engine/llm.py` | `FallbackLLMClient.generate()` branches on `output_schema["type"] == "bootstrap_rules"` | 237-264 |
| `gateway/main.py` | `_get_merged_tools()` reads `policy_config.bootstrap.yaml`, merges into base tools | 59-76 |
| `gateway/main.py` | Intercept uses merged tools for unknown-tool check and eval config | 196-231 |
| `engine/bootstrap.py` | `_yaml_quote` uses single quotes, added `\\` and `$` to special chars | 65-72 |
| `engine/severity.py` | Added `_generic_severity()` fallback for bootstrap tools | 16-34 |
| `engine/policy.py` | Added operators: `gt`, `lt`, `gte`, `lte`, `==`, `!=`/`neq`, `in`, `not_in` | 25-52 |
| `engine/slack.py` | Risk score label is now trigger-aware (Cumulative Risk / Weighted Score / Driving Factor) | 19-35 |

## Untouched files (for reference)

- `engine/policy_config.yaml` — base tool config (send_payment, delete_file, query_database, check_balance)
- `engine/policy_config.bootstrap.yaml` — created by bootstrap approve (gitignored)
- `data/audit.db` — SQLite audit store (gitignored)
- `frontend/src/BootstrapReview.tsx` — bootstrap review UI
- `frontend/src/App.tsx` — main app with intercept mode

## Suggested skills for next agent

- `impeccable` — if doing UI polish for demo
- `handoff` — if you need to pass to another agent

## Fireworks integration

Added `FireworksLLMClient` in `engine/llm.py:296-334`. To use:

1. Set `FIREWORKS_API_KEY` in `.env`
2. Change `engine/llm_config.yaml`:
   ```yaml
   provider: fireworks
   model: accounts/fireworks/models/llama-v3p3-70b-instruct
   ```
3. Restart server

The client is a drop-in replacement for `FallbackLLMClient` — same interface, supports both explanation and bootstrap_rules output schemas.

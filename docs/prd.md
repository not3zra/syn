# PRD: AI Action Firewall

**Status:** Implemented (core issues live-verified); deploy-safety prereqs #33–#36 added (demo-token tripwire, randomized per-visit `agent_id`, `POST /admin/reset`)
**Target track:** AMD ACT II Hackathon — Unicorn Track
**Submission deadline:** July 11, 2026, 15:00 UTC

---

## Problem Statement

Every AI agent today can call real-world tools — send payments, delete files, update databases, query customer records. There is no security checkpoint between the agent's decision and the tool executing. If the agent is compromised, confused, or simply wrong, the damage is instant and irreversible.

Existing governance tools evaluate one tool call at a time. They cannot correlate individually-low-risk actions into a dangerous sequence. Neither the leading open standard (OAP) nor Microsoft's Agent Governance Toolkit currently correlates across actions within a session. This is the field's own named unsolved gap in 2026, and practitioners rank "industry standards or frameworks for governance" as their most-wanted improvement.

The core thesis: **a governance layer for AI agents must be deterministic (not an LLM judgment call), session-aware (not per-action-only), and privacy-preserving (the third-party AI only sees abstracted scores, never raw action content).**

---

## Solution

AI Action Firewall is a governance layer that sits between an AI agent and the tools it calls. Every tool call is intercepted by an MCP-compatible gateway, scored against six deterministic risk factors, checked against the session's recent history for risky patterns, and either approved, escalated to a human, or blocked — with a full audit trail and a plain-English explanation.

The decision never leaves local code. The LLM (Fireworks or Groq, config-swappable) receives only abstracted numeric scores and generates explanation, remediation, and rollback text — it never makes or influences the allow/block/escalate decision. An AI Bootstrap feature reads tool schemas and auto-generates the initial security profile, reducing setup from days to minutes.

---

## User Stories

1. As a developer deploying an AI agent, I want to drop a governance layer in front of my agent's tool calls without modifying the agent, so that I retroactively secure tools I already use.

2. As a developer, I want the governance layer to speak the Model Context Protocol, so that it works with any MCP-compatible agent out of the box.

3. As a security reviewer, I want every tool call scored against severity, policy compliance, anomaly, data sensitivity, confidence, and tool trust, so that no risk axis is invisible.

4. As a security reviewer, I want a decision-tree floor that applies hard rules (severity > 90 → reject, policy violation → reject, data_sensitivity ≥ 70 → escalate, confidence < 40 → escalate) before any weighted blending, so that critical violations cannot be averaged away by low scores on other factors. The `data_sensitivity` floor (#28) routes PII/sensitive access (e.g. `SELECT * FROM users`) and sensitive deletes to a human even when the blended weighted score stays low.

5. As a security reviewer, I want the anomaly factor computed by a statistical scorer (z-score, rolling average, frequency) by default, so that it works reliably without any GPU or model dependency.

6. As a security reviewer, I want the anomaly factor optionally upgradeable to a local LLM running on AMD GPU (if the Day 2 ROCm smoke test passes), so that the privacy story is even stronger.

7. As a security reviewer, I want actions grouped into sessions with auto-generated session IDs, so that cross-action correlation works without agents knowing they are being governed.

8. As a security reviewer, I want the session scorer to detect ordered risky sequences (e.g., check_balance → send_payment), so that individually-approved actions that form a dangerous pattern are escalated.

9. As a security reviewer, I want cumulative session severity tracked as a simple sum with a threshold, so that a run of medium-risk actions eventually triggers escalation even without an exact pattern match.

10. As a compliance officer, I want every decision tagged with a regulatory tier (EU AI Act risk category, relevant US regime), so that I can demonstrate governance alignment on each action.

11. As a compliance officer, I want the regulatory mapping to follow the actual EU AI Act Article structure — Unacceptable Risk reserved for the fixed list of prohibited practices (Article 5), High Risk for systems with safety/rights implications (Article 6), Limited Risk for transparency obligations (Article 52), Minimal Risk as the default.

12. As a compliance officer, I want the regulatory tag clearly labeled as informational — not a legal certification — so that no one overclaims compliance guarantees.

13. As a human approver, I want escalated actions routed to Slack via webhook, so that I can approve or deny from the tool I already use.

14. As a human approver, I want each escalation to include a rollback plan ("what to do if this was wrong") and an expiry time, so that stale approvals do not linger indefinitely.

15. As a human approver, I want a Trust Receipt UI showing the action, risk gauge, session risk gauge, the explicit trigger string (e.g., `session:pattern_matched:check_balance_send_payment`), regulatory badge, six-factor breakdown, AI explanation, audit hash, and timestamp, so that I can make a fully-informed decision at a glance and verify that the AI explanation matches the deterministic trigger.

16. As a human approver, I want the audit log presented as a chronological timeline (not a table), so that I can quickly scan what happened and in what order.

17. As an on-call engineer, I want the LLM that generates explanations to receive the exact trigger that caused the decision (not just factor scores), so that the plain-English explanation never drifts from or contradicts the deterministic cause shown on the receipt.

18. As a platform engineer deploying the firewall, I want the entire system containerized with Docker from Day 1, so that I never hit a "works on my machine" problem during a deadline.

19. As a platform engineer, I want the LLM provider abstracted behind a config-swappable interface, so that I can switch between providers (mock, Groq, Fireworks) by editing one line in `llm_config.yaml`.

20. [Implemented] As a platform engineer, I want a Fireworks cutoff policy: if Fireworks access is not confirmed by end of Day 3, the submission ships on the fallback provider with Fireworks calls pre-tested and ready to flip via config change.

21. As a first-time user, I want the onboarding to auto-generate the initial security profile from tool schemas, so that I have working rules in minutes instead of days.

22. As a first-time user, I want the AI Bootstrap to use a context-rich prompt (domain, regulatory context, risk priorities) so that the generated rules are relevant, not generic.

23. As a first-time user, I want AI Bootstrap output to produce valid nested YAML with embedded reasoning comments, so that I can understand why each score was assigned.

24. As a first-time user, I want AI Bootstrap output validated for structural correctness before I see it in the Bootstrap Review UI, so that I never approve malformed YAML.

25. As a first-time user, I want the Bootstrap Review UI to show a table of proposed rules with an editable YAML textarea, so that I can tweak inaccurate values before locking them.

26. As a first-time user, I want unknown tools (not in the config) to fail closed: blocked and escalated to a human, so that no ungoverned action can slip through.

27. As a judge at a hackathon, I want to see a live demo that shows a low-risk approval, a high-risk escalation, and a session-pattern escalation, so that I can clearly understand what differentiates this product.

28. As a judge, I want to see the demo include the "four individually-approved actions flagged as a session pattern" beat, so that I can see the primary differentiator in action.

29. As a judge, I want the demo to optionally show AI Bootstrap generating rules for a new tool in real time, so that I can see the setup automation working.

30. As the developer building this, I want a single end-to-end smoke test that sends a real mock tool call through the running gateway and confirms a decision + a SQLite row, so that wiring bugs surface on Day 2-3 instead of Day 5.

31. As the developer building this, I want risk engine integration tests covering all defined scenarios, so that I can refactor with confidence.

32. As the developer building this, I want an LLM provider abstraction with a mock for testing, so that I can verify prompt structure without needing API access.

---

## Implementation Decisions

### LLM Provider Abstraction

The LLM integration (explanation layer, AI Bootstrap) is built behind a swappable provider interface (abstract `LLMClient` class). A factory function reads `llm_config.yaml` to select the active provider. Three providers exist: `MockLLMClient` (testing), `FallbackLLMClient` (Groq), and `FireworksLLMClient` (Fireworks AI). The `generate(prompt, output_schema)` method handles both explanation prompts and bootstrap-rules generation (selected via `output_schema["type"]`).

For bootstrap generation, the client switches to a longer `max_tokens` limit (800 vs 300 for explanations) and a different system prompt targeting security policy generation.

### Explicit Trigger Passing to LLM

The explanation layer does not let the LLM infer the reason for a decision. The deterministic engine returns both the decision and the exact trigger string (e.g., `session:pattern_matched:check_balance_send_payment`, `decision_tree:severity_floor`). The LLM prompt includes the trigger string explicitly and instructs the model to explain only that trigger. For weighted_score decisions, the highest-contributing factor is also passed so the LLM names it. This prevents hallucination and ensures the explanation never contradicts the factor scores shown on the receipt.

### AI Bootstrap Config Generation

The AI Bootstrap reads tool schemas (via MCP `tools/list` introspection or manual JSON input). A context-rich prompt is sent to the LLM, which returns structured JSON. The prompt context (industry, regulatory regimes, risk priorities) is sourced from `domain_config.yaml` instead of being hardcoded — editing the config file changes the generated rules without touching code. The JSON is converted to nested YAML with the LLM's reasoning comments preserved as YAML comments. Before the output reaches the Bootstrap Review UI, it passes through the same schema validation used for all config files.

**Continuous auto-registration:** When an unknown tool is encountered during an intercept, the gateway blocks it AND automatically triggers bootstrap rule generation via FastAPI BackgroundTasks. The blocked response returns immediately (`gateway:unknown_tool`) — the generation is a background side effect that cannot delay the response. Proposed rules enter a SQLite-backed pending review queue with status tracking. The Bootstrap Review UI exposes a Pending Approvals tab with a flash-on-load notice when new rules are waiting. Each tool shows a line-based diff view (red/green — "no rules → proposed" as all-additions, or current-vs-proposed for re-generated tools). Per-tool approve/reject and "Approve All" are available. Failed LLM generations store the error and offer a "Retry" button. Approve and reject actions are logged to the audit timeline for a complete lifecycle narrative. Rules approved mid-window apply forward-only — past actions are not rescored. After approval, the generated config is written to `policy_config.bootstrap.yaml` and merged at request time — the base `policy_config.yaml` is never overwritten. **Planned (deferred, decision log #30):** approved bootstraps will move to a separate, gitignored runtime override (`policy_config.bootstrap.runtime.yaml`), keeping the committed `policy_config.bootstrap.yaml` as an untouched `tools: {}` baseline; until then, the committed file is reset to `tools: {}` after runs that approve tools.

### Session Risk Scorer

Three improvements upgrade session risk scoring beyond the initial implementation:

**1. Session ID lifecycle:** Agents can explicitly manage sessions via `session_intent` ("start", "continue", "end"). On "start", the gateway generates a UUID-based session ID stored in a SQLite-backed session registry. On "continue", the gateway validates the ID is active before accepting it. On "end", the session is closed cleanly. If no intent is provided, the gateway falls back to time-bucketing (`agent_id:timestamp // 600`) for backward compatibility. Concurrent sessions per agent are allowed (scoring is agent-wide, not per-session). Unknown or expired "continue" IDs fall back to time-bucketing and are noted in the trigger string.

**2. N-action sequence matching:** Ordered pair (A → B) matching is replaced by ordered subsequence matching against N-action patterns from `risky_sequences.yaml`. If an N-length action chain appears in order anywhere within the session's action history, it is a match. Gap between chain elements is bounded by the shared sliding window (default 30 minutes) — benign interleaved actions do not evade detection, but actions outside the window do not participate. Multiple patterns can fire on one action; all matches are reported in the trigger string (e.g., `session:pattern_matched:check_balance_send_payment+query_database_delete_file`).

**3. Sliding-window cumulative severity:** Cumulative severity is decoupled from session boundaries. Instead of a per-session simple sum, an agent-wide sliding time window (configurable, default 30 minutes) computes cumulative severity from all actions within the window. This prevents resetting risk by outwaiting a session boundary. The threshold of 70 is preserved and constrained by the Demo Beat 4 script:

```yaml
check_balance: 15  # non-financial read operation, no mutation possible
send_payment: 50   # sub-threshold payment, below $5,000 policy limit
```

Cumulative sums: 3 × check_balance (45) < 70 < 45 + send_payment (95).

### Generic Fallback for Bootstrap Tools

The severity scorer originally had hardcoded branches for `send_payment`, `delete_file`, `query_database`, and `check_balance`. Bootstrap tools fell through to `return 50.0`. A generic fallback (`_generic_severity`) now processes `max_amount` and `path_pattern` rules for any tool. The policy scorer supports operators `>`, `<`, `>=`, `<=`, `==`, `!=`, `in`, `not_in`, and `matches`.

### Regulatory Tier Mapping

The regulatory mapper implements the EU AI Act's Article structure:
- **Unacceptable Risk (Article 5):** Exhaustive list of prohibited practices only (social scoring, real-time biometric categorization in public, subliminal manipulation, exploitation of vulnerabilities). Never inferred from severity or action type.
- **High Risk (Article 6):** Triggered by trust tier (Unsigned/Unknown with high severity), data sensitivity (GDPR Art. 9 special category data), or action type (critical infrastructure, biometric identification, employment decisions).
- **Limited Risk (Article 52):** Triggered by transparency-relevant action types (chatbot, emotion recognition, deepfake).
- **Minimal Risk:** Default for everything else.

US financial regimes (FINRA, SEC) are flagged as additional badges where the action type is financial.

### Docker Architecture

Two primary containers:
1. **gateway** — Python + FastAPI backend, MCP interception, risk engine, AI Bootstrap, LLM integration, SQLite, Slack
2. **frontend** — React + Vite static build, served via nginx

A third optional `local-model` container (AMD GPU / ROCm) was scoped but not built.

### Config Files

Four YAML config files:
1. **policy_config.yaml** — Base tool security profiles. Never overwritten — bootstrap additions go to `policy_config.bootstrap.yaml` and merge at request time.
2. **domain_config.yaml** — Domain context for AI Bootstrap prompt generation (industry, regulatory regimes, risk priorities).
3. **risky_sequences.yaml** — N-action chain patterns for session risk scoring (subsequence matching, unlimited gap tolerance).
4. **regulatory_mapping.yaml** — EU AI Act tier triggers and US regime rules.

All configs are validated against a schema on load. **Planned (deferred, #30):** a fifth, gitignored `policy_config.bootstrap.runtime.yaml` will hold runtime-approved tools so the committed `policy_config.bootstrap.yaml` stays a clean `tools: {}` baseline.

### Unknown Tool Handling

Any tool call for a tool not in the merged tools dict (base config + bootstrap file) is blocked immediately and escalated to a human. Bootstrap-approved tools are merged into the known-tool set at request time — the base config is never modified.

### Slack Integration

Escalated actions are posted to a Slack channel via incoming webhook. Each message includes the action type, decision, trigger-aware risk label (Cumulative Risk / Weighted Score / Driving Factor), the AI explanation, and a timestamp. A link to the web resolution UI is included so the approver can review and act from their browser. Full interactive approve/deny from Slack (Block Kit buttons) requires a Slack app with OAuth and a public HTTPS endpoint — scoped as a production upgrade.

---

## Testing Decisions

### Six Testing Seams

**Seam 1 — Risk Engine Integration Tests (HIGHEST PRACTICAL SEAM)**
Feed a complete action input through all six factors + session scorer + decision-tree floor. Assert the final decision and trigger string are correct. Covers all defined scenarios. This is the primary correctness assertion for the core product.

**Seam 2 — Deterministic Factor Unit Tests**
Pure function tests for each factor in isolation. Fast, TDD-friendly, catches factor-level bugs before integration.

**Seam 3 — LLM Client Abstraction Tests**
Inject a mock LLM provider. Verify that the prompt sent to the provider includes the correct trigger string, factor scores, and action context. Verify schema enforcement. This catches prompt structure bugs without needing external API access.

**Seam 4 — Session Scorer Unit Tests**
Feed action histories with known time windows and sequences. Verify sliding-window cumulative severity, N-action subsequence matching (both match and no-match cases), and session lifecycle flow.

**Seam 5 — Config Validation + AI Bootstrap Output Validation + Unacceptable Risk Guard**
Parse all YAML configs and verify schema compliance. Additionally, after AI Bootstrap output is produced, run it through the same schema validation before surfacing to the Bootstrap Review UI. This prevents "looked fine in the table but YAML parser breaks" failures.

Includes one regression-style guard: feed the regulatory mapper every extreme/edge-case input (severity 100, data_sensitivity 100, unsigned tool + high severity, all combinations) and assert none produce `unacceptable_risk` unless the action_type is literally one of the four Article 5 prohibited practices.

**Seam 6 — End-to-End Smoke Test**
One real mock tool call through the actual running gateway (FastAPI routes, request/response serialization, SQLite write). Three variants: one approve path, one escalate path, one block path. Monitored via Live API Verification tests that call the real gateway + real LLM and assert real responses.

### Live Verification Pattern

Every feature follows the same cycle: build → claim done → manually verify live → bug found → fix → re-verify. This pattern caught: stale session history leaking, missing top_factor in LLM prompts, incorrect Slack risk-score labels, YAML quoting failures with regex patterns, and the FallbackLLMClient silently returning empty bootstrap rules. The Live API Verification suite (`tests/test_live_api_verification.py`) encodes these scenarios as automated tests.

### What makes a good test

A good test asserts external behavior, not implementation details. It feeds inputs in (action type, parameters, session context, tool trust tier) and asserts outputs out (decision, trigger string, factor scores, regulatory tag, SQLite row count). Tests that assert which internal function was called or what the config object looked like mid-pipeline are too brittle for a 5-day build.

---

## Out of Scope

- **Production-grade event store.** SQLite is sufficient for the hackathon.
- **Full RBAC/authentication.** The gateway trusts its caller for the hackathon. A throwaway `X-Demo-Token` tripwire (#14) was added as a deploy prereq to gate mutations on the public demo, but it is extractable by design and is not real auth — full authentication/RBAC (#19) remains out of scope.
- **Multi-tenant isolation.** Single-tenant demo only.
- **Real agent integration.** Demo uses mock tools and pre-scripted triggers. Live agent integration is a stretch goal.
- **Replay feature.** Requires full input state snapshotting — too expensive for Day 4-5.
- **Localization/i18n.** English-only UI.
- **CI/CD pipeline.** Not needed for a 5-day hackathon.
- **Certified legal compliance.** The regulatory mapping is explicitly informational and disclaimed as not guaranteeing legal or regulatory compliance.
- **MCP wrapper.** Scoped for post-hackathon.
- **Interactive Slack app.** Current implementation uses incoming webhooks only. Full interactive approve/deny from Slack requires a Slack app with OAuth and a public HTTPS endpoint.
- **Decay-weighted cumulative severity.** A half-life decay model for cumulative severity was considered but not implemented — the sliding time window provides sufficient protection for the hackathon scope.

---

## Further Notes

- Two LLM providers are integrated: Groq (`llama-3.3-70b-versatile`) and Fireworks (`llama-v3p3-70b-instruct`). Switch via `provider:` in `engine/llm_config.yaml`. Both require an API key in `.env`.
- Groq free tier has a 100K token/day limit — switch to Fireworks for higher throughput during demo/rehearsal.
- The demo flow has two parts: **Beat 4** (3× check_balance → send_payment, demonstrating session pattern matching) and **Bootstrap** (3 acts: fail-closed → introspect/approve → live enforcement). Total runtime ~4 minutes.
- The sequence-of-actions correlation (agent-wide sliding time window, displayed via session grouping) is the primary differentiator and should be foregrounded in the pitch. The six-factor score and regulatory tagging are supporting depth.

### Post-Hackathon Improvements

Documented production upgrades that were explicitly considered but deferred:

- **Fresh agent_id evasion.** An attacker cycling agent IDs per action bypasses all session and sliding-window tracking. Requires authentication/RBAC.
- **Decay-weighted cumulative severity.** Half-life decay would weight recent actions more than old ones within the sliding window. The simple sum was sufficient for the hackathon.
- **Interactive Slack integration.** Block Kit approve/deny buttons require a Slack app with OAuth and a public HTTPS endpoint. Current webhook-only is functional but requires opening the browser to resolve escalations.
- **PostgreSQL.** SQLite is appropriate for single-user demo. PostgreSQL is needed for concurrent access, multi-tenancy, and production scale.

---

## Security Hardening (post-submission)

After the hackathon submission, a vulnerability scan + attack-surface test pass closed the following issues. All are live-verified:

| # | Control | Implementation |
|---|----------|----------------|
| 1 | Path-traversal sanitization on `POST /bootstrap/approve` `target_path` | `_sanitize_bootstrap_path` resolves inside the engine config dir; rejects `..` escapes (400) |
| 2 | LLM prompt-injection sanitization | `action_type`/`trigger`/`tool_name` are JSON-escaped before prompt interpolation |
| 3 | Startup validation | Gateway fails to start if the configured LLM provider is missing its API key |
| 4 | LLM timeout + fallback | Fireworks/Groq calls time out (default 15s) and fall back to mock instead of hanging |
| 5 | Rate limiting | 100 req/min/IP on all paths except `GET /health`; keyed on the real TCP peer, not spoofable `X-Forwarded-For` |
| 6 | Max body size | 1 MB enforced for both `Content-Length` and chunked transfer encoding |
| 7 | Audit retention | Rows older than `SYN_AUDIT_RETENTION_DAYS` (90) auto-purged on each `/intercept` |
| 8 | Request IDs | UUID `X-Request-ID` + structured logs tagged per request |
| 9 | Async LLM calls | LLM `.generate()` runs in a thread pool; event loop is not blocked |
| 10 | CORS | `CORSMiddleware` added; `allow_origins` configurable. `allow_credentials` is **disabled** while origins are wildcard |
| 11 | SSRF guard | `POST /bootstrap/introspect` rejects an `api_base` that is non-HTTP(S) or resolves to a private/loopback/link-local address |
| 12 | No dev reload in container | `gateway/Dockerfile` no longer launches uvicorn with `--reload` |

### Deploy-safety prereqs for public demo (added July 2026)

These close the gap for a public Fly.io demo without real auth (which stays deferred, #19). They are throwaway demo guards, not a security boundary — the token is baked into the client bundle and is extractable by design:

| # | Control | Implementation |
|---|----------|----------------|
| 13 | Randomized per-visit `agent_id` | Frontend generates a fresh `crypto.randomUUID()` in memory on each page load and sends it as `agent_id` on `/intercept`. Not stored, not user-supplied — gives normal users cross-visit history isolation. `agent_id` is still attacker-controllable, so this is isolation, not authentication (#20/#29). |
| 14 | `X-Demo-Token` tripwire | `require_demo_token` FastAPI dependency gates `/intercept`, `/resolve/{entry_id}`, `/bootstrap/approve`, `/bootstrap/approve/{tool}`, `/bootstrap/reject/{tool}`, `/bootstrap/approve-all`, `/bootstrap/retry/{id}`, `/bootstrap/introspect`, `/admin/reset`. No-op when `DEMO_TOKEN` env is unset (local dev). On Fly (`FLY_APP_NAME` set) the gateway **refuses to start** if `DEMO_TOKEN` is unset (`gateway/main.py:166`). |
| 15 | `POST /admin/reset` | Token-gated endpoint that clears the audit store (decisions + pending rules + sessions) and rewrites `policy_config.bootstrap.yaml` to `tools: {}`. Safe teardown between demo sessions. |
| 16 | Frontend token wiring | `api.ts` attaches `X-Demo-Token` (from `VITE_DEMO_TOKEN`) to every request; `vite.config.ts` proxy covers `/bootstrap`, `/resolve`, `/admin`, `/timeline`; `frontend/Dockerfile` passes `VITE_DEMO_TOKEN` as a build arg so the token is inlined into the static bundle. |

### Residual risks (require pre-production work)

- **No authentication/RBAC (partially mitigated).** A throwaway `X-Demo-Token` tripwire (#14) now gates all mutating/introspect endpoints and the gateway refuses to boot on Fly without `DEMO_TOKEN`. This is a ship-blocking demo guard, not real auth — the token is in the public bundle and extractable. Full RBAC (#19) remains deferred.
- **Fresh `agent_id` evasion (partially mitigated).** Per-visit randomized `agent_id` (#13) stops a normal user's history bleeding across visits, but `agent_id` is still self-reported and spoofable, so an attacker can still cycle IDs to bypass session/pattern/cumulative tracking. Only authentication (#19) closes this.
- **Bootstrap persistence writes the committed baseline (deferred, #30).** Approved bootstraps write into the git-tracked `policy_config.bootstrap.yaml`; use `POST /admin/reset` (#15) to reset it. A gitignored runtime override is planned.
- **Proxy deployment.** The rate limiter keys on the raw peer IP. Behind a trusted reverse proxy it must be changed to trust `X-Forwarded-For` from that proxy only (`SYN_TRUSTED_PROXY`).

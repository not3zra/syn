# AI Action Firewall — Project Spec for Build Kickoff

**Purpose of this document:** a complete description of what we're building, broken into components, with the reasoning for each technology choice. This is meant to be handed directly to an AI coding agent as a build brief.

**Event context:** AMD Developer Cloud + Fireworks AI hackathon (AMD ACT II, Unicorn Track). AMD compute access arrives Day 2 (July 7); Fireworks API access should be confirmed independently, ideally already working. Submission deadline July 11, 15:00 UTC. Must be containerized (Docker).

---

## 1. One-paragraph description

AI Action Firewall is a governance layer that sits between an AI agent and the real-world tools it's allowed to call (send a payment, delete a file, update a database, etc.). Every tool call is intercepted before it executes, scored against six risk factors by deterministic rule-based code, and either approved, escalated to a human, or blocked — with a full audit trail. An LLM (via Fireworks) is used only to explain the decision in plain English and suggest a remediation path; it never makes the actual allow/block/escalate decision. The system is designed so the core security decision never leaves local, auditable code — the AI layer is advisory, not authoritative.

---

## 2. System components

### 2.1 MCP Gateway (interception layer)

**What it does:** Sits in front of the agent's tool-calling interface. Every tool call an agent attempts to make is routed through the gateway first, instead of executing directly.

**Why this component exists:** Without an interception point, there's nothing to govern — the whole product depends on being able to see and pause a tool call before it runs.

**Technology choice — MCP (Model Context Protocol):** MCP is the emerging standard interface for how agents call tools, so building the gateway as an MCP-compatible proxy means it can sit in front of any MCP-speaking agent, not just a custom-built one. This is also what gives the demo credibility with judges — "works with the same protocol real agents use" beats "works with our mock agent only."

**Implementation for the hackathon:** Mock tools to start (`send_payment`, `update_database`, `delete_file`), each with realistic-looking parameters (amount, recipient, table name, filename). The gateway intercepts the call, passes it to the risk engine, waits for a decision, then either forwards the call to the (mock) tool executor or blocks it.

---

### 2.2 Deterministic Risk Engine (the core — six factors)

**What it does:** Scores every intercepted action against six factors, each computed by plain rule-based code — no model involved in the actual scoring.

| Factor | What it measures | How it's computed |
|---|---|---|
| **Severity** | Can this action cause damage, and how much? | Rule-based lookup by action type + parameters (e.g., payment amount above threshold = higher severity; `delete_file` on a path matching `prod/` = high severity) |
| **Policy** | Does this violate an explicit rule? | Match against a policy config file (YAML/JSON) — e.g., "no payments above $5,000 without approval" |
| **Anomaly** | Is this unusual for this agent/user? | Statistical: z-score or rolling average of amount/frequency vs. recent history |
| **Data Sensitivity** | What kind of data is involved? | Rule-based tagging of parameters/fields (e.g., presence of SSN-like patterns, "payroll," "customer" in table/file names) |
| **Confidence** | How certain is this assessment? | Derived from how much history/context is available — e.g., a brand-new agent/action pair with no history gets a low confidence score by definition |
| **Tool Trust** | Is this a trusted tool/MCP server? | Static tiering: Official / Verified / Unknown / Unsigned, looked up from a config list |

**Why deterministic, rule-based code and not a model:** This is the single most important design decision in the whole project. It directly answers the hardest question a judge or a real buyer will ask — "what stops the AI from hallucinating a risk score?" The answer is: nothing AI-related makes this decision at all. It's plain code, which means it's auditable, reproducible, and explainable by definition. This also means zero GPU dependency for the core product — it works even if the local model step fails entirely.

**Decision-tree floor (applied before any weighted blending):**
- Severity > 90 → **reject**
- Policy violation → **reject**
- Confidence < 40 → **escalate**
- Otherwise → compute a weighted score across all six factors → approve / escalate / block based on thresholds

**Why a decision tree before the weighted score:** Some situations shouldn't be "averaged away" — a severe policy violation shouldn't be able to squeak through because other factors scored low. Hard rules first, nuance second.

**Technology choice — plain application code (Python) + a config file for policy:** No ML framework needed for this component at all. A simple, readable rule engine in Python is faster to build, faster to debug live on stage, and more convincing to a judge who can read the code and see exactly why a decision was made. The policy config being a separate YAML/JSON file (not hardcoded) also sets up the "Policy Playground" stretch feature — editing a rule live without redeploying code.

---

### 2.3 Statistical Anomaly Scorer (default, always-on version of the Anomaly factor)

**What it does:** Computes the Anomaly factor using z-scores / rolling averages / frequency analysis against recent action history for that agent or account.

**Why this exists as the default, not a fallback:** Built and tested on Day 1, before AMD access even arrives, so the Anomaly factor is never a single point of failure for the demo. It's fast, fully explainable, and requires no GPU.

**Technology choice — plain Python (numpy/pandas or even hand-rolled math), no external service:** Deliberately boring and reliable. This factor needs to work on stage every time; a lightweight statistical calculation is far less likely to fail than a live model call.

---

### 2.4 Local Model Upgrade (conditional, optional enhancement to the Anomaly factor)

**What it does:** If it works cleanly, replaces the statistical anomaly scorer with a small local LLM (Qwen2.5-7B preferred over Llama-3.1-8B) running on AMD Developer Cloud, doing anomaly reasoning over the same history data.

**Why this exists at all, given the risk:** It's a stronger technical showcase — actual local GPU inference contributing to a real decision, on the required AMD stack, strengthens the "the decision never leaves the machine" privacy/architecture story. But it's explicitly optional because a broken GPU pipeline shouldn't be able to take down the whole demo.

**Why it's gated behind a Day 2 smoke test before being wired in:** A 30-60 minute test — just load the model, get a response — done the moment AMD access arrives, before touching anything else. If it works cleanly, wire it in. If it doesn't, walk away with zero sunk cost, because the statistical version is already the real, working default from Day 1.

**Technology choice — Qwen2.5-7B via whatever serving path AMD's own docs/tutorials recommend for the instance type (likely ROCm + PyTorch, possibly a plain `transformers.generate()` loop rather than a full inference server like vLLM/TGI):** The risk here isn't drivers, it's mismatched inference-server versions against the pre-configured ROCm image. Sticking to AMD's documented path and preferring the simpler, slower `transformers.generate()` loop over a fragile production-grade inference server maximizes the odds of "it just works" under a hard deadline.

---

### 2.5 Fireworks AI Layer (explanation + remediation — advisory only)

**What it does:** Takes the four-to-six abstracted factor scores (e.g., `severity:82, policy:70, anomaly:30, confidence:55`) — never the raw action content — and generates two outputs:
1. A 2-sentence plain-English explanation of the decision, written for a non-technical approver.
2. A remediation suggestion — what the requester should do instead (e.g., "request manager approval" or "use the staging environment").

**Why this is separated from the decision itself:** This is the second-most important design decision after the deterministic engine. Fireworks is a required part of the hackathon stack, so it needs a real, visible job — but that job must not be "decide whether this is risky," because that would undermine the entire "AI never makes the security call" narrative. Giving it explanation + remediation instead of scoring turns the required-stack constraint into a strength: Fireworks makes the system usable by a human, not just secure.

**Why abstracted scores only, never raw action content:** This is the concrete privacy claim in the pitch — Fireworks (a third-party API) never sees "delete payroll.xlsx" or "send ₹3,00,000" or "customer SSNs," only numbers. That's a real, defensible enterprise-grade argument, not just a talking point.

**Technology choice — Fireworks AI API (required by the hackathon), called with a tightly scoped prompt that only receives the numeric factor scores and the action type category (not parameters):** Satisfies the hackathon's required-stack rule (Fireworks hosts models on AMD hardware, so calling it counts toward the AMD stack requirement even independent of the local model). Caching/pre-warming a set of likely responses ahead of the live demo removes live-network dependency risk on stage.

---

### 2.6 Trust Receipt UI

**What it does:** The visual centerpiece. For every processed action, displays: action name, requesting agent, tool called, a risk gauge/bar, the decision (approved/escalated/blocked), a one-line reason, the full six-factor breakdown, the Fireworks explanation, an audit hash, and a timestamp.

**Why it's styled as a receipt, not a debug panel:** Judges remember visual metaphors. A bank-receipt aesthetic makes the artifact legible to a non-technical viewer instantly, which reinforces the "governance for humans, not just engineers" positioning, and photographs/screenshots well for a pitch deck.

**Technology choice — a simple web frontend (React or plain HTML/CSS/JS, whichever the team is fastest in), rendering data straight from the gateway/decision API:** No framework complexity needed beyond what's comfortable to build fast; the value is entirely in the layout and information hierarchy, not in frontend sophistication.

---

### 2.7 Audit Log (timeline view, with approval flow)

**What it does:** Shows a running history of decisions as a timeline (not a table): e.g. "10:31 Payment Approved → 10:35 Database Modified → 10:40 Delete File Escalated → Approved by Admin." Escalated actions route to a Slack webhook (or a mocked approver inbox if Slack OAuth setup is too slow) for a human approve/reject decision, which then appends to the timeline.

**Why a timeline instead of a table:** Chronological, narrative framing is easier for a judge (or a real approver) to scan quickly and matches how humans actually think about "what happened, in what order."

**Technology choice — simple append-only log (in-memory or lightweight local storage for the hackathon, e.g., SQLite or a JSON file), Slack Incoming Webhooks for escalation notifications:** No need for a production-grade event store in a 5-day build; SQLite or even a JSON file is enough to demo reliably and is fast to build. Slack webhooks are simple to wire up and instantly recognizable to judges as "this integrates into how real teams already work."

---

### 2.9 Session Risk Scorer **[NEW]**

**What it does:** Scores the *sequence* of recent actions within a session (same agent/task), not just each action in isolation. Groups actions under a `session_id`, checks the recent history against a small table of known risky sequences (e.g., `read_file → send_email`, `query_database → update_database`, `check_balance → send_payment`), and computes a cumulative session-severity value alongside the per-action score.

**Why this exists:** This is the field's most-cited unsolved gap in 2026 — governance tools evaluate one tool call at a time, with nothing correlating individually-low-risk actions into a risky pattern (e.g., five escalating database queries in three minutes, or a conversation that starts with "what's the weather" and ends requesting customer records). Neither the leading open standard (OAP) nor Microsoft's Agent Governance Toolkit currently correlates across actions — this is a genuine, currently-unclaimed differentiator, not a cosmetic feature.

**Where it plugs in:** Extends the decision-tree floor (2.2) with one more branch: "if session pattern matches a known risky sequence, or cumulative session severity exceeds threshold, escalate regardless of this action's individual score." Reuses the same per-agent history store the statistical anomaly scorer (2.3) already needs — no new data infrastructure.

**Technology choice — plain Python, a small rules table (YAML/JSON, same pattern as the policy config):** Deterministic and explainable, consistent with the rest of the risk engine's design philosophy. No ML needed; the differentiator is architectural (scoring sequences at all), not the sophistication of the matching logic.

---

### 2.10 Regulatory Tier Mapping **[NEW]**

**What it does:** Adds one more output field to each decision — `regulatory_tier` — mapping the combination of action type, data sensitivity, and severity to a real-world regulatory classification (e.g., EU AI Act risk category — minimal/limited/high-risk/unacceptable — with a note where a US regime such as FINRA or SEC guidance would also apply for financial actions).

**Why this exists:** Practitioners rank "industry standards or frameworks for governance" as the single most-wanted improvement in this space, and the actual regulatory landscape is a patchwork (EU AI Act, California's AI Act, FINRA/SEC/FDA/FTC guidance in the US) that nothing in the current competitive landscape exposes as a first-class, per-decision output. Existing tools map compliance at the *policy* level (a rule was tagged "GDPR-relevant"); almost none surface a live classification on the decision artifact itself.

**Important scope note:** this is an informational classification aid, not a certified legal compliance determination — labeled as such in the UI and in the pitch, the same way Microsoft's own toolkit explicitly disclaims that it doesn't guarantee legal or regulatory compliance by itself.

**Technology choice — a mapping table, structured like the existing policy config, evaluated after the six-factor score is computed:** Near-zero new engineering; the work is in getting the mapping reasonably accurate, not building new infrastructure.

---

### 2.11 Rollback Plan + Expiry on Escalations **[NEW — schema extension]**

**What it does:** Every escalated action's Trust Receipt gains two new fields: a **rollback procedure** (what to do if this gets approved and turns out to be wrong — e.g., "contact recipient bank within 24 hours to request recall") and an **expiry time** (a pending approval that's never actioned should not stay valid indefinitely — e.g., auto-expire after 4 hours and re-route or auto-deny).

**Why this exists:** A mature approval-request schema includes the action, the agent's reasoning trace, estimated impact, a rollback procedure if available, and an expiry time — most governance tools in the field stop at "decision + reason," without either of these two fields. Both are near-zero-cost additions to a schema you're already building.

**Technology choice — additional fields on the existing decision/receipt object, no new component:** Rollback text can come from the same Fireworks remediation call (2.5) with one more instruction in the prompt; expiry is a timestamp field with a simple background check or UI countdown.

---

### 2.12 Stretch features (only if time allows, in priority order)

1. **Simulation Mode** — a LIVE/SIMULATION toggle that runs the full pipeline (interception → scoring → decision → explanation) without actually executing the underlying tool call. Good, safe, interactive demo material with no build risk once the core pipeline works.
2. **Policy Playground** — edit one rule live in the policy config (e.g., "no payments above $5,000") and rerun the same action to watch the decision flip from Approved to Escalated without redeploying. Demonstrates flexibility without touching code, and the policy-as-config-file decision from 2.2 is what makes this cheap to build.
3. **Replay** — click a past audit-log entry and reconstruct exactly the decision that was made from stored input state. Deprioritized because it requires snapshotting full input state per decision — a real feature, not a UI add-on — and shouldn't compete with the Trust Receipt or audit log for build time.

---

## 3. Containerization

**What it does:** The entire system (gateway, risk engine, Fireworks integration, frontend, audit log) is packaged with Docker/docker-compose from Day 1, not bolted on at the end.

**Why this matters and why it's built early:** It's a hard hackathon requirement, and building the Docker setup from Day 1 means the team is developing inside the actual submission environment the whole time — avoiding a last-minute "it works on my machine but not in the container" scramble on Day 5.

---

## 4. Data flow summary

```
Agent attempts tool call
        ↓
MCP Gateway intercepts
        ↓
Deterministic Risk Engine (6 factors, local code, no GPU required)
        ↓
Session Risk Scorer (checks this action against recent session history)
        ↓
Decision-tree floor check (hard rules first, now including session pattern match)
        ↓
Weighted score (if no hard rule triggered)
        ↓
Regulatory Tier tag attached (EU AI Act / relevant US regime, informational only)
        ↓
   ┌────┴────┐
   ↓         ↓
Approve   Escalate/Block
   ↓         ↓
Tool      Slack/approver notification
executes  (includes rollback plan + expiry)
   ↓         ↓
   └────┬────┘
        ↓
Abstracted scores (numbers only, action-level + session-level) sent to Fireworks
        ↓
Fireworks returns: plain-English explanation + remediation suggestion + rollback text
        ↓
Trust Receipt rendered (action risk gauge + session risk gauge + regulatory badge) + Audit Log timeline updated
```

---

## 5. Why this combination of technology choices, as a whole

- **Deterministic core, advisory-only AI layer:** directly answers the "can the AI hallucinate a risk decision" objection, and means the core product works even under total AMD/GPU failure.
- **MCP as the interception standard:** makes the gateway credible against real agent frameworks, not just a toy demo.
- **Fireworks scoped to explanation/remediation, never scoring, never raw content:** turns a required-stack constraint into a genuine privacy/architecture selling point instead of a checkbox.
- **Local model as a strictly optional, tested-before-committed upgrade:** captures the technical-ambition upside of real AMD GPU inference without making it a single point of failure for the whole submission.
- **Config-file-driven policy:** cheap now (Day 2), and directly enables the Policy Playground stretch feature later without extra engineering.
- **Boring, reliable storage (SQLite/JSON) and Slack webhooks over a production event pipeline:** appropriate scope for a 5-day build — every technology choice here optimizes for "will definitely work live on stage" over "impressive-sounding infrastructure."
- **Session Risk Scorer over per-action-only scoring:** the field's own 2026 commentary names cross-action behavioral correlation as the unsolved gap even the leading players (OAP, Microsoft's toolkit) don't address — this is the genuine differentiator, not the six-factor score alone.
- **Regulatory Tier Mapping as an informational tag, not a compliance guarantee:** gives judges and real buyers a concrete, standards-oriented hook ("industry standards/frameworks" is practitioners' most-requested improvement) without overclaiming legal certification.
- **Rollback plan + expiry on every escalation:** closes the two fields most governance schemas skip, at near-zero build cost since both reuse existing Fireworks calls and the receipt object.

---

## 6. Suggested repo structure (starting point for the coding agent)

```
ai-action-firewall/
├── docker-compose.yml
├── gateway/              # MCP interception layer
│   ├── mcp_server.py
│   └── tools/            # mock tools: send_payment, update_database, delete_file
├── risk_engine/          # deterministic core
│   ├── severity.py
│   ├── policy.py
│   ├── anomaly_statistical.py
│   ├── anomaly_local_model.py   # optional, wired in only if Day 2 smoke test passes
│   ├── data_sensitivity.py
│   ├── confidence.py
│   ├── tool_trust.py
│   ├── decision_tree.py
│   └── policy_config.yaml
├── fireworks_layer/
│   └── explain_and_remediate.py
├── audit_log/
│   ├── store.py           # SQLite or JSON-backed
│   └── slack_webhook.py
├── frontend/               # Trust Receipt UI + timeline + (stretch) Simulation/Playground
└── README.md               # submission requirements checklist at the top
```

---

## 7. Immediate build order for tomorrow (Day 1, July 6 — see full day-by-day plan for the rest of the week)

1. Repo + docker-compose skeleton.
2. Confirm Fireworks API access works end-to-end with a trivial call.
3. MCP gateway skeleton with a hardcoded fake score, full round-trip.
4. Build all six risk factors as real rule-based logic + the statistical anomaly scorer + the decision-tree floor.
5. Test against 10-15 scenarios, including the ambiguous confidence/severity edge case.

This should leave the entire deterministic engine done and tested by end of Day 1, ahead of AMD access arriving Day 2.

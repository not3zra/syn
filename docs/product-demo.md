# Product Demo — syn: AI Action Firewall

**Total runtime:** ~4 minutes

---

## Setup (pre-demo)

```bash
# Ensure the gateway and frontend are running
docker compose up --build

# Reset state for a clean demo
# (no DEMO_TOKEN set locally → the check is a no-op on local dev)
curl -X POST http://localhost:8000/admin/reset
```

Frontend: `http://localhost:3000`

---

## Beat 1: Basic Governance (30s)

**Goal:** Show that a normal action is approved and a dangerous one is blocked.

### 1a — Low-risk approval

Open the browser to the Console (Intercept) view. Select `send_payment` and set:
- amount: `100`
- currency: `USD`
- recipient: `alice`

**Send the call.**

**Expect:** ✅ **Approved** — Trust Receipt shows:
- Decision badge: green "APPROVED"
- Risk gauge in the green zone (~18.5)
- Factor breakdown: severity 20, policy 0, all others low
- AI explanation: "This is a routine low-value payment"
- Regulatory badge: Minimal Risk

**Say:** *"A $100 payment to an internal recipient — low severity, no policy violation, high tool trust. Approved instantly."*

### 1b — Policy violation blocked

Now set:
- amount: `10000`
- currency: `USD`
- recipient: `bob`

**Send the call.**

**Expect:** 🚫 **Blocked** — Trust Receipt shows:
- Decision badge: red "BLOCKED"
- Trigger string: `decision_tree:policy_floor`
- Risk gauge in the red zone
- Policy score: 100

**Say:** *"Same tool, but now the recipient is external and the amount exceeds the $5,000 policy limit. Blocked at the decision-tree floor — the weighted blend never even runs."*

### 1c — Destructive database query

Select `query_database` with:
- query: `DROP TABLE users`

**Send the call.**

**Expect:** 🚫 **Blocked** — high severity from destructive SQL patterns.

**Say:** *"Data sensitivity floor catches attempts to drop tables or access PII. Blocked before execution."*

---

## Beat 2: Unknown Tool → Failed Closed → Bootstrap (1m)

**Goal:** Show that unknown tools are blocked with auto-generated rules.

### 2a — Unknown tool blocked

Select a tool not in the config (e.g., `send_email`):
- to: `admin@example.com`
- subject: `Test`
- body: `Hello`

**Send the call.**

**Expect:** 🚫 **Blocked** — Trust Receipt shows:
- Trigger: `gateway:unknown_tool`
- Explanation: "This tool is not registered in the security policy. Blocked by default."

**Say:** *"An unknown tool appears. We fail closed — blocked immediately. But something happened in the background..."*

### 2b — Review pending rules

Switch to the **Bootstrap** view, then the **Pending Approvals** tab.

**Expect:** A pending rule card for `send_email` with status `pending` (or `generating` → `pending` within a few seconds). Shows:
- Tool name and description
- Proposed severity and policy rules with LLM reasoning
- Edit button (inline YAML textarea)
- Approve / Reject buttons

**Say:** *"While the action was blocked, the gateway auto-generated a proposed security profile for this tool using the LLM. The reviewer can edit, approve, or reject it — no manual YAML writing."*

### 2c — Approve the pending rule

Click **Approve** on the `send_email` card.

**Expect:** Success notification. The rule is written to `policy_config.bootstrap.yaml`.

### 2d — Re-test the now-approved tool

Switch back to Intercept mode. Send the same `send_email` call again.

**Expect:** ✅ **Approved** (or escalated depending on generated rules).

**Say:** *"One click to approve. Now the tool is governed — no longer blocked."*

---

## Beat 3: AI Bootstrap from Scratch (1m)

**Goal:** Show the full Bootstrap workflow generating rules from tool schemas.

### 3a — Introspect tools

If not already on the Bootstrap tab, navigate there.

Click **Introspect Tools** to auto-fetch schemas for registered tools (or paste a custom schema JSON in the Manual textarea).

**Expect:** A grid of tool cards, each showing:
- Tool name, description, parameters
- Proposed severity and policy rules with LLM reasoning comments
- Policy descriptions in bullet form
- A diff view showing additions vs current config (green lines for new rules)

### 3b — Review and edit

Click into a tool card. The editable YAML textarea shows the full proposed config.

Make a small tweak (e.g., change a severity score).

**Expect:** The textarea updates in place.

**Say:** *"Every generated rule is editable before approval. The LLM's reasoning is preserved as YAML comments so you know why each score was chosen."*

### 3c — Approve

Click **Approve and Write Config**.

**Expect:** Success. Config is written to disk. Navigate to Intercept — the bootstrapped tools now have active governance.

---

## Beat 4: Session-Aware Pattern Detection (1m 30s)

**Goal:** Demonstrate the core differentiator — detecting a dangerous sequence of individually-safe actions.

### Setup

Use a single `agent_id` (e.g., `demo-session-1`) across all four calls. The frontend auto-generates an `agent_id` per page load.

### Step 1: check_balance

```json
{
  "action_type": "check_balance",
  "parameters": {"account_id": "123"},
  "agent_id": "demo-session-1",
  "mode": "live"
}
```

**Expect:** ✅ **Approved** — severity ~15, no policy issue. Gauge green.

**Say:** *"Checking an account balance. Low risk, no mutation possible. Approved."*

### Step 2: check_balance (again)

Same call.

**Expect:** ✅ **Approved** — confidence is higher now (seen this before). Still green.

**Say:** *"A second balance check. Still approved — individually, neither is a concern."*

### Step 3: check_balance (third time)

Same call.

**Expect:** ✅ **Approved** — but note cumulative severity is now 45.

**Say:** *"Three balance checks. The session history is building up, but individually each one is fine."*

### Step 4: send_payment

```json
{
  "action_type": "send_payment",
  "parameters": {"amount": 500, "currency": "USD", "recipient": "alice"},
  "agent_id": "demo-session-1",
  "mode": "live"
}
```

**Expect:** ⚠️ **Escalated** — Trust Receipt shows:
- Decision badge: yellow "ESCALATED"
- Trigger: `session:pattern_matched:check_balance_send_payment`
- Session risk gauge in the yellow zone
- Factor breakdown: severity 20 (still low!), but session score is 80
- Explanation: "Three balance checks followed by a payment — this matches a known reconnaissance-to-execution pattern. Escalated to a human for review."
- Escalation timer counting down (default 5 minutes)
- Expiry timer showing

**Say:** *(point to the trigger string)* *"This is the core differentiator. Each of the first three actions was harmless on its own — severity 15, no policy violation, nothing suspicious. Any per-action-only governance system would approve all four. But syn correlates across the session and recognizes the pattern: three reconnaissance actions followed by an execution. Escalated to a human."*

**Say:** *"The most dangerous AI actions are the ones that look safe in isolation. Only session-aware governance can catch them."*

---

## Beat 5: Audit Timeline (30s)

**Goal:** Show the audit trail.

Navigate to the **Timeline** view.

**Expect:** A chronological list of all actions, each showing:
- Timestamp
- Decision badge (green/yellow/red)
- Action type and parameters (abstracted)
- Trigger string
- Regulatory badge
- Expand for full receipt details

Use the outcome filter to show only escalated or blocked actions.

**Say:** *"Every action is logged with a full audit trail — decision, trigger, factor scores, regulatory tags. Filterable by outcome. Ready for compliance review."*

---

## Beat 6: Regulatory Tagging (30s)

**Goal:** Show regulatory compliance context.

Revisit any receipt from the timeline. Point out the regulatory badge:

- `send_payment` → shows **High Risk** (Article 6) + **FINRA**, **SEC** flags
- `check_balance` → shows **Minimal Risk**
- A prohibited action → would show **Unacceptable Risk** (Article 5)

**Say:** *"Every action is tagged with its EU AI Act tier and relevant US regulatory regimes. Informational — not a legal certification — but it gives compliance teams immediate visibility into which actions might need additional scrutiny."*

---

## Recap

| Beat | What It Shows |
|------|---------------|
| 1 | Basic approve / escalate / block based on six factors + decision tree |
| 2 | Unknown tools fail closed; auto-generated rules appear in Pending Approvals |
| 3 | AI Bootstrap generates a full security profile from tool schemas in seconds |
| 4 | **Session-aware pattern detection** — individually-safe actions flagged as a dangerous sequence |
| 5 | Audit timeline with full traceability |
| 6 | Regulatory tier mapping (EU AI Act + US regimes) |

---

## Troubleshooting

### LLM not responding
- Verify `LLM_PROVIDER` and `LLM_API_KEY` in `.env`
- Try `GET /health/llm` to force a fresh probe
- For demo without LLM, set `LLM_PROVIDER=mock` — mock returns canned explanations

### Frontend can't reach backend
- Check `http://localhost:8000/health` returns `{"status": "ok"}`
- In Docker: `docker compose logs gateway` for backend errors

### Bootstrap generation fails
- Check the LLM provider has sufficient token quota (Groq free tier: 100K/day)
- Switch to Fireworks for higher throughput: `LLM_PROVIDER=fireworks`
- Retry failed rules from the Pending Approvals tab

### Reset for re-demo
```bash
curl -X POST http://localhost:8000/admin/reset
```
This clears all audit log entries, pending rules, and resets `policy_config.bootstrap.yaml` to `tools: {}`.

# AI Action Firewall — Revised Final Plan (Post-Review, AMD-Access-Delayed Version)

This is the tightened version of the plan, incorporating the review pass, **plus a restructure for a confirmed AMD Developer Cloud access delay: access doesn't arrive until Day 2 (July 7) due to late registration.** Changes from the previous version are marked **[CHANGED]**. Everything not marked is carried over as-is because it already held up.

**Key date anchor:** Day 1 = July 6, Day 2 = July 7 (AMD access arrives), Day 3 = July 8, Day 4 = July 9, Day 5 = July 10. Submission deadline: July 11, 15:00 UTC.

**[CHANGED — core restructuring logic]** Almost the entire deterministic engine (severity, policy, data sensitivity, confidence, tool-trust scoring, the statistical anomaly scorer, the decision-tree floor, the MCP gateway skeleton, Docker setup, Fireworks integration) requires no AMD hardware at all. Only the ROCm smoke test and the optional local-model upgrade actually need AMD access. So the fix for the delay isn't losing a day — it's front-loading all AMD-independent work into Day 1, so the deterministic engine is fully built and tested a day ahead of the original schedule, and the smoke test simply happens the moment access arrives on Day 2 instead of on Day 1.

**[CHANGED — action item for today, before Day 1]** Confirm Fireworks API access status separately from AMD access. There's no reason Fireworks should be affected by late registration, but if it is, that's a different and more urgent problem — check this today, not on Day 1.

---

## 0. Non-negotiables locked before Day 1 starts **[CHANGED — moved up from Day 5]**

Do this in the first hour, before any code:

- [ ] Open the actual lablab.ai submission page for this hackathon and confirm: exact required fields (repo link, demo video length/format, write-up length, any specific template), submission mechanism, and time zone handling for the July 11, 15:00 UTC deadline.
- [ ] Confirm Track 3 (Unicorn Track) submission criteria specifically — check if it has different requirements than the other tracks.
- [ ] Write these requirements down somewhere visible (top of README) so Day 5 has zero surprises.

This costs 10-15 minutes and removes the one risk in the original plan that was purely due to not looking.

---

## 1. Positioning (unchanged, carry forward as-is)

- One-liner: **"Every AI agent today can call tools. None of them have a security checkpoint before doing it."**
- Category: **Execution Governance for AI Agents** — not "security." Security, compliance, audit, human approval, and policy are sub-features of the larger category.
- Track: Unicorn Track (creativity, originality, product potential).

**[CHANGED — updated]** One explicit differentiation line for the pitch, now foregrounding session-risk correlation as the primary claim (validated as the field's own named unsolved gap in 2026), with the six-factor score and regulatory tagging as supporting depth:

> "Existing tools score one action at a time. We score the pattern — five individually low-risk actions can still add up to something dangerous, and this is the first governance layer that catches that before it happens, not after. On top of that, every decision is made by deterministic code, never an LLM judgment call, and tagged against the regulatory framework it actually falls under."

Say this explicitly in the pitch. Don't leave the differentiation implicit.

---

## 2. Architecture (unchanged)

```
        Local Deterministic Engine
              ↑
              |
Agent → Gateway → Decision
              |
              ↓
        Fireworks AI (explanation + remediation only)
              ↓
        Tool executes
```

The decision never leaves the machine. Fireworks only ever sees abstracted scores (severity:82, policy:70, anomaly:30), never raw action content. This holds whether or not the local anomaly model ends up running — worth its own beat in the pitch either way.

---

## 3. Risk schema (unchanged) — six factors

1. **Severity** — can this action cause damage?
2. **Policy** — does it violate a rule?
3. **Anomaly** — is this unusual? (statistical by default, local-model upgrade if Day 1 smoke test passes)
4. **Data Sensitivity** — what data is involved?
5. **Confidence** — how certain is this assessment? Low confidence is itself a signal, not a footnote.
6. **Tool Trust** — Official / Verified / Unknown / Unsigned tiers.

**Decision-tree floor before any weighted score:**
- Severity > 90 → reject
- Policy violation → reject
- Confidence < 40 → escalate
- Otherwise → weighted score

**[CHANGED — added]** Add an explicit test scenario on Day 2 for the interaction case: mid-confidence + high risk (e.g., confidence 45, risk 85) to make sure the tree and weighted score don't produce a contradictory or confusing result together. Don't just test the individual factors — test one deliberately ambiguous combination.

---

## 4. Day-by-day plan **[CHANGED — restructured around AMD access arriving Day 2, not Day 1]**

### Day 0 / today — before the hackathon officially starts
- Do Section 0 (submission requirements) — needs nothing, do it now.
- Confirm Fireworks API access status specifically. Late registration delayed AMD compute access; verify Fireworks isn't also affected. If it is, treat that as a separate, more urgent problem to escalate immediately.

### Day 1 — July 6 (no AMD access yet — front-load everything AMD-independent)
- Lock vertical (fintech/payments), freeze the six-factor schema.
- Set up repo + Docker/docker-compose skeleton from the start.
- Confirm Fireworks API working end-to-end (if not already confirmed on Day 0).
- Build the MCP gateway skeleton with a hardcoded fake score, full round-trip working end-to-end.
- **[CHANGED — pulled forward from original Day 2]** Build severity, policy, data sensitivity, confidence, and tool-trust scoring as real rule-based logic (policy config file) — not a skeleton, the actual working version.
- **[CHANGED — pulled forward from original Day 2]** Build the **statistical anomaly scorer as the real, default version** (z-score / rolling average / frequency).
- **[CHANGED — pulled forward from original Day 2]** Add the decision-tree floor (severity > 90 → reject, policy violation → reject, confidence < 40 → escalate, else → weighted score).
- **[CHANGED — pulled forward from original Day 2]** Test against 10-15 scenarios, including the ambiguous confidence/severity interaction case (e.g. confidence 45, risk 85).
- **Goal:** by end of Day 1, the entire deterministic engine is done and tested — a day ahead of the original schedule, purely because AMD access forced the reordering.

### Day 2 — July 7 (AMD access arrives)
- **First thing, before anything else today:** 30-60 minute ROCm smoke test — load any model, get any response. Use whatever serving path AMD's own docs show for the instance type; don't freelance the stack. Prefer Qwen2.5-7B over Llama-3.1-8B for lighter serving; a plain `transformers.generate()` loop beats a fragile inference server under this timeline.
- If it succeeds cleanly: wire in the local model as the upgrade to the anomaly factor.
- If not: keep the statistical version from Day 1 — no time lost, nothing left half-built, move on.
- **[NEW]** Build the Session Risk Scorer: `session_id` grouping on top of the existing per-agent history store, a small risky-sequence rules table (`read_file → send_email`, `query_database → update_database`, `check_balance → send_payment`), and one more decision-tree branch that escalates on a session-pattern match regardless of the individual action's score. Pure Python, no AMD dependency — this is the project's main differentiator, so it gets priority over starting Fireworks work today if time is tight.
- **[NEW]** Build the Regulatory Tier Mapping config (EU AI Act categories + a flag for relevant US regimes like FINRA/SEC where the action type is financial) and wire it as an additional output field on the decision object.
- Start the Fireworks explanation + remediation layer if time remains today: two outputs (explanation + remediation suggestion), fed only abstracted scores (now including the session-level score), never raw action content.

### Day 3 — July 8
- Finish the Fireworks explanation + remediation layer if it spilled over from Day 2.
- **[NEW]** Extend the Fireworks remediation prompt to also produce rollback text for escalated actions; add an expiry timestamp field to the decision/receipt object (simple countdown, no new component).
- Buffer for any local-model wiring that spilled over from Day 2.
- If everything above is already done: start Trust Receipt UI work early.

### Day 4 — July 9 — UI, audit log, integration testing
- Build the Trust Receipt UI (bank-receipt aesthetic): action, agent, tool, risk gauge, decision, one-line reason, full factor breakdown, AI explanation, audit hash, timestamp.
- **[NEW]** Add a second, smaller gauge for session risk next to the per-action risk gauge, a regulatory-tier badge, and the rollback/expiry fields to the receipt layout.
- Build the audit log as a timeline (not a table): e.g. 10:31 Payment Approved → 10:35 Database Modified → 10:40 Delete File Escalated → Approved by Admin.
- Build Slack escalation (or mocked approver inbox as fallback if OAuth is slow).
- Test Fireworks caching/pre-warming against the actual UI today — confirm cached responses render correctly and the demo doesn't silently depend on a live call.
- Stretch, in priority order if time remains: Simulation Mode toggle (LIVE/SIMULATION) → Policy Playground (edit a rule live, rerun, watch the decision flip) → replay (click a past entry, reconstruct the exact decision — requires snapshotting full input state per decision; don't let it compete with Trust Receipt or audit log polish).

### Day 5 — July 10 — Polish, rehearsal, submit
- Bug fixing, run the three-tier demo (low/medium/high risk) repeatedly.
- **[NEW]** Add a fourth demo beat: three or four individually-approved low-risk actions in a row, then the same-looking action gets escalated purely on session pattern — this is the single strongest live-demo moment in the plan, since no current competitor correlates across actions this way. Rehearse it specifically.
- Confirm all cached/pre-warmed Fireworks responses still work — this should already be tested from Day 4; today is final verification, not first-time testing.
- Finalize the pitch: lead with the problem statement, not the architecture diagram. Include the explicit differentiation line from Section 1, updated to foreground session-risk correlation as the primary claim, with the six-factor score and regulatory tagging as supporting depth.
- Submit against the requirements confirmed on Day 0 — this should be a checklist exercise, not a discovery exercise.
- Reserve the evening as genuine buffer, before the July 11, 15:00 UTC deadline.

---

## 5. Summary of what changed and why

| Change | Reason |
|---|---|
| Submission requirements moved to Day 1 (hour one) | Previously deferred to Day 5; a 10-minute check shouldn't carry deadline risk |
| Explicit differentiation line added to pitch | Originality re-score flagged a prior similar entry; the differentiator (decision-tree floor, not the word "governance") needs to be said out loud, not left implicit |
| Replay demoted to stretch goal | It's a real feature (state snapshotting) disguised as a UI flourish; shouldn't compete with Trust Receipt/audit log for Day 4 time |
| Fireworks caching moved to Day 4 | De-risks the one live-network dependency a day earlier, leaving Day 5 for verification only, not first-time testing |
| Added ambiguous-case test scenario | Confirms the decision tree and weighted score behave sensibly together, not just individually |
| **[NEW]** Entire schedule shifted to Day 0-5 = July 5-10, with the deterministic engine front-loaded into Day 1 | AMD Developer Cloud access delayed to Day 2 (July 7) due to late registration; the smoke test and local-model upgrade are the only pieces that actually need AMD hardware, so front-loading the AMD-independent work preserves the original de-risking sequence instead of losing a day to the delay |
| **[NEW]** Session Risk Scorer added (Day 2), scoring action sequences not just single actions | Validated as the field's own named unsolved gap in 2026 — neither the leading open standard (OAP) nor Microsoft's Agent Governance Toolkit correlates across actions; this is now the primary differentiator and pitch claim |
| **[NEW]** Regulatory Tier Mapping added (Day 2), tagging each decision against EU AI Act / relevant US regimes | Practitioners rank "industry standards or frameworks for governance" as their top-requested improvement; near-zero build cost, concrete hook for judges and real buyers, explicitly framed as informational, not a compliance guarantee |
| **[NEW]** Rollback plan + expiry fields added to every escalation (Day 3) | Closes the two fields most governance schemas skip; reuses the existing Fireworks remediation call and receipt object, no new component |

Everything else — the six-factor schema, the local-model de-risking sequence, the architecture split, the receipt-styled UI, the "Execution Governance" positioning — is unchanged because it already held up under review.

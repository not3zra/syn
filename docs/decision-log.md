# Decision Log

Every decision made during planning, with the hackathon choice and what would change if time/simplicity were not a constraint. Only decisions that would *meaningfully* improve the product if redone are listed.

---

| # | Decision | Hackathon choice | Ideal (unconstrained) | Why it matters |
|---|---|---|---|---|
| 1 | Session ID source | Auto-generated time buckets (10-min windows) | Agent-provided explicit session IDs | Time bucketing is a heuristic — it splits legitimate long-running tasks and merges unrelated actions. Explicit session IDs from the agent are semantically accurate. |
| 2 | Sequence matching | Ordered pairs (A→B) | N-action chains with gap tolerance | Pairs catch simple patterns but miss longer attack chains or sequences with benign actions interleaved. Gap-tolerant chains are harder to evade. |
| 3 | Cumulative severity | Simple sum, threshold=70 | Decay-weighted sum | Simple sum lets old actions accumulate forever. Decay weighting (recent actions matter more) is a realistic risk model instead of an arbitrary counter. |
| 4 | AI Bootstrap input | One-time introspection | Continuous auto-registration on new tool appearance | One-time setup means stale rules. Auto-registration keeps rules up to date without manual re-runs. |
| 5 | AI Bootstrap prompt | Hardcoded fintech context | Dynamic context from knowledge base / vector store | Hardcoded context only works for one domain. Dynamic context lets AI Bootstrap generate relevant rules for any codebase without editing prompts. |
| 6 | AI Bootstrap review | Minimal table + "Approve All" | Per-tool staged approval with diff view and rollback | "Approve All" is fast but risky. Per-tool approval with diff view gives the human reviewer confidence to accept or revert individual generated rules. |
| 7 | Slack integration | Incoming webhook (post-only) | Full Slack app with interactive approve/deny buttons | Webhooks post notifications but require switching to the UI to act. Interactive buttons let the approver approve or deny from Slack. |
| 8 | Database | SQLite | PostgreSQL | Irrelevant for a single-user demo. PostgreSQL matters when concurrent access, multi-user, and production scale are required. |

## Round 2 — Post-submission-hardening decisions

| # | Decision | Hackathon choice | Ideal (unconstrained) | Why it matters |
|---|---|---|---|---|
| 9 | Session ID source (revised) | Agent-managed lifecycle with gateway-issued IDs (session_intent: start/continue/end), time-bucket fallback | Same | Gateway owning the session ID neutralizes the lying-agent attack. Time-bucket fallback preserves backward compat for unmodified agents. |
| 10 | Sequence matching (revised) | N-action subsequence matching, unlimited gap tolerance, agent-wide sliding window | N-action subsequence with configurable gap tolerance | Pairs missed padded attacks. Unlimited gap catches any subsequence match but may add false positives in long sessions. |
| 11 | Cumulative severity (revised) | Agent-wide sliding time window (30 min default), simple sum | Decay-weighted sum within sliding window | Sliding window prevents session-boundary evasion. Decay-weighting would add realism but wasn't needed for the demo. |
| 12 | AI Bootstrap input | Continuous auto-registration on unknown tool with pending review queue | Same, with auto-rollback if human rejects within a window | One-time setup means stale rules. Auto-registration keeps rules up to date without manual re-runs. Pending queue keeps human in loop. |
| 13 | AI Bootstrap prompt | Dynamic context from domain_config.yaml | Dynamic context from vector store over org policy docs | Config file is the right level for a demo. Vector store matters when an org has 100+ policy documents. |
| 14 | Slack integration | Incoming webhook with resolve URL link. Interactive buttons deferred to production. | Full Slack app with interactive approve/deny buttons | Webhook + link is functional. Interactive buttons require OAuth + public endpoint — a demo-day risk. |
| 15 | Auto-registration notification | Flash-on-load message on Pending Approvals tab | Live polling or websocket push for badge count | Flash message is simpler to build and verify — no timing race to test. Generation is already done by BackgroundTasks before user navigates to the tab anyway. |
| 16 | Auto-registration error handling | Error status with "Retry generation" button; pending_rules table tracks generation_attempts counter | Auto-retry with exponential backoff | Manual retry is simpler to reason about and demo — the reviewer can see the error, understand it, and trigger a retry. Auto-retry would silently mask failures. |
| 17 | Bootstrap audit trail | Approve/reject actions logged to decisions table as bootstrap_approved/bootstrap_rejected entries | Dedicated bootstrap audit table | Logging to the existing timeline is simpler and creates a coherent narrative (blocked → generated → approved → governed) in the same view. |
| 18 | Pending rules diff view | Line-based red/green diff over editable YAML | Full side-by-side diff with syntax-highlighted AST comparison | Line-based diff is simple to build and reads clearly for a demo. Side-by-side AST diff is a production UX investment. |

## What this tells you

Twenty decisions separate the 5-day hackathon submission from a production product. The first set (1-3) were the original session-risk differentiator improvements. Round 2 (9-11) revises those same three decisions based on deeper threat modeling. The AI Bootstrap and Slack improvements (4-7, 12-14) improve setup automation and UX. The auto-registration refinements (15-18) harden the design that was previously scoped loosely. The database (8) matters later but not now.

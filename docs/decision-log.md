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

## What this tells you

Eight decisions separate the 5-day hackathon submission from a production product. The first three (session IDs, sequence matching, decay weighting) improve the core differentiator — session-risk scoring. The next three (AI Bootstrap input, prompt, review) improve the setup automation. The Slack integration is a UX polish. The database matters later but not now.

#!/usr/bin/env python3
"""Realistic, scenario-based behaviour test for the syn gateway.

Distinct from ``test_workflow.sh`` (an adversarial / edge-case fuzz suite that
spins up its own server, wipes the audit DB, and uses a unique agent per
section). This script is a *pure client* written in the Python standard library
only (no third-party deps, no server management) that drives an already-running
gateway the way a real agent session would:

* Each scenario runs as its own focused agent session, so the decision being
  exercised is deterministic (the engine's session branch — recon→action fraud
  patterns and cumulative-severity thresholds — is intentionally isolated to the
  scenarios that demonstrate it).
* Plausible tool sequences: a first-time payment that needs review, a trusted
  payment that goes through, an invalid amount, an over-limit payment, a
  recon-then-pay fraud pair, PII access, destructive DDL, a cumulative buildup,
  and an unknown tool.
* Per-step assertions on ``decision`` + ``trigger`` + a grounded, human-readable
  ``reason`` (the engine now threads a cause string through every decision).
* A closing timeline check confirming the audit trail reflects the session.

Usage:
    python scripts/syn_test_scenarios.py                 # against http://localhost:8000
    SYN_API_BASE=http://host:8000 python scripts/syn_test_scenarios.py
    SYN_DEMO_TOKEN=secret python scripts/syn_test_scenarios.py   # sends X-Demo-Token
    python scripts/syn_test_scenarios.py --reset         # wipe the demo first (needs token)

Exits non-zero if any assertion fails.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import uuid

API_BASE = os.environ.get("SYN_API_BASE", "http://localhost:8000").rstrip("/")
DEMO_TOKEN = os.environ.get("SYN_DEMO_TOKEN")
HTTP_TIMEOUT = float(os.environ.get("SYN_HTTP_TIMEOUT", "60"))

# Unique per run so agent sessions start clean (the audit store is shared).
RUN = uuid.uuid4().hex[:8]


def _request(method: str, path: str, payload: dict | None = None) -> tuple[int, dict | None]:
    url = f"{API_BASE}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if DEMO_TOKEN:
        headers["X-Demo-Token"] = DEMO_TOKEN
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"detail": raw}
    except urllib.error.URLError as e:
        return -1, {"detail": str(e.reason)}


def intercept(action_type: str, parameters: dict, agent_id: str, mode: str = "live") -> dict:
    status, body = _request(
        "POST",
        "/intercept",
        {
            "action_type": action_type,
            "parameters": parameters,
            "agent_id": agent_id,
            "mode": mode,
        },
    )
    if status != 200 or not isinstance(body, dict):
        raise RuntimeError(f"/intercept returned {status}: {body}")
    return body


def get_timeline() -> list:
    status, body = _request("GET", "/timeline")
    if status != 200 or not isinstance(body, list):
        raise RuntimeError(f"/timeline returned {status}: {body}")
    return body


def reset_demo() -> None:
    status, body = _request("POST", "/admin/reset")
    if status != 200:
        raise RuntimeError(f"/admin/reset returned {status}: {body}")
    print("  ↳ demo reset\n")


class Results:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        if ok:
            self.passed += 1
            print(f"  [PASS] {name}")
        else:
            self.failed += 1
            print(f"  [FAIL] {name}  {detail}")
        return ok


def step(res: Results, agent: str, action_type: str, parameters: dict, agent_id: str,
         expected: str | set, trigger_sub: str | None = None) -> dict | None:
    label = f"{agent} → {action_type}{(' ' + json.dumps(parameters)) if parameters else ''}"
    # Each run gets a unique id appended to agent ids so scenarios start from a
    # clean session (the audit store is shared, so reusing an id would carry
    # prior-run history and make "first use needs review" assertions flaky).
    aid = f"{agent_id}-{RUN}"
    try:
        resp = intercept(action_type, parameters, aid)
    except Exception as e:  # network/timeout — record as a failure, keep going
        res.check(f"{label} == {expected}", False, f"(request error: {e})")
        return None

    decision = resp.get("decision")
    reason = resp.get("reason")
    trigger = resp.get("trigger", "")
    print(f"  {label}\n        syn decided: {decision}  | trigger: {trigger}")
    print(f"        because: {reason}")

    exp_set = {expected} if isinstance(expected, str) else set(expected)
    ok = decision in exp_set
    ok &= bool(reason) and isinstance(reason, str)
    if trigger_sub:
        ok &= trigger_sub in trigger
    res.check(
        f"{label} == {expected}",
        ok,
        f"(decision={decision!r}, trigger={trigger!r}, reason={reason!r})",
    )
    return resp


def main() -> int:
    parser = argparse.ArgumentParser(description="syn realistic scenario test")
    parser.add_argument("--reset", action="store_true", help="reset the demo before running")
    args = parser.parse_args()

    print(f"== syn realistic scenario suite == target: {API_BASE}")
    if DEMO_TOKEN:
        print("  (sending X-Demo-Token)")
    if args.reset:
        reset_demo()

    res = Results()

    # ------------------------------------------------------------------ #
    # Fresh agent: a brand-new agent starts at neutral trust and is approved.
    # ------------------------------------------------------------------ #
    print("\n== Scenario: fresh agent payment (pay-trust) ==")
    step(res, "pay-trust", "send_payment", {"amount": 80, "currency": "USD", "recipient": "alice"},
         "scenario-pay-trust", "approved")

    # ------------------------------------------------------------------ #
    # New tool for an agent with history elsewhere → escalated for low
    # confidence (the engine only drops confidence below the floor when the
    # agent has done other things but never this specific action).
    # ------------------------------------------------------------------ #
    print("\n== Scenario: new tool, low confidence (conf-newtool) ==")
    step(res, "conf-newtool", "send_payment", {"amount": 80, "currency": "USD", "recipient": "alice"},
         "scenario-conf-newtool", "approved")
    step(res, "conf-newtool", "query_database", {"query": "SELECT count(*) FROM products"},
         "scenario-conf-newtool", "escalated", trigger_sub="confidence_floor")

    # ------------------------------------------------------------------ #
    # Invalid amount must be blocked, with a reason naming the bad amount.
    # ------------------------------------------------------------------ #
    print("\n== Scenario: invalid amount (pay-invalid) ==")
    step(res, "pay-invalid", "send_payment", {"amount": 0, "recipient": "alice"},
         "scenario-pay-invalid", "blocked", trigger_sub="severity_floor")

    # ------------------------------------------------------------------ #
    # Over-limit payment is blocked by policy, with a reason naming the limit.
    # ------------------------------------------------------------------ #
    print("\n== Scenario: over-limit payment (pay-limit) ==")
    step(res, "pay-limit", "send_payment", {"amount": 6000, "currency": "USD", "recipient": "alice"},
         "scenario-pay-limit", "blocked", trigger_sub="policy_floor")

    # ------------------------------------------------------------------ #
    # Recon-then-pay fraud pair → escalated as a recognised sequence.
    # ------------------------------------------------------------------ #
    print("\n== Scenario: recon-then-pay fraud pair (fraud-recon) ==")
    step(res, "fraud-recon", "check_balance", {}, "scenario-fraud-recon", {"escalated", "approved"})
    step(res, "fraud-recon", "send_payment", {"amount": 80, "currency": "USD", "recipient": "alice"},
         "scenario-fraud-recon", "escalated", trigger_sub="pattern_matched")

    # ------------------------------------------------------------------ #
    # PII / regulated data access → escalated on data sensitivity.
    # (one benign query first so the decision is judged on sensitivity, not
    #  low confidence)
    # ------------------------------------------------------------------ #
    print("\n== Scenario: PII access (data-pii) ==")
    step(res, "data-pii", "query_database", {"query": "SELECT count(*) FROM products"},
         "scenario-data-pii", {"escalated", "approved"})
    step(res, "data-pii", "query_database", {"query": "SELECT * FROM customers WHERE ssn = '1'"},
         "scenario-data-pii", "escalated", trigger_sub="data_sensitivity_floor")

    # ------------------------------------------------------------------ #
    # Destructive DDL → blocked by policy.
    # ------------------------------------------------------------------ #
    print("\n== Scenario: destructive DDL (data-ddl) ==")
    step(res, "data-ddl", "query_database", {"query": "SELECT count(*) FROM products"},
         "scenario-data-ddl", {"escalated", "approved"})
    step(res, "data-ddl", "query_database", {"query": "DROP TABLE users"},
         "scenario-data-ddl", "blocked", trigger_sub="policy_floor")

    # ------------------------------------------------------------------ #
    # Cumulative buildup: repeated medium-risk actions cross the session
    # severity threshold → escalated for cumulative risk.
    # ------------------------------------------------------------------ #
    print("\n== Scenario: cumulative buildup (accum) ==")
    for i in range(1, 6):
        exp = "escalated" if i >= 5 else {"escalated", "approved"}
        sub = "cumulative_threshold" if i >= 5 else None
        step(res, "accum", "send_payment", {"amount": 80, "currency": "USD", "recipient": "alice"},
             "scenario-accum", exp, trigger_sub=sub)

    # ------------------------------------------------------------------ #
    # Unknown tool — must be blocked by default.
    # ------------------------------------------------------------------ #
    print("\n== Scenario: unknown tool (unknown-tool) ==")
    step(res, "unknown-tool", "deploy_model", {"name": "unverified-llm"},
         "scenario-unknown-tool", "blocked", trigger_sub="unknown_tool")

    # ------------------------------------------------------------------ #
    # Close-out: the audit trail reflects the session.
    # ------------------------------------------------------------------ #
    print("\n== Audit trail ==")
    try:
        entries = get_timeline()
    except Exception as e:
        res.check("timeline retrievable", False, f"(error: {e})")
        entries = []
    res.check("timeline returned decisions", len(entries) > 0, f"(count={len(entries)})")
    with_reason = [e for e in entries if e.get("reason")]
    res.check(
        "every timeline entry carries a grounded reason",
        len(entries) > 0 and len(with_reason) == len(entries),
        f"({len(with_reason)}/{len(entries)} have a reason)",
    )

    print(f"\n== Summary: {res.passed} passed, {res.failed} failed ==")
    return 1 if res.failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)

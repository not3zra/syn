import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import pytest

from engine.audit import AuditStore

PROJECT_ROOT = Path(__file__).resolve().parent.parent

VALID_DECISIONS = {"approved", "escalated", "blocked"}
FACTOR_KEYS = {"severity", "policy", "anomaly", "data_sensitivity", "confidence", "tool_trust"}
SESSION_KEYS = {"session_id", "cumulative_severity", "pattern_matched"}


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server():
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_audit.db"
        env = {
            **os.environ,
            "SYN_AUDIT_DB_PATH": str(db_path),
            "PYTHONPATH": str(PROJECT_ROOT),
        }

        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "gateway.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=PROJECT_ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        for attempt in range(30):
            try:
                r = httpx.get(f"{base_url}/health", timeout=1)
                if r.status_code == 200:
                    break
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            time.sleep(0.5)
        else:
            proc.terminate()
            proc.wait()
            pytest.fail("Gateway failed to start within 15 seconds")

        yield base_url, db_path

        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def assert_valid_decision_response(data, action_type):
    assert data["decision"] in VALID_DECISIONS
    assert isinstance(data["trigger"], str) and len(data["trigger"]) > 0
    assert set(data["factor_scores"].keys()) == FACTOR_KEYS
    assert all(0 <= v <= 100 for v in data["factor_scores"].values())
    assert set(data["session_data"].keys()) == SESSION_KEYS
    assert isinstance(data["regulatory_tier"], str)
    assert isinstance(data["us_regime_flags"], list)
    assert data["action_type"] == action_type
    assert isinstance(data["parameters_abstracted"], dict)
    assert "timestamp" in data
    assert "simulation" in data


def _post(base_url, action_type, parameters, agent_id="test", mode="live"):
    return httpx.post(
        f"{base_url}/intercept",
        json={
            "action_type": action_type,
            "parameters": parameters,
            "agent_id": agent_id,
            "mode": mode,
        },
        timeout=10,
    )


# ===== Risk Engine Scenarios =====

class TestRiskEngineScenarios:

    def test_low_risk_payment_approved(self, server):
        base_url, _ = server
        resp = _post(base_url, "send_payment",
                     {"amount": 50, "currency": "USD", "recipient": "alice"},
                     agent_id="risk-01")
        assert resp.status_code == 200
        data = resp.json()
        assert_valid_decision_response(data, "send_payment")
        assert data["decision"] == "approved"

    def test_high_severity_payment_blocked(self, server):
        base_url, _ = server
        resp = _post(base_url, "send_payment",
                     {"amount": 100000, "currency": "USD", "recipient": "bob"},
                     agent_id="risk-02")
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "blocked"
        assert data["trigger"] == "decision_tree:severity_floor"

    def test_policy_violating_payment_blocked(self, server):
        base_url, _ = server
        resp = _post(base_url, "send_payment",
                     {"amount": 10000, "currency": "USD", "recipient": "external"},
                     agent_id="risk-03")
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "blocked"
        assert "policy" in data["trigger"].lower()

    def test_delete_file_escalated_data_sensitivity_floor(self, server):
        base_url, _ = server
        resp = _post(base_url, "delete_file",
                     {"file_path": "/tmp/customers.xlsx"},
                     agent_id="risk-04")
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "escalated"
        assert data["trigger"] == "decision_tree:data_sensitivity_floor"
        explanation = data.get("explanation", "")
        contributor_phrases = ["severity", "data_sensitivity", "tool_trust", "policy", "anomaly", "confidence"]
        assert any(p in explanation for p in contributor_phrases), (
            f"Explanation '{explanation}' does not name any contributing factor"
        )
        assert data["rollback_plan"] is not None
        assert data["expires_at"] is not None

    def test_delete_file_escalated_weighted_score(self, server):
        base_url, _ = server
        agent_id = "risk-05"
        _post(base_url, "delete_file",
              {"file_path": "/tmp/test.txt"},
              agent_id=agent_id)
        resp = _post(base_url, "delete_file",
                     {"file_path": "/data/prod/foo.xlsx"},
                     agent_id=agent_id)
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "escalated"
        assert "weighted_score" in data["trigger"]
        explanation = data.get("explanation", "")
        contributor_phrases = ["severity", "data_sensitivity", "tool_trust", "policy", "anomaly", "confidence"]
        assert any(p in explanation for p in contributor_phrases), (
            f"Explanation '{explanation}' does not name any contributing factor"
        )

    def test_delete_etc_shadow_blocked(self, server):
        base_url, _ = server
        resp = _post(base_url, "delete_file",
                     {"file_path": "/etc/shadow"},
                     agent_id="risk-06")
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "blocked"
        assert data["trigger"] == "decision_tree:severity_floor"

    def test_safe_select_query_approved(self, server):
        base_url, _ = server
        agent_id = "risk-07"
        for _ in range(5):
            _post(base_url, "query_database",
                  {"query": "SELECT * FROM orders"},
                  agent_id=agent_id)
        resp = _post(base_url, "query_database",
                     {"query": "SELECT id, name FROM orders WHERE id = 1"},
                     agent_id=agent_id)
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "approved"
        assert_valid_decision_response(data, "query_database")

    def test_destructive_query_blocked(self, server):
        base_url, _ = server
        resp = _post(base_url, "query_database",
                     {"query": "DROP TABLE users"},
                     agent_id="risk-08")
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "blocked"
        assert "policy" in data["trigger"].lower()

    def test_check_balance_approved(self, server):
        base_url, _ = server
        agent_id = "risk-09"
        for _ in range(2):
            _post(base_url, "check_balance",
                  {"account_id": "acc_123"},
                  agent_id=agent_id)
        resp = _post(base_url, "check_balance",
                     {"account_id": "acc_123"},
                     agent_id=agent_id)
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "approved"

    def test_session_pattern_match_escalated(self, server):
        base_url, _ = server
        agent_id = "risk-10"
        resp = _post(base_url, "check_balance",
                     {"account_id": "acc_123"},
                     agent_id=agent_id)
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "approved"

        resp = _post(base_url, "send_payment",
                     {"amount": 50, "currency": "USD", "recipient": "alice"},
                     agent_id=agent_id)
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "escalated"
        assert data["trigger"] == "session:pattern_matched:check_balance->send_payment"
        assert data["session_data"]["pattern_matched"] is True
        explanation = data.get("explanation", "")
        assert explanation and len(explanation) > 20, (
            f"Explanation too short or missing: '{explanation}'"
        )

    def test_session_cumulative_threshold_escalated(self, server):
        base_url, _ = server
        agent_id = "risk-11"
        for _ in range(5):
            resp = _post(base_url, "check_balance",
                         {"account_id": "acc_123"},
                         agent_id=agent_id)
            assert resp.status_code == 200
        resp = _post(base_url, "check_balance",
                     {"account_id": "acc_123"},
                     agent_id=agent_id)
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "escalated", (
            f"Expected escalated after 5 warmup calls, got {data['decision']}"
        )
        assert data["trigger"] == "session:cumulative_threshold"
        assert data["session_data"]["cumulative_severity"] >= 70.0
        explanation = data.get("explanation", "")
        assert explanation and len(explanation) > 20, (
            f"Explanation too short or missing: '{explanation}'"
        )

    def test_session_data_included_in_result(self, server):
        base_url, _ = server
        agent_id = "risk-12"
        _post(base_url, "check_balance",
              {"account_id": "acc_123"},
              agent_id=agent_id)
        resp = _post(base_url, "check_balance",
                     {"account_id": "acc_123"},
                     agent_id=agent_id)
        assert resp.status_code == 200
        data = resp.json()
        sd = data["session_data"]
        assert isinstance(sd["session_id"], str) and len(sd["session_id"]) > 0
        assert isinstance(sd["cumulative_severity"], (int, float))
        assert isinstance(sd["pattern_matched"], bool)


# ===== Gateway Endpoint Tests =====

class TestGatewayEndpoints:

    def test_tools_endpoint(self, server):
        base_url, _ = server
        resp = httpx.get(f"{base_url}/tools", timeout=10)
        assert resp.status_code == 200
        tools = resp.json()
        assert len(tools) == 3
        names = [t["name"] for t in tools]
        assert "send_payment" in names
        assert "delete_file" in names
        assert "query_database" in names

    def test_health_endpoint(self, server):
        base_url, _ = server
        resp = httpx.get(f"{base_url}/health", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "llm" in data

    def test_unknown_tool_blocked(self, server):
        base_url, _ = server
        resp = _post(base_url, "unknown_tool", {}, agent_id="gateway-15")
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "blocked"
        assert data["trigger"] == "gateway:unknown_tool"

    def test_simulation_mode_returns_simulation_flag(self, server):
        base_url, _ = server
        resp = _post(base_url, "send_payment",
                     {"amount": 50, "recipient": "alice"},
                     agent_id="gateway-16", mode="simulation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["simulation"] is True
        assert data["decision"] == "approved"
        assert data["execution"] is None


# ===== Named Beat 4 Sequence =====

class TestBeat4Sequence:

    AGENT_ID = "beat4"

    def test_beat4_sequence(self, server):
        base_url, db_path = server

        for i in range(3):
            resp = _post(base_url, "check_balance",
                         {"account_id": "acc_123"},
                         agent_id=self.AGENT_ID)
            assert resp.status_code == 200
            data = resp.json()
            assert data["decision"] == "approved", (
                f"Beat 4 step {i+1}: expected approved, got {data['decision']}"
            )
            assert_valid_decision_response(data, "check_balance")

        resp = _post(base_url, "send_payment",
                     {"amount": 50, "currency": "USD", "recipient": "alice"},
                     agent_id=self.AGENT_ID)
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "escalated", (
            f"Beat 4 final step: expected escalated, got {data['decision']}"
        )
        assert data["trigger"] == "session:pattern_matched:check_balance->send_payment", (
            f"Beat 4 trigger: expected session:pattern_matched:check_balance->send_payment, got {data['trigger']}"
        )
        assert data["session_data"]["pattern_matched"] is True
        expected_cumulative = 3 * 15
        assert data["session_data"]["cumulative_severity"] == expected_cumulative, (
            f"Beat 4 cumulative_severity: expected {expected_cumulative}, got {data['session_data']['cumulative_severity']}"
        )
        explanation = data.get("explanation", "")
        assert explanation and len(explanation) > 20, (
            f"Beat 4 explanation too short or missing: '{explanation}'"
        )
        assert data["rollback_plan"] is not None
        assert data["expires_at"] is not None


# ===== E2E Smoke Tests (HTTP + SQLite) =====

class TestE2EApprovePath:
    AGENT_ID = "e2e-live-approve"

    def test_approve_path_http_response(self, server):
        base_url, _ = server
        for _ in range(2):
            resp = _post(base_url, "send_payment",
                         {"amount": 50, "recipient": "alice"},
                         agent_id=self.AGENT_ID)
            assert resp.status_code == 200
        resp = _post(base_url, "send_payment",
                     {"amount": 50, "recipient": "alice"},
                     agent_id=self.AGENT_ID)
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "approved"

    def test_approve_path_sqlite_side_effect(self, server):
        _, db_path = server
        store = AuditStore(str(db_path))
        try:
            entries = store.list_all(outcome="approved")
            approved = [e for e in entries if e["action_type"] == "send_payment"]
            assert len(approved) >= 1
            assert approved[-1]["decision"] == "approved"
        finally:
            store.close()


class TestE2EEscalatePath:
    AGENT_ID = "e2e-live-escalate"

    def test_escalate_path_http_response(self, server):
        base_url, _ = server
        resp = _post(base_url, "delete_file",
                     {"file_path": "/tmp/customers.xlsx"},
                     agent_id=self.AGENT_ID)
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "escalated"

    def test_escalate_path_sqlite_side_effect(self, server):
        _, db_path = server
        store = AuditStore(str(db_path))
        try:
            entries = store.list_all(outcome="escalated")
            escalated = [e for e in entries if e["action_type"] == "delete_file"]
            assert len(escalated) >= 1
        finally:
            store.close()


class TestE2EBlockPath:
    AGENT_ID = "e2e-live-block"

    def test_block_path_http_response(self, server):
        base_url, _ = server
        resp = _post(base_url, "send_payment",
                     {"amount": 100000, "recipient": "bob"},
                     agent_id=self.AGENT_ID)
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "blocked"

    def test_block_path_sqlite_side_effect(self, server):
        _, db_path = server
        store = AuditStore(str(db_path))
        try:
            entries = store.list_all(outcome="blocked")
            blocked = [e for e in entries if e["action_type"] == "send_payment"]
            assert len(blocked) >= 1
        finally:
            store.close()

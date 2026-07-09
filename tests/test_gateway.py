from fastapi.testclient import TestClient
from gateway.main import app, REGISTERED_TOOLS
from engine.execution import execute_tool

client = TestClient(app)

VALID_DECISIONS = {"approved", "escalated", "blocked"}
FACTOR_KEYS = {"severity", "policy", "anomaly", "data_sensitivity", "confidence", "tool_trust"}
SESSION_KEYS = {"session_id", "cumulative_severity", "pattern_matched"}


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


def test_lists_registered_tools():
    response = client.get("/tools")
    assert response.status_code == 200
    tools = response.json()
    assert len(tools) == 3
    names = [t["name"] for t in tools]
    assert "send_payment" in names
    assert "delete_file" in names
    assert "query_database" in names


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_headers_on_response():
    response = client.get("/health", headers={"origin": "http://example.com"})
    assert response.status_code == 200
    origin = response.headers.get("access-control-allow-origin")
    assert origin in ("*", "http://example.com")


def test_cors_preflight_succeeds():
    response = client.options(
        "/intercept",
        headers={
            "origin": "http://localhost:3000",
            "access-control-request-method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") in ("*", "http://localhost:3000")


def test_body_size_limit_exceeded():
    large_payload = {"action_type": "x" * (1024 * 1024 + 1)}
    response = client.post("/intercept", json=large_payload)
    assert response.status_code == 413


def test_body_size_limit_normal_succeeds():
    payload = {"action_type": "send_payment", "parameters": {"amount": 100}}
    response = client.post("/intercept", json=payload)
    assert response.status_code == 200


def test_intercept_send_payment():
    payload = {
        "action_type": "send_payment",
        "parameters": {"amount": 100, "recipient": "alice"},
    }
    response = client.post("/intercept", json=payload)
    assert response.status_code == 200
    assert_valid_decision_response(response.json(), "send_payment")


def test_intercept_delete_file():
    payload = {
        "action_type": "delete_file",
        "parameters": {"file_path": "/data/records.csv"},
    }
    response = client.post("/intercept", json=payload)
    assert response.status_code == 200
    assert_valid_decision_response(response.json(), "delete_file")


def test_intercept_query_database():
    payload = {
        "action_type": "query_database",
        "parameters": {"query": "SELECT * FROM users"},
    }
    response = client.post("/intercept", json=payload)
    assert response.status_code == 200
    assert_valid_decision_response(response.json(), "query_database")


def test_unknown_tool_is_blocked():
    payload = {
        "action_type": "unknown_tool",
        "parameters": {},
    }
    response = client.post("/intercept", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "blocked"
    assert data["trigger"] == "gateway:unknown_tool"


def test_bootstrap_introspect_with_manual_schemas(monkeypatch):
    from engine.llm import MockLLMClient
    from gateway import main as gateway_main
    monkeypatch.setattr(gateway_main, "LLM_CLIENT", MockLLMClient())
    payload = {
        "manual_schemas": [
            {"name": "send_payment", "parameters": {"amount": {"type": "number"}}},
            {"name": "delete_file", "parameters": {"file_path": {"type": "string"}}},
        ]
    }
    response = client.post("/bootstrap/introspect", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "rules" in data
    assert "yaml" in data
    assert "valid" in data
    assert data["valid"] is True
    assert len(data["rules"]) >= 2
    assert "send_payment" in data["yaml"]
    assert "delete_file" in data["yaml"]


def test_bootstrap_introspect_rules_have_structure(monkeypatch):
    from engine.llm import MockLLMClient
    from gateway import main as gateway_main
    monkeypatch.setattr(gateway_main, "LLM_CLIENT", MockLLMClient())
    payload = {
        "manual_schemas": [
            {"name": "send_payment", "parameters": {"amount": {"type": "number"}}},
        ]
    }
    response = client.post("/bootstrap/introspect", json=payload)
    data = response.json()
    rule = data["rules"][0]
    assert "tool_name" in rule
    assert "severity_rules" in rule
    assert "policy_rules" in rule
    assert "data_sensitivity_rules" in rule
    assert "tool_trust_tier" in rule
    assert "anomaly_lookback" in rule
    assert "reasoning" in rule


def test_bootstrap_approve_valid_yaml():
    yaml_content = """tools:
  send_payment:
    severity_rules:
      - max_amount: 1000
        score: 20
    policy_rules: []
    data_sensitivity_rules: []
    tool_trust_tier: official
    anomaly_lookback: 20"""
    response = client.post("/bootstrap/approve", json={"yaml_content": yaml_content})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_bootstrap_approve_invalid_yaml():
    yaml_content = """tools:
  send_payment:
    tool_trust_tier: invalid_tier"""
    response = client.post("/bootstrap/approve", json={"yaml_content": yaml_content})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert len(data["errors"]) > 0


_YAML_CONTENT = """tools:
  test_tool:
    severity_rules:
      - max_amount: 100
        score: 10
    policy_rules: []
    data_sensitivity_rules: []
    tool_trust_tier: official
    anomaly_lookback: 10"""


def test_bootstrap_approve_path_traversal_rejected():
    """Path traversal via target_path should return 400."""
    response = client.post("/bootstrap/approve", json={
        "yaml_content": _YAML_CONTENT,
        "target_path": "../../etc/passwd",
    })
    assert response.status_code == 400


def test_bootstrap_approve_default_path():
    """Null target_path should write to default location."""
    response = client.post("/bootstrap/approve", json={
        "yaml_content": _YAML_CONTENT,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "policy_config.bootstrap.yaml" in data["path"]


def test_intercept_simulation_returns_valid():
    payload = {
        "action_type": "send_payment",
        "parameters": {"amount": 100, "recipient": "alice"},
        "mode": "simulation",
    }
    response = client.post("/intercept", json=payload)
    assert response.status_code == 200
    assert_valid_decision_response(response.json(), "send_payment")


def test_intercept_simulation_sets_flag():
    payload = {
        "action_type": "send_payment",
        "parameters": {"amount": 100, "recipient": "alice"},
        "mode": "simulation",
    }
    response = client.post("/intercept", json=payload)
    assert response.json()["simulation"] is True


def test_intercept_live_default_no_simulation():
    payload = {
        "action_type": "send_payment",
        "parameters": {"amount": 100, "recipient": "alice"},
    }
    response = client.post("/intercept", json=payload)
    assert response.json()["simulation"] is False


def test_intercept_simulation_unknown_tool():
    payload = {
        "action_type": "unknown_tool",
        "parameters": {},
        "mode": "simulation",
    }
    response = client.post("/intercept", json=payload)
    data = response.json()
    assert data["simulation"] is True
    assert data["decision"] == "blocked"
    assert data["trigger"] == "gateway:unknown_tool"


def test_slack_webhook_url_reads_from_env(monkeypatch):
    monkeypatch.setenv("SYN_SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    import importlib
    from gateway import main as gateway_main
    importlib.reload(gateway_main)
    assert gateway_main.SLACK_WEBHOOK_URL == "https://hooks.slack.com/test"


def test_slack_webhook_url_falls_back_to_none(monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda **kwargs: None)
    monkeypatch.delenv("SYN_SLACK_WEBHOOK_URL", raising=False)
    import importlib
    from gateway import main as gateway_main
    importlib.reload(gateway_main)
    assert gateway_main.SLACK_WEBHOOK_URL is None


def test_execute_tool_returns_success():
    result = execute_tool("send_payment", {"amount": 50, "recipient": "alice"})
    assert result == {
        "action": "send_payment",
        "params": {"amount": 50, "recipient": "alice"},
        "status": "success",
    }


def test_execute_tool_logs_on_call(caplog):
    import logging
    caplog.set_level(logging.INFO)
    execute_tool("delete_file", {"file_path": "/tmp/test.txt"})
    assert any("[exec] delete_file" in record.getMessage() for record in caplog.records)


def test_intercept_approved_includes_execution(monkeypatch):
    import importlib
    import tempfile
    from pathlib import Path
    from fastapi.testclient import TestClient

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        monkeypatch.setenv("SYN_AUDIT_DB_PATH", str(db_path))
        from gateway import main as gateway_main
        importlib.reload(gateway_main)
        test_client = TestClient(gateway_main.app)

        payload = {
            "action_type": "send_payment",
            "parameters": {"amount": 50, "recipient": "alice"},
        }
        resp = test_client.post("/intercept", json=payload)
        data = resp.json()
        assert data["decision"] == "approved"
        assert data["execution"] == {
            "action": "send_payment",
            "params": {"amount": 50, "recipient": "alice"},
            "status": "success",
        }


def test_intercept_escalated_no_execution(monkeypatch):
    import importlib
    import tempfile
    from pathlib import Path
    from fastapi.testclient import TestClient

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        monkeypatch.setenv("SYN_AUDIT_DB_PATH", str(db_path))
        from gateway import main as gateway_main
        importlib.reload(gateway_main)
        test_client = TestClient(gateway_main.app)

        payload = {
            "action_type": "delete_file",
            "parameters": {"file_path": "/tmp/customers.xlsx"},
        }
        resp = test_client.post("/intercept", json=payload)
        data = resp.json()
        assert data["decision"] == "escalated"
        assert data["execution"] is None


def test_escalation_includes_rollback_plan_and_expires_at(monkeypatch):
    import importlib
    import tempfile
    from pathlib import Path
    from fastapi.testclient import TestClient

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        monkeypatch.setenv("SYN_AUDIT_DB_PATH", str(db_path))
        from gateway import main as gateway_main
        importlib.reload(gateway_main)
        test_client = TestClient(gateway_main.app)

        payload = {
            "action_type": "delete_file",
            "parameters": {"file_path": "/tmp/customers.xlsx"},
        }
        resp = test_client.post("/intercept", json=payload)
        data = resp.json()
        assert data["decision"] == "escalated"
        assert isinstance(data.get("rollback_plan"), str) and len(data["rollback_plan"]) > 0
        assert isinstance(data.get("expires_at"), str) and len(data["expires_at"]) > 0


def test_resolve_approved_calls_mark_resolved_and_execute_tool(monkeypatch):
    import importlib
    import tempfile
    from pathlib import Path
    from fastapi.testclient import TestClient

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        monkeypatch.setenv("SYN_AUDIT_DB_PATH", str(db_path))
        from gateway import main as gateway_main
        importlib.reload(gateway_main)
        test_client = TestClient(gateway_main.app)

        payload = {
            "action_type": "delete_file",
            "parameters": {"file_path": "/tmp/customers.xlsx"},
        }
        test_client.post("/intercept", json=payload)

        resp = test_client.get("/timeline?outcome=escalated")
        entries = resp.json()
        assert len(entries) > 0
        entry_id = entries[-1]["id"]

        resolve_resp = test_client.post(f"/resolve/{entry_id}", json={"outcome": "approved"})
        resolve_data = resolve_resp.json()
        assert resolve_data["success"] is True
        assert resolve_data["execution"]["status"] == "success"


def test_resolve_denied_marks_resolved_only(monkeypatch):
    import importlib
    import tempfile
    from pathlib import Path
    from fastapi.testclient import TestClient

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        monkeypatch.setenv("SYN_AUDIT_DB_PATH", str(db_path))
        from gateway import main as gateway_main
        importlib.reload(gateway_main)
        test_client = TestClient(gateway_main.app)

        payload = {
            "action_type": "delete_file",
            "parameters": {"file_path": "/tmp/customers.xlsx"},
        }
        test_client.post("/intercept", json=payload)

        resp = test_client.get("/timeline?outcome=escalated")
        entries = resp.json()
        assert len(entries) > 0
        entry_id = entries[-1]["id"]

        resolve_resp = test_client.post(f"/resolve/{entry_id}", json={"outcome": "denied"})
        resolve_data = resolve_resp.json()
        assert resolve_data["success"] is True
        assert resolve_data["execution"] is None


def test_intercept_blocked_no_execution(monkeypatch):
    import importlib
    import tempfile
    from pathlib import Path
    from fastapi.testclient import TestClient

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        monkeypatch.setenv("SYN_AUDIT_DB_PATH", str(db_path))
        from gateway import main as gateway_main
        importlib.reload(gateway_main)
        test_client = TestClient(gateway_main.app)

        payload = {
            "action_type": "send_payment",
            "parameters": {"amount": 100000, "recipient": "bob"},
        }
        resp = test_client.post("/intercept", json=payload)
        data = resp.json()
        assert data["decision"] == "blocked"
        assert data["execution"] is None


def test_intercept_simulation_no_execution(monkeypatch):
    import importlib
    import tempfile
    from pathlib import Path
    from fastapi.testclient import TestClient

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        monkeypatch.setenv("SYN_AUDIT_DB_PATH", str(db_path))
        from gateway import main as gateway_main
        importlib.reload(gateway_main)
        test_client = TestClient(gateway_main.app)

        payload = {
            "action_type": "send_payment",
            "parameters": {"amount": 50, "recipient": "alice"},
            "mode": "simulation",
        }
        resp = test_client.post("/intercept", json=payload)
        data = resp.json()
        assert data["decision"] == "approved"
        assert data["execution"] is None


class TestSessionLifecycle:
    def _make_client(self, tmpdir, monkeypatch):
        import importlib
        from pathlib import Path
        from fastapi.testclient import TestClient
        from engine.llm import MockLLMClient
        db_path = Path(tmpdir) / "test.db"
        monkeypatch.setenv("SYN_AUDIT_DB_PATH", str(db_path))
        from gateway import main as gateway_main
        importlib.reload(gateway_main)
        monkeypatch.setattr(gateway_main, "LLM_CLIENT", MockLLMClient())
        return TestClient(gateway_main.app)

    def test_start_session_returns_uuid(self, tmpdir, monkeypatch):
        c = self._make_client(tmpdir, monkeypatch)
        payload = {
            "action_type": "send_payment",
            "parameters": {"amount": 50, "recipient": "alice"},
            "session_intent": "start",
        }
        resp = c.post("/intercept", json=payload)
        data = resp.json()
        assert len(data["session_data"]["session_id"]) > 20

    def test_continue_with_valid_session(self, tmpdir, monkeypatch):
        c = self._make_client(tmpdir, monkeypatch)
        start_resp = c.post("/intercept", json={
            "action_type": "send_payment",
            "parameters": {"amount": 50, "recipient": "alice"},
            "session_intent": "start",
        })
        session_id = start_resp.json()["session_data"]["session_id"]

        continue_resp = c.post("/intercept", json={
            "action_type": "check_balance",
            "parameters": {},
            "session_intent": "continue",
            "session_id": session_id,
        })
        data = continue_resp.json()
        assert data["session_data"]["session_id"] == session_id

    def test_unknown_continue_falls_back_to_timebucket(self, tmpdir, monkeypatch):
        c = self._make_client(tmpdir, monkeypatch)
        resp = c.post("/intercept", json={
            "action_type": "send_payment",
            "parameters": {"amount": 50, "recipient": "alice"},
            "session_intent": "continue",
            "session_id": "nonexistent-uuid",
        })
        data = resp.json()
        assert "session:fallback_timebucket" in data["trigger"]

    def test_end_session_closes_it(self, tmpdir, monkeypatch):
        c = self._make_client(tmpdir, monkeypatch)
        start_resp = c.post("/intercept", json={
            "action_type": "send_payment",
            "parameters": {"amount": 50, "recipient": "alice"},
            "session_intent": "start",
        })
        session_id = start_resp.json()["session_data"]["session_id"]

        c.post("/intercept", json={
            "action_type": "check_balance",
            "parameters": {},
            "session_intent": "end",
            "session_id": session_id,
        })

        continue_resp = c.post("/intercept", json={
            "action_type": "send_payment",
            "parameters": {"amount": 50, "recipient": "alice"},
            "session_intent": "continue",
            "session_id": session_id,
        })
        assert "session:fallback_timebucket" in continue_resp.json()["trigger"]

    def test_concurrent_sessions_allowed(self, tmpdir, monkeypatch):
        c = self._make_client(tmpdir, monkeypatch)
        sid1 = c.post("/intercept", json={
            "action_type": "send_payment",
            "parameters": {"amount": 50, "recipient": "alice"},
            "session_intent": "start",
        }).json()["session_data"]["session_id"]
        sid2 = c.post("/intercept", json={
            "action_type": "check_balance",
            "parameters": {},
            "session_intent": "start",
        }).json()["session_data"]["session_id"]
        assert sid1 != sid2

    def test_no_intent_uses_timebucket(self, tmpdir, monkeypatch):
        c = self._make_client(tmpdir, monkeypatch)
        resp = c.post("/intercept", json={
            "action_type": "send_payment",
            "parameters": {"amount": 50, "recipient": "alice"},
        })
        sid = resp.json()["session_data"]["session_id"]
        assert ":" in sid  # time-bucket format agent:bucket


class TestBootstrapPending:
    def _make_client(self, tmpdir, monkeypatch):
        import importlib
        from pathlib import Path
        from fastapi.testclient import TestClient
        db_path = Path(tmpdir) / "test.db"
        monkeypatch.setenv("SYN_AUDIT_DB_PATH", str(db_path))
        from gateway import main as gateway_main
        importlib.reload(gateway_main)
        return TestClient(gateway_main.app), gateway_main.AUDIT_STORE

    def test_pending_initially_empty(self, tmpdir, monkeypatch):
        c, _ = self._make_client(tmpdir, monkeypatch)
        resp = c.get("/bootstrap/pending")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_approve_single_tool(self, tmpdir, monkeypatch):
        c, store = self._make_client(tmpdir, monkeypatch)
        store.create_pending_rule("custom_tool", "tools:\n  custom_tool:\n    tool_trust_tier: unknown\n    anomaly_lookback: 10\n    severity_rules: []\n    policy_rules: []\n    data_sensitivity_rules: []\n    reasoning: \"\"", "[]")
        approve_resp = c.post("/bootstrap/approve/custom_tool", json={"reviewed_by": "test-admin"})
        assert approve_resp.status_code == 200
        data = approve_resp.json()
        assert data["success"] is True
        assert data["tool_name"] == "custom_tool"

        pending_resp = c.get("/bootstrap/pending")
        assert pending_resp.json() == []

    def test_approve_nonexistent_tool(self, tmpdir, monkeypatch):
        c, _ = self._make_client(tmpdir, monkeypatch)
        resp = c.post("/bootstrap/approve/nonexistent", json={"reviewed_by": "test-admin"})
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    def test_reject_single_tool(self, tmpdir, monkeypatch):
        c, store = self._make_client(tmpdir, monkeypatch)
        store.create_pending_rule("reject_me", "yaml_content", "[]")
        reject_resp = c.post("/bootstrap/reject/reject_me", json={"reviewed_by": "test-admin"})
        assert reject_resp.status_code == 200
        data = reject_resp.json()
        assert data["success"] is True
        assert data["tool_name"] == "reject_me"

        pending_resp = c.get("/bootstrap/pending")
        assert pending_resp.json() == []

    def test_approve_all(self, tmpdir, monkeypatch):
        c, store = self._make_client(tmpdir, monkeypatch)
        store.create_pending_rule("tool_a", "tools:\n  tool_a:\n    tool_trust_tier: unknown\n    anomaly_lookback: 10\n    severity_rules: []\n    policy_rules: []\n    data_sensitivity_rules: []\n    reasoning: \"\"", "[]")
        store.create_pending_rule("tool_b", "tools:\n  tool_b:\n    tool_trust_tier: unknown\n    anomaly_lookback: 10\n    severity_rules: []\n    policy_rules: []\n    data_sensitivity_rules: []\n    reasoning: \"\"", "[]")
        approve_resp = c.post("/bootstrap/approve-all", json={"reviewed_by": "test-admin"})
        assert approve_resp.status_code == 200
        data = approve_resp.json()
        assert data["success"] is True
        assert data["approved_count"] == 2

        pending_resp = c.get("/bootstrap/pending")
        assert pending_resp.json() == []

    def test_retry_nonexistent_rule(self, tmpdir, monkeypatch):
        c, _ = self._make_client(tmpdir, monkeypatch)
        resp = c.post("/bootstrap/retry/999", json={"tool_name": "x", "parameters": {}})
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    def test_reject_nonexistent_tool(self, tmpdir, monkeypatch):
        c, _ = self._make_client(tmpdir, monkeypatch)
        resp = c.post("/bootstrap/reject/nonexistent", json={"reviewed_by": "test-admin"})
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    def test_approve_all_empty(self, tmpdir, monkeypatch):
        c, _ = self._make_client(tmpdir, monkeypatch)
        resp = c.post("/bootstrap/approve-all", json={"reviewed_by": "test-admin"})
        assert resp.status_code == 200
        assert resp.json()["success"] is False

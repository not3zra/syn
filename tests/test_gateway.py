from fastapi.testclient import TestClient
from gateway.main import app, REGISTERED_TOOLS

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


def test_bootstrap_introspect_with_manual_schemas():
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


def test_bootstrap_introspect_rules_have_structure():
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


def test_bootstrap_approve_valid_yaml(tmp_path):
    yaml_content = """tools:
  send_payment:
    severity_rules:
      - max_amount: 1000
        score: 20
    policy_rules: []
    data_sensitivity_rules: []
    tool_trust_tier: official
    anomaly_lookback: 20"""
    target = str(tmp_path / "test_policy.yaml")
    response = client.post("/bootstrap/approve", json={"yaml_content": yaml_content, "target_path": target})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["path"] == target


def test_bootstrap_approve_invalid_yaml():
    yaml_content = """tools:
  send_payment:
    tool_trust_tier: invalid_tier"""
    response = client.post("/bootstrap/approve", json={"yaml_content": yaml_content})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert len(data["errors"]) > 0


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

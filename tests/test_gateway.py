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

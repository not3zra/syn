from fastapi.testclient import TestClient
from gateway.main import app, REGISTERED_TOOLS

client = TestClient(app)


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


DECISION_SHAPE = {
    "decision": "approved",
    "trigger": "hardcoded_fake",
    "factor_scores": {
        "severity": 0,
        "policy": 0,
        "anomaly": 0,
        "data_sensitivity": 0,
        "confidence": 100,
        "tool_trust": 100,
    },
    "session_data": {
        "session_id": None,
        "cumulative_severity": 0,
        "pattern_matched": False,
    },
    "regulatory_tier": "minimal_risk",
    "us_regime_flags": [],
}


def assert_valid_decision(data, action_type):
    assert data["decision"] == DECISION_SHAPE["decision"]
    assert data["trigger"] == DECISION_SHAPE["trigger"]
    assert data["factor_scores"] == DECISION_SHAPE["factor_scores"]
    assert data["session_data"] == DECISION_SHAPE["session_data"]
    assert data["regulatory_tier"] == DECISION_SHAPE["regulatory_tier"]
    assert data["us_regime_flags"] == DECISION_SHAPE["us_regime_flags"]
    assert data["action_type"] == action_type
    assert "parameters_abstracted" in data
    assert "timestamp" in data


def test_intercept_send_payment():
    payload = {
        "action_type": "send_payment",
        "parameters": {"amount": 100, "recipient": "alice"},
    }
    response = client.post("/intercept", json=payload)
    assert response.status_code == 200
    assert_valid_decision(response.json(), "send_payment")


def test_intercept_delete_file():
    payload = {
        "action_type": "delete_file",
        "parameters": {"file_path": "/data/records.csv"},
    }
    response = client.post("/intercept", json=payload)
    assert response.status_code == 200
    assert_valid_decision(response.json(), "delete_file")


def test_intercept_query_database():
    payload = {
        "action_type": "query_database",
        "parameters": {"query": "SELECT * FROM users"},
    }
    response = client.post("/intercept", json=payload)
    assert response.status_code == 200
    assert_valid_decision(response.json(), "query_database")




import pytest
from fastapi.testclient import TestClient

from gateway.main import app

DEMO_TOKEN = "test-demo-token"

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_llm(monkeypatch):
    from engine.llm import MockLLMClient
    import gateway.main as gm

    monkeypatch.setattr(gm, "LLM_CLIENT", MockLLMClient())


@pytest.fixture
def temp_state(tmp_path, monkeypatch):
    """Isolate the gateway's audit store + bootstrap config to a temp dir.

    Lets reset tests assert real DB / file state without touching the dev db.
    """
    from engine.audit import AuditStore
    import gateway.main as gm

    db_path = tmp_path / "audit.db"
    bootstrap_path = tmp_path / "policy_config.bootstrap.yaml"
    bootstrap_path.write_text("tools: {}\n")
    store = AuditStore(str(db_path))

    monkeypatch.setattr(gm, "AUDIT_STORE", store)
    monkeypatch.setattr(gm, "bootstrap_config_path", bootstrap_path)
    yield store, bootstrap_path
    store.close()


@pytest.fixture
def demo_token_set(monkeypatch):
    monkeypatch.setenv("DEMO_TOKEN", DEMO_TOKEN)
    yield DEMO_TOKEN
    monkeypatch.delenv("DEMO_TOKEN", raising=False)


def _seed_tool(bootstrap_path, tool_name):
    bootstrap_path.write_text(
        f"tools:\n  {tool_name}:\n    tool_trust_tier: verified\n"
    )


# --- Token gate (tracer bullet) ---

def test_admin_reset_401_without_token(demo_token_set, temp_state):
    resp = client.post("/admin/reset")
    assert resp.status_code == 401


def test_admin_reset_200_with_correct_token(demo_token_set, temp_state):
    resp = client.post("/admin/reset", headers={"X-Demo-Token": DEMO_TOKEN})
    assert resp.status_code == 200
    assert resp.json().get("success") is True


# --- Timeline emptied ---

def test_admin_reset_clears_timeline(demo_token_set, temp_state):
    store, _ = temp_state
    store.append(
        {
            "decision": "approved",
            "action_type": "send_payment",
            "timestamp": "2026-01-01T00:00:00Z",
        }
    )
    assert client.get("/timeline").json()

    resp = client.post("/admin/reset", headers={"X-Demo-Token": DEMO_TOKEN})
    assert resp.status_code == 200
    assert client.get("/timeline").json() == []


# --- Bootstrap config restored to baseline + reload ---

def test_admin_reset_restores_bootstrap_baseline(demo_token_set, temp_state):
    store, bootstrap_path = temp_state
    _seed_tool(bootstrap_path, "mystery_tool")

    # Pre-reset: tool is known (not blocked as unknown).
    pre = client.post(
        "/intercept",
        headers={"X-Demo-Token": DEMO_TOKEN},
        json={"action_type": "mystery_tool", "parameters": {}, "agent_id": "reset-agent"},
    )
    assert "unknown_tool" not in pre.json().get("trigger", "")

    resp = client.post("/admin/reset", headers={"X-Demo-Token": DEMO_TOKEN})
    assert resp.status_code == 200

    # Post-reset: merged tools reload to baseline, tool is unknown again.
    post = client.post(
        "/intercept",
        headers={"X-Demo-Token": DEMO_TOKEN},
        json={"action_type": "mystery_tool", "parameters": {}, "agent_id": "reset-agent"},
    )
    assert post.json().get("decision") == "blocked"
    assert "unknown_tool" in post.json().get("trigger", "")

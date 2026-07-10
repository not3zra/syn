import pytest
from fastapi.testclient import TestClient

from gateway.main import app, assert_demo_token_configured_for_production

DEMO_TOKEN = "test-demo-token"

client = TestClient(app)

# (method, path, json body) for every route gated by the demo-token tripwire.
GATED_ROUTES = [
    ("POST", "/intercept", {"action_type": "send_payment", "parameters": {"amount": 5}}),
    ("POST", "/resolve/1", {"outcome": "approved"}),
    ("POST", "/bootstrap/introspect", {"manual_schemas": [{"name": "x", "parameters": {}}]}),
    ("POST", "/bootstrap/approve", {"yaml_content": "tools: {}"}),
    ("POST", "/bootstrap/approve-all", {}),
    ("POST", "/bootstrap/retry/1", {"tool_name": "x"}),
]

OPEN_ROUTES = ["/health", "/tools", "/timeline", "/bootstrap/pending"]


@pytest.fixture(autouse=True)
def mock_llm(monkeypatch):
    """Avoid real LLM network calls during accept-path tests."""
    from engine.llm import MockLLMClient
    import gateway.main as gm

    monkeypatch.setattr(gm, "LLM_CLIENT", MockLLMClient())


@pytest.fixture
def demo_token_set(monkeypatch):
    monkeypatch.setenv("DEMO_TOKEN", DEMO_TOKEN)
    yield
    monkeypatch.delenv("DEMO_TOKEN", raising=False)


@pytest.fixture
def demo_token_unset(monkeypatch):
    monkeypatch.delenv("DEMO_TOKEN", raising=False)
    yield


def test_open_routes_200_without_token_when_token_set(demo_token_set):
    for path in OPEN_ROUTES:
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} -> {resp.status_code}"


def test_gated_routes_401_without_token(demo_token_set):
    for method, path, body in GATED_ROUTES:
        resp = client.request(method, path, json=body)
        assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}: {resp.text}"


def test_gated_routes_401_with_wrong_token(demo_token_set):
    headers = {"X-Demo-Token": "wrong-token"}
    for method, path, body in GATED_ROUTES:
        resp = client.request(method, path, json=body, headers=headers)
        assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}: {resp.text}"


def test_gated_routes_open_with_correct_token(demo_token_set):
    headers = {"X-Demo-Token": DEMO_TOKEN}
    # Routes with no dangerous side effects prove the gate opens.
    probes = [
        ("POST", "/intercept", {"action_type": "send_payment", "parameters": {"amount": 5}}),
        ("POST", "/bootstrap/introspect", {"manual_schemas": [{"name": "x", "parameters": {}}]}),
    ]
    for method, path, body in probes:
        resp = client.request(method, path, json=body, headers=headers)
        assert resp.status_code != 401, f"{method} {path} -> {resp.status_code}: {resp.text}"


def test_gated_routes_noop_when_token_unset(demo_token_unset):
    for method, path, body in GATED_ROUTES:
        resp = client.request(method, path, json=body)
        assert resp.status_code != 401, f"{method} {path} -> {resp.status_code}: {resp.text}"


def test_prod_refuses_to_start_without_token(monkeypatch):
    monkeypatch.setenv("FLY_APP_NAME", "syn")
    monkeypatch.delenv("DEMO_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        assert_demo_token_configured_for_production()


def test_prod_ok_with_token(monkeypatch):
    monkeypatch.setenv("FLY_APP_NAME", "syn")
    monkeypatch.setenv("DEMO_TOKEN", DEMO_TOKEN)
    assert_demo_token_configured_for_production()


def test_local_no_fly_no_token_ok(monkeypatch):
    monkeypatch.delenv("FLY_APP_NAME", raising=False)
    monkeypatch.delenv("DEMO_TOKEN", raising=False)
    assert_demo_token_configured_for_production()

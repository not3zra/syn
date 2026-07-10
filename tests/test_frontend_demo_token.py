"""Frontend demo-token wiring (#36).

The demo token must never be visible to a normal visitor: it is read from
``VITE_DEMO_TOKEN`` at build time and attached as ``X-Demo-Token`` on every
mutating frontend fetch. These tests assert the static wiring is in place
(env read, header attach, build ARG, dev proxy, docs) since the frontend has
no JS test runner.
"""

from pathlib import Path

FRONTEND = Path("frontend")


def test_dockerfile_declares_vite_demo_token_arg():
    content = (FRONTEND / "Dockerfile").read_text()
    assert "ARG VITE_DEMO_TOKEN" in content, (
        "frontend/Dockerfile must declare ARG VITE_DEMO_TOKEN so the token "
        "inlines at npm run build"
    )


def test_env_example_documents_vars():
    env = FRONTEND / ".env.example"
    assert env.exists(), "frontend/.env.example must exist"
    content = env.read_text()
    assert "VITE_DEMO_TOKEN" in content
    assert "VITE_API_BASE" in content


def test_dev_proxy_covers_all_backend_routes():
    content = (FRONTEND / "vite.config.ts").read_text()
    for route in ("/bootstrap", "/resolve", "/admin", "/timeline"):
        assert f"'{route}'" in content, f"dev proxy must forward {route}"


def test_frontend_reads_token_and_attaches_header():
    src = "\n".join(
        p.read_text() for p in (FRONTEND / "src").glob("*.ts*")
    )
    assert "VITE_DEMO_TOKEN" in src, "frontend must read import.meta.env.VITE_DEMO_TOKEN"
    assert "X-Demo-Token" in src, "frontend must attach the X-Demo-Token header"

import yaml
from pathlib import Path


def test_gateway_dockerfile_exists():
    df = Path("gateway/Dockerfile")
    assert df.exists(), "gateway/Dockerfile must exist"
    content = df.read_text()
    assert "python" in content.lower()


def test_frontend_dockerfile_exists():
    df = Path("frontend/Dockerfile")
    assert df.exists(), "frontend/Dockerfile must exist"
    content = df.read_text()
    assert "node" in content.lower()
    assert "nginx" in content.lower()


def test_docker_compose_yml_exists():
    dc = Path("docker-compose.yml")
    assert dc.exists(), "docker-compose.yml must exist"
    config = yaml.safe_load(dc.read_text())
    assert "services" in config
    assert "gateway" in config["services"]
    assert "frontend" in config["services"]


def test_docker_compose_port_mappings():
    dc = Path("docker-compose.yml")
    config = yaml.safe_load(dc.read_text())

    gw_ports = config["services"]["gateway"].get("ports", [])
    assert any("8000" in p for p in gw_ports), "gateway should expose port 8000"

    fe_ports = config["services"]["frontend"].get("ports", [])
    assert any("3000" in p for p in fe_ports), "frontend should expose port 3000"

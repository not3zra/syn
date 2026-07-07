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


class TestApprovePath:
    AGENT_ID = "e2e-approve"

    def test_approve_path_http_response(self, server):
        base_url, db_path = server

        for _ in range(2):
            resp = httpx.post(
                f"{base_url}/intercept",
                json={
                    "action_type": "send_payment",
                    "parameters": {"amount": 50, "recipient": "alice"},
                    "agent_id": self.AGENT_ID,
                },
            )
            assert resp.status_code == 200

        resp = httpx.post(
            f"{base_url}/intercept",
            json={
                "action_type": "send_payment",
                "parameters": {"amount": 50, "recipient": "alice"},
                "agent_id": self.AGENT_ID,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "approved"

    def test_approve_path_sqlite_side_effect(self, server):
        base_url, db_path = server
        store = AuditStore(str(db_path))
        try:
            entries = store.list_all(outcome="approved")
            approved = [e for e in entries if e["action_type"] == "send_payment"]
            assert len(approved) >= 1
            assert approved[-1]["decision"] == "approved"
        finally:
            store.close()


class TestEscalatePath:
    AGENT_ID = "e2e-escalate"

    def test_escalate_path_http_response(self, server):
        base_url, _ = server
        resp = httpx.post(
            f"{base_url}/intercept",
            json={
                "action_type": "delete_file",
                "parameters": {"file_path": "/tmp/customers.xlsx"},
                "agent_id": self.AGENT_ID,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "escalated"

    def test_escalate_path_sqlite_side_effect(self, server):
        base_url, db_path = server
        store = AuditStore(str(db_path))
        try:
            entries = store.list_all(outcome="escalated")
            escalated = [e for e in entries if e["action_type"] == "delete_file"]
            assert len(escalated) >= 1
        finally:
            store.close()


class TestBlockPath:
    AGENT_ID = "e2e-block"

    def test_block_path_http_response(self, server):
        base_url, _ = server
        resp = httpx.post(
            f"{base_url}/intercept",
            json={
                "action_type": "send_payment",
                "parameters": {"amount": 100000, "recipient": "bob"},
                "agent_id": self.AGENT_ID,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "blocked"

    def test_block_path_sqlite_side_effect(self, server):
        base_url, db_path = server
        store = AuditStore(str(db_path))
        try:
            entries = store.list_all(outcome="blocked")
            blocked = [e for e in entries if e["action_type"] == "send_payment"]
            assert len(blocked) >= 1
        finally:
            store.close()

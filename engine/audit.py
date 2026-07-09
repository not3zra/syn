import json
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any


class AuditStore:
    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry TEXT NOT NULL,
                decision TEXT NOT NULL,
                action_type TEXT NOT NULL,
                session_id TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                resolved_at TEXT DEFAULT NULL
            )
        """)
        try:
            self._conn.execute("ALTER TABLE decisions ADD COLUMN session_id TEXT NOT NULL DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        try:
            self._conn.execute("ALTER TABLE decisions ADD COLUMN agent_id TEXT NOT NULL DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_decisions_decision
            ON decisions(decision)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_decisions_created
            ON decisions(created_at)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_decisions_session
            ON decisions(session_id)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_decisions_agent
            ON decisions(agent_id)
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                closed_at TEXT DEFAULT NULL
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_agent
            ON sessions(agent_id)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_status
            ON sessions(status)
        """)
        self._conn.commit()

    def append(self, entry: dict[str, Any], session_id: str = "", agent_id: str = "") -> int:
        decision = entry.get("decision", "unknown")
        action_type = entry.get("action_type", "unknown")
        created_at = entry.get("timestamp", datetime.now(timezone.utc).isoformat())
        sid = session_id or ""
        if not sid:
            sd = entry.get("session_data") or {}
            sid = sd.get("session_id") or ""
        aid = agent_id or entry.get("agent_id", "")

        cursor = self._conn.execute(
            "INSERT INTO decisions (entry, decision, action_type, session_id, agent_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (json.dumps(entry), decision, action_type, sid, aid, created_at),
        )
        self._conn.commit()
        return cursor.lastrowid

    def list_all(
        self,
        outcome: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if outcome:
            rows = self._conn.execute(
                "SELECT * FROM decisions WHERE decision = ? ORDER BY created_at ASC LIMIT ? OFFSET ?",
                (outcome, limit, offset),
            )
        else:
            rows = self._conn.execute(
                "SELECT * FROM decisions ORDER BY created_at ASC LIMIT ? OFFSET ?",
                (limit, offset),
            )

        results = []
        for row in rows.fetchall():
            entry = json.loads(row["entry"])
            entry["id"] = row["id"]
            entry["created_at"] = row["created_at"]
            results.append(entry)
        return results

    def list_pending_escalations(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM decisions WHERE decision = 'escalated' AND (resolved_at IS NULL OR resolved_at = '') ORDER BY created_at ASC"
        )
        return [dict(r) for r in rows.fetchall()]

    def mark_resolved(self, entry_id: int) -> None:
        self._conn.execute(
            "UPDATE decisions SET resolved_at = datetime('now') WHERE id = ?",
            (entry_id,),
        )
        self._conn.commit()

    def expire_old(self, hours: int = 4) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        cursor = self._conn.execute(
            "UPDATE decisions SET resolved_at = 'expired' WHERE decision = 'escalated' AND (resolved_at IS NULL OR resolved_at = '') AND created_at < ?",
            (cutoff,),
        )
        self._conn.commit()
        return cursor.rowcount

    def get_history(self, action_type: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT entry FROM decisions WHERE action_type = ? ORDER BY created_at ASC LIMIT ?",
            (action_type, limit),
        )
        history: list[dict[str, Any]] = []
        for row in rows.fetchall():
            entry = json.loads(row["entry"])
            params = entry.get("parameters") or entry.get("parameters_abstracted", {})
            severity = entry.get("factor_scores", {}).get("severity", 0)
            history.append({
                "action_type": action_type,
                "parameters": params,
                "severity": severity,
            })
        return history

    def get_agent_recent_history(self, agent_id: str, window_minutes: int | None = 30) -> list[dict[str, Any]]:
        rows = None
        if window_minutes is not None:
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=window_minutes)).isoformat()
            rows = self._conn.execute(
                "SELECT entry, action_type FROM decisions WHERE agent_id = ? AND created_at >= ? ORDER BY created_at ASC",
                (agent_id, cutoff),
            )
        else:
            rows = self._conn.execute(
                "SELECT entry, action_type FROM decisions WHERE agent_id = ? ORDER BY created_at ASC",
                (agent_id,),
            )
        history: list[dict[str, Any]] = []
        for row in rows.fetchall():
            entry = json.loads(row["entry"])
            at = row["action_type"]
            params = entry.get("parameters") or entry.get("parameters_abstracted", {})
            severity = entry.get("factor_scores", {}).get("severity", 0)
            history.append({
                "action_type": at,
                "parameters": params,
                "severity": severity,
                "agent_id": agent_id,
            })
        return history

    def get_session_history(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT entry, action_type FROM decisions WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
            (session_id, limit),
        )
        history: list[dict[str, Any]] = []
        for row in rows.fetchall():
            entry = json.loads(row["entry"])
            at = row["action_type"]
            params = entry.get("parameters") or entry.get("parameters_abstracted", {})
            severity = entry.get("factor_scores", {}).get("severity", 0)
            history.append({
                "action_type": at,
                "parameters": params,
                "severity": severity,
            })
        return history

    def create_session(self, agent_id: str) -> str:
        sid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO sessions (id, agent_id, status, created_at) VALUES (?, ?, 'active', ?)",
            (sid, agent_id, now),
        )
        self._conn.commit()
        return sid

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def close_session(self, session_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE sessions SET closed_at = ? WHERE id = ?", (now, session_id),
        )
        self._conn.commit()

    def list_active_sessions(self, agent_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM sessions WHERE agent_id = ? AND status = 'active' AND closed_at IS NULL ORDER BY created_at ASC",
            (agent_id,),
        )
        return [dict(r) for r in rows.fetchall()]

    def close(self):
        self._conn.close()

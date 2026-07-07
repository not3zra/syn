import json
import sqlite3
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
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                resolved_at TEXT DEFAULT NULL
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_decisions_decision
            ON decisions(decision)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_decisions_created
            ON decisions(created_at)
        """)
        self._conn.commit()

    def append(self, entry: dict[str, Any]) -> int:
        decision = entry.get("decision", "unknown")
        action_type = entry.get("action_type", "unknown")
        created_at = entry.get("timestamp", datetime.now(timezone.utc).isoformat())

        cursor = self._conn.execute(
            "INSERT INTO decisions (entry, decision, action_type, created_at) VALUES (?, ?, ?, ?)",
            (json.dumps(entry), decision, action_type, created_at),
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

    def close(self):
        self._conn.close()

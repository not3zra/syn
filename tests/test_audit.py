import json
import tempfile
from pathlib import Path

from engine.audit import AuditStore
from datetime import datetime, timezone, timedelta


class TestAuditStore:
    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.store = AuditStore(self.tmp.name)

    def teardown_method(self):
        self.store.close()
        Path(self.tmp.name).unlink()

    def test_store_and_retrieve(self):
        entry = {
            "decision": "approved",
            "trigger": "weighted_score",
            "action_type": "send_payment",
        }
        self.store.append(entry)
        entries = self.store.list_all()
        assert len(entries) == 1
        assert entries[0]["decision"] == "approved"
        assert entries[0]["action_type"] == "send_payment"

    def test_multiple_entries_chronological(self):
        self.store.append({"action_type": "first", "decision": "approved"})
        self.store.append({"action_type": "second", "decision": "blocked"})
        self.store.append({"action_type": "third", "decision": "escalated"})
        entries = self.store.list_all()
        assert len(entries) == 3
        assert [e["action_type"] for e in entries] == ["first", "second", "third"]

    def test_filter_by_outcome(self):
        self.store.append({"action_type": "a", "decision": "approved"})
        self.store.append({"action_type": "b", "decision": "blocked"})
        self.store.append({"action_type": "c", "decision": "escalated"})
        self.store.append({"action_type": "d", "decision": "approved"})

        approved = self.store.list_all(outcome="approved")
        assert len(approved) == 2
        assert all(e["decision"] == "approved" for e in approved)

        blocked = self.store.list_all(outcome="blocked")
        assert len(blocked) == 1

    def test_full_decision_object_stored(self):
        full = {
            "decision": "blocked",
            "trigger": "decision_tree:severity_floor",
            "factor_scores": {"severity": 95},
            "session_data": {"session_id": None, "cumulative_severity": 0, "pattern_matched": False},
            "regulatory_tier": "minimal_risk",
            "us_regime_flags": [],
            "action_type": "delete_file",
            "timestamp": "2026-07-07T12:00:00Z",
        }
        self.store.append(full)
        entries = self.store.list_all()
        stored = entries[0]
        assert stored["decision"] == "blocked"
        assert stored["trigger"] == "decision_tree:severity_floor"
        assert stored["factor_scores"]["severity"] == 95
        assert stored["timestamp"] == "2026-07-07T12:00:00Z"

    def test_append_only(self):
        self.store.append({"action_type": "a", "decision": "approved"})
        entries = self.store.list_all()
        assert len(entries) == 1

    def test_pending_escalations(self):
        self.store.append({"action_type": "a", "decision": "escalated"})
        self.store.append({"action_type": "b", "decision": "approved"})
        self.store.append({"action_type": "c", "decision": "escalated"})

        pending = self.store.list_pending_escalations()
        assert len(pending) == 2

    def test_mark_resolved(self):
        self.store.append({"action_type": "a", "decision": "escalated"})
        entries = self.store.list_all()
        entry_id = entries[0]["id"]

        self.store.mark_resolved(entry_id)
        pending = self.store.list_pending_escalations()
        assert len(pending) == 0

    def test_auto_expire(self):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        old = (now - timedelta(hours=5)).isoformat()
        recent = (now - timedelta(hours=1)).isoformat()

        self.store.append({"action_type": "a", "decision": "escalated", "timestamp": old})
        self.store.append({"action_type": "b", "decision": "escalated", "timestamp": recent})

        self.store.expire_old(hours=4)
        pending = self.store.list_pending_escalations()
        assert len(pending) == 1
        assert pending[0]["action_type"] == "b"

    def test_get_history_returns_entries_for_action_type(self):
        self.store.append({
            "decision": "approved",
            "action_type": "send_payment",
            "parameters_abstracted": {"amount_category": "low"},
            "factor_scores": {"severity": 20},
        })
        self.store.append({
            "decision": "escalated",
            "action_type": "query_database",
        })
        self.store.append({
            "decision": "approved",
            "action_type": "send_payment",
            "factor_scores": {"severity": 50},
        })

        history = self.store.get_history("send_payment")
        assert len(history) == 2
        assert all(h["action_type"] == "send_payment" for h in history)
        assert history[0]["severity"] == 20
        assert history[1]["severity"] == 50

    def test_get_history_returns_empty_list_when_no_matches(self):
        history = self.store.get_history("nonexistent")
        assert history == []

    def test_agent_id_column_exists(self):
        proxy = self.store._conn.execute(
            "PRAGMA table_info(decisions)"
        ).fetchall()
        cols = {r["name"] for r in proxy}
        assert "agent_id" in cols, f"Expected agent_id column, got {cols}"

    def test_agent_id_index_exists(self):
        indexes = self.store._conn.execute(
            "PRAGMA index_list(decisions)"
        ).fetchall()
        names = {r["name"] for r in indexes}
        assert "idx_decisions_agent" in names

    def test_append_stores_agent_id(self):
        entry = {
            "decision": "approved",
            "action_type": "send_payment",
            "agent_id": "agent_alpha",
        }
        self.store.append(entry, agent_id="agent_alpha")
        row = self.store._conn.execute(
            "SELECT agent_id FROM decisions WHERE id = ?", (1,)
        ).fetchone()
        assert row["agent_id"] == "agent_alpha"

    def test_get_agent_recent_history_all_unbounded(self):
        self.store.append({"decision": "approved", "action_type": "send_payment"}, agent_id="agent_1")
        self.store.append({"decision": "approved", "action_type": "check_balance"}, agent_id="agent_1")
        history = self.store.get_agent_recent_history("agent_1", window_minutes=None)
        assert len(history) == 2
        assert all(h["agent_id"] == "agent_1" for h in history)

    def test_get_agent_recent_history_windowed(self):
        from datetime import datetime, timezone, timedelta
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        recent_ts = datetime.now(timezone.utc).isoformat()
        self.store.append({
            "decision": "approved", "action_type": "send_payment", "timestamp": old_ts
        }, agent_id="agent_1")
        self.store.append({
            "decision": "approved", "action_type": "check_balance", "timestamp": recent_ts
        }, agent_id="agent_1")
        history = self.store.get_agent_recent_history("agent_1", window_minutes=30)
        assert len(history) == 1
        assert history[0]["action_type"] == "check_balance"

    def test_get_agent_recent_history_other_agent_excluded(self):
        self.store.append({"decision": "approved", "action_type": "send_payment"}, agent_id="agent_1")
        self.store.append({"decision": "approved", "action_type": "delete_file"}, agent_id="agent_2")
        history = self.store.get_agent_recent_history("agent_1")
        assert len(history) == 1
        assert history[0]["action_type"] == "send_payment"

    def test_get_history_limited_to_recent_entries(self):
        for i in range(5):
            self.store.append({
                "decision": "approved",
                "action_type": "send_payment",
                "factor_scores": {"severity": 10},
            })

        history = self.store.get_history("send_payment", limit=3)
        assert len(history) == 3

    def test_retention_deletes_old_entries(self):
        now = datetime.now(timezone.utc)
        very_old = (now - timedelta(days=100)).isoformat()
        recent = (now - timedelta(days=30)).isoformat()

        self.store.append({"action_type": "a", "decision": "approved", "timestamp": very_old})
        self.store.append({"action_type": "b", "decision": "approved", "timestamp": recent})

        self.store.expire_old(retention_days=90)
        remaining = self.store.list_all()
        assert len(remaining) == 1
        assert remaining[0]["action_type"] == "b"

    def test_retention_keeps_recent_entries(self):
        """Entries within retention period are preserved."""
        now = datetime.now(timezone.utc)
        borderline = (now - timedelta(days=89)).isoformat()
        self.store.append({"action_type": "x", "decision": "approved", "timestamp": borderline})
        self.store.expire_old(retention_days=90)
        remaining = self.store.list_all()
        assert len(remaining) == 1


class TestSessionLifecycle:
    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.store = AuditStore(self.tmp.name)

    def teardown_method(self):
        self.store.close()
        Path(self.tmp.name).unlink()

    def test_create_session_returns_uuid(self):
        sid = self.store.create_session("agent_1")
        assert isinstance(sid, str)
        assert len(sid) > 20

    def test_get_session_returns_none_for_unknown(self):
        session = self.store.get_session("nonexistent")
        assert session is None

    def test_get_session_returns_created_session(self):
        sid = self.store.create_session("agent_1")
        session = self.store.get_session(sid)
        assert session is not None
        assert session["id"] == sid
        assert session["agent_id"] == "agent_1"
        assert session["status"] == "active"
        assert session["closed_at"] is None

    def test_create_and_close_session(self):
        sid = self.store.create_session("agent_1")
        self.store.close_session(sid)
        session = self.store.get_session(sid)
        assert session["status"] == "active"
        assert session["closed_at"] is not None

    def test_list_active_sessions_empty_for_new_agent(self):
        active = self.store.list_active_sessions("unknown_agent")
        assert active == []

    def test_list_active_sessions_returns_only_active(self):
        sid1 = self.store.create_session("agent_1")
        sid2 = self.store.create_session("agent_1")
        self.store.close_session(sid1)
        active = self.store.list_active_sessions("agent_1")
        assert len(active) == 1
        assert active[0]["id"] == sid2

    def test_concurrent_sessions_allowed(self):
        sid1 = self.store.create_session("agent_1")
        sid2 = self.store.create_session("agent_1")
        active = self.store.list_active_sessions("agent_1")
        assert len(active) == 2

    def test_sessions_scoped_by_agent(self):
        sid1 = self.store.create_session("agent_1")
        sid2 = self.store.create_session("agent_2")
        active_1 = self.store.list_active_sessions("agent_1")
        active_2 = self.store.list_active_sessions("agent_2")
        assert len(active_1) == 1
        assert len(active_2) == 1
        assert active_1[0]["id"] == sid1
        assert active_2[0]["id"] == sid2


class TestPendingRules:
    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.store = AuditStore(self.tmp.name)

    def teardown_method(self):
        self.store.close()
        Path(self.tmp.name).unlink()

    def test_create_pending_rule(self):
        pid = self.store.create_pending_rule(
            tool_name="unknown_tool",
            proposed_yaml="tools:\n  unknown_tool:\n    tool_trust_tier: unknown",
            schemas_json='[{"name": "unknown_tool", "parameters": {}}]',
        )
        assert isinstance(pid, int)
        assert pid > 0

    def test_list_pending_rules_empty_initially(self):
        rules = self.store.list_pending_rules()
        assert rules == []

    def test_list_pending_rules_returns_created(self):
        self.store.create_pending_rule("tool_a", "yaml_a", "[]")
        self.store.create_pending_rule("tool_b", "yaml_b", "[]")
        rules = self.store.list_pending_rules()
        assert len(rules) == 2
        assert rules[0]["tool_name"] == "tool_a"
        assert rules[0]["status"] == "pending"
        assert rules[1]["tool_name"] == "tool_b"

    def test_approve_pending_rule(self):
        pid = self.store.create_pending_rule("tool_a", "yaml_a", "[]")
        self.store.approve_pending_rule("tool_a", reviewed_by="demo-admin")
        rules = self.store.list_pending_rules()
        assert len(rules) == 0

        row = self.store._conn.execute(
            "SELECT * FROM pending_rules WHERE id = ?", (pid,)
        ).fetchone()
        assert row["status"] == "approved"
        assert row["reviewed_by"] == "demo-admin"

    def test_reject_pending_rule(self):
        self.store.create_pending_rule("tool_a", "yaml_a", "[]")
        self.store.reject_pending_rule("tool_a", reviewed_by="demo-admin")
        rules = self.store.list_pending_rules()
        assert len(rules) == 0

        row = self.store._conn.execute(
            "SELECT * FROM pending_rules WHERE id = ?", (1,)
        ).fetchone()
        assert row["status"] == "rejected"
        assert row["reviewed_by"] == "demo-admin"

    def test_approve_only_matching_tool(self):
        self.store.create_pending_rule("tool_a", "yaml_a", "[]")
        self.store.create_pending_rule("tool_b", "yaml_b", "[]")
        self.store.approve_pending_rule("tool_a", reviewed_by="demo-admin")
        rules = self.store.list_pending_rules()
        assert len(rules) == 1
        assert rules[0]["tool_name"] == "tool_b"

    def test_approve_all(self):
        self.store.create_pending_rule("tool_a", "yaml_a", "[]")
        self.store.create_pending_rule("tool_b", "yaml_b", "[]")
        self.store.approve_all_pending(reviewed_by="demo-admin")
        rules = self.store.list_pending_rules()
        assert len(rules) == 0
        rows = self.store._conn.execute(
            "SELECT * FROM pending_rules"
        ).fetchall()
        assert all(r["status"] == "approved" for r in rows)
        assert all(r["reviewed_by"] == "demo-admin" for r in rows)

    def test_retry_pending_rule_increments_attempts(self):
        pid = self.store.create_pending_rule("tool_a", "yaml_a", "[]")
        self.store.mark_pending_rule_error(pid, "LLM failed")
        self.store.retry_pending_rule(pid, "new_yaml", "[]")
        row = self.store._conn.execute(
            "SELECT * FROM pending_rules WHERE id = ?", (pid,)
        ).fetchone()
        assert row["status"] == "pending"
        assert row["error_message"] is None
        assert row["generation_attempts"] == 2
        assert row["proposed_yaml"] == "new_yaml"

    def test_mark_pending_rule_error(self):
        pid = self.store.create_pending_rule("tool_a", "yaml_a", "[]")
        self.store.mark_pending_rule_error(pid, "LLM generation failed")
        row = self.store._conn.execute(
            "SELECT * FROM pending_rules WHERE id = ?", (pid,)
        ).fetchone()
        assert row["status"] == "error"
        assert row["error_message"] == "LLM generation failed"
        assert row["generation_attempts"] == 1

    def test_get_pending_rule_by_tool_name(self):
        self.store.create_pending_rule("tool_a", "yaml_a", "[]")
        self.store.create_pending_rule("tool_b", "yaml_b", "[]")
        row = self.store.get_pending_rule_by_tool("tool_a")
        assert row is not None
        assert row["tool_name"] == "tool_a"
        assert row["status"] == "pending"

    def test_get_pending_rule_by_tool_not_found(self):
        row = self.store.get_pending_rule_by_tool("nonexistent")
        assert row is None

import json
import tempfile
from pathlib import Path

from engine.audit import AuditStore


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
        self.store.append({"action_type": "a", "decision": "escalated", "timestamp": "2026-01-01T00:00:00Z"})
        self.store.append({"action_type": "b", "decision": "escalated", "timestamp": "2026-07-07T12:00:00Z"})

        self.store.expire_old(hours=4)
        pending = self.store.list_pending_escalations()
        assert len(pending) == 1
        assert pending[0]["action_type"] == "b"

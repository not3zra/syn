import yaml
from pathlib import Path

from engine.severity import score_severity
from engine.policy import score_policy
from engine.anomaly import score_anomaly
from engine.data_sensitivity import score_data_sensitivity
from engine.confidence import score_confidence
from engine.tool_trust import score_tool_trust
from engine.decision_tree import apply_decision_tree, compute_weighted_score
from engine.models import Decision, FactorScores


def load_config():
    path = Path(__file__).parent.parent / "engine" / "policy_config.yaml"
    return yaml.safe_load(path.read_text())


CONFIG = load_config()


class TestSeverity:
    def test_send_payment_low_amount(self):
        assert score_severity("send_payment", {"amount": 50}, CONFIG) == 20

    def test_send_payment_medium_amount(self):
        assert score_severity("send_payment", {"amount": 3000}, CONFIG) == 50

    def test_send_payment_high_amount(self):
        assert score_severity("send_payment", {"amount": 8000}, CONFIG) == 80

    def test_send_payment_very_high(self):
        assert score_severity("send_payment", {"amount": 100000}, CONFIG) == 95

    def test_delete_file_prod(self):
        assert score_severity("delete_file", {"file_path": "/data/prod/db.sqlite"}, CONFIG) == 90

    def test_delete_file_etc(self):
        assert score_severity("delete_file", {"file_path": "/etc/passwd"}, CONFIG) == 95

    def test_delete_file_other(self):
        assert score_severity("delete_file", {"file_path": "/tmp/test.txt"}, CONFIG) == 60

    def test_query_database_select(self):
        assert score_severity("query_database", {"query": "SELECT * FROM users"}, CONFIG) == 10

    def test_query_database_ddl(self):
        assert score_severity("query_database", {"query": "DROP TABLE users"}, CONFIG) == 90

    def test_query_database_dml(self):
        assert score_severity("query_database", {"query": "UPDATE users SET name='x'"}, CONFIG) == 40

    def test_unknown_tool_defaults(self):
        assert score_severity("unknown_tool", {}, CONFIG) == 50


class TestPolicy:
    def test_no_policy_violation_low_amount(self):
        assert score_policy("send_payment", {"amount": 100}, CONFIG) == 0

    def test_policy_violation_high_amount(self):
        assert score_policy("send_payment", {"amount": 10000}, CONFIG) == 100

    def test_no_policy_rules(self):
        assert score_policy("delete_file", {"file_path": "/tmp/test.txt"}, CONFIG) == 0

    def test_destructive_query_policy(self):
        assert score_policy("query_database", {"query": "DROP TABLE users"}, CONFIG) == 100

    def test_safe_query_no_policy(self):
        assert score_policy("query_database", {"query": "SELECT * FROM users"}, CONFIG) == 0


class TestAnomaly:
    def test_no_history(self):
        assert score_anomaly("send_payment", {"amount": 100}, CONFIG) == 0

    def test_single_entry(self):
        assert score_anomaly("send_payment", {"amount": 100}, CONFIG, [{"action_type": "send_payment", "parameters": {"amount": 50}}]) == 5

    def test_normal_amount(self):
        history = [{"action_type": "send_payment", "parameters": {"amount": a}} for a in [90, 95, 100, 105, 110]]
        assert score_anomaly("send_payment", {"amount": 100}, CONFIG, history) == 5

    def test_anomalous_amount(self):
        history = [{"action_type": "send_payment", "parameters": {"amount": a}} for a in [10, 15, 12, 18, 14]]
        assert score_anomaly("send_payment", {"amount": 1000}, CONFIG, history) >= 50


class TestDataSensitivity:
    def test_internal_recipient(self):
        assert score_data_sensitivity("send_payment", {"recipient": "alice"}, CONFIG) == 0

    def test_external_recipient(self):
        assert score_data_sensitivity("send_payment", {"recipient": "external_vendor"}, CONFIG) == 40

    def test_path_with_customer(self):
        assert score_data_sensitivity("delete_file", {"file_path": "/data/customers.xlsx"}, CONFIG) == 80

    def test_destructive_query(self):
        assert score_data_sensitivity("query_database", {"query": "DROP TABLE users"}, CONFIG) >= 70

    def test_safe_query(self):
        assert score_data_sensitivity("query_database", {"query": "SELECT count(*) FROM products"}, CONFIG) == 10


class TestConfidence:
    def test_no_history(self):
        assert score_confidence("send_payment", {}, CONFIG) == 20

    def test_low_history(self):
        assert score_confidence("send_payment", {}, CONFIG, [{"action_type": "send_payment"}]) == 30

    def test_medium_history(self):
        history = [{"action_type": "send_payment"} for _ in range(5)]
        assert score_confidence("send_payment", {}, CONFIG, history) == 70

    def test_high_history(self):
        history = [{"action_type": "send_payment"} for _ in range(10)]
        assert score_confidence("send_payment", {}, CONFIG, history) == 90


class TestToolTrust:
    def test_official(self):
        assert score_tool_trust("send_payment", {}, CONFIG) == 100

    def test_verified(self):
        assert score_tool_trust("delete_file", {}, CONFIG) == 80

    def test_unknown(self):
        assert score_tool_trust("unknown_tool", {}, CONFIG) == 40


class TestDecisionTree:
    def test_severity_floor_blocks(self):
        scores = FactorScores(severity=95, confidence=80)
        decision, trigger = apply_decision_tree(scores, CONFIG)
        assert decision == Decision.BLOCKED
        assert trigger == "decision_tree:severity_floor"

    def test_policy_floor_blocks(self):
        scores = FactorScores(policy=100, severity=50, confidence=80)
        decision, trigger = apply_decision_tree(scores, CONFIG)
        assert decision == Decision.BLOCKED

    def test_confidence_floor_escalates(self):
        scores = FactorScores(severity=50, policy=0, confidence=30)
        decision, trigger = apply_decision_tree(scores, CONFIG)
        assert decision == Decision.ESCALATED

    def test_no_floor_passes(self):
        scores = FactorScores(severity=50, policy=0, confidence=80)
        decision, trigger = apply_decision_tree(scores, CONFIG)
        assert decision is None

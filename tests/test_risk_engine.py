import yaml
from pathlib import Path

from engine.evaluate import evaluate
from engine.models import Decision


def load_config():
    path = Path(__file__).parent.parent / "engine" / "policy_config.yaml"
    return yaml.safe_load(path.read_text())


CONFIG = load_config()


def test_approve_low_risk_payment():
    history = [{"action_type": "send_payment", "parameters": {"amount": a}} for a in [30, 45, 55, 60, 40, 35, 50, 48, 52, 42]]
    result = evaluate(
        action_type="send_payment",
        parameters={"amount": 50, "currency": "USD", "recipient": "alice"},
        session_context={"history": history, "session_id": None},
        config=CONFIG,
    )
    assert result.decision == Decision.APPROVED


def test_block_high_severity_payment():
    result = evaluate(
        action_type="send_payment",
        parameters={"amount": 100000, "currency": "USD", "recipient": "bob"},
        session_context={"history": [], "session_id": None},
        config=CONFIG,
    )
    assert result.decision == Decision.BLOCKED
    assert result.trigger == "decision_tree:severity_floor"


def test_block_policy_violation():
    result = evaluate(
        action_type="send_payment",
        parameters={"amount": 10000, "currency": "USD", "recipient": "external"},
        session_context={"history": [], "session_id": None},
        config=CONFIG,
    )
    assert result.decision == Decision.BLOCKED
    assert "policy" in result.trigger.lower()


def test_escalate_low_confidence():
    result = evaluate(
        action_type="delete_file",
        parameters={"file_path": "/tmp/customers.xlsx"},
        session_context={"history": [], "session_id": None},
        config=CONFIG,
    )
    assert result.decision == Decision.ESCALATED
    assert "weighted_score" in result.trigger


def test_escalate_weighted_score():
    history = [{"action_type": "delete_file", "parameters": {"file_path": "/tmp/test.txt"}} for _ in range(5)]
    result = evaluate(
        action_type="delete_file",
        parameters={"file_path": "/tmp/customers.xlsx"},
        session_context={"history": history, "session_id": None},
        config=CONFIG,
    )
    assert result.decision == Decision.ESCALATED
    assert "weighted_score" in result.trigger


def test_block_via_severity_floor():
    history = [{"action_type": "delete_file", "parameters": {"file_path": "/tmp/test.txt"}} for _ in range(5)]
    result = evaluate(
        action_type="delete_file",
        parameters={"file_path": "/etc/shadow"},
        session_context={"history": history, "session_id": None},
        config=CONFIG,
    )
    assert result.decision == Decision.BLOCKED
    assert result.trigger == "decision_tree:severity_floor"


def test_approve_query_database_select():
    history = [{"action_type": "query_database", "parameters": {"query": "SELECT * FROM users"}} for _ in range(5)]
    result = evaluate(
        action_type="query_database",
        parameters={"query": "SELECT id, name FROM users WHERE id = 1"},
        session_context={"history": history, "session_id": None},
        config=CONFIG,
    )
    assert result.decision == Decision.APPROVED


def test_block_destructive_query():
    result = evaluate(
        action_type="query_database",
        parameters={"query": "DROP TABLE users"},
        session_context={"history": [], "session_id": None},
        config=CONFIG,
    )
    assert result.decision == Decision.BLOCKED


def test_approve_check_balance():
    history = [{"action_type": "check_balance", "parameters": {"account_id": "acc_123"}} for _ in range(10)]
    result = evaluate(
        action_type="check_balance",
        parameters={"account_id": "acc_123"},
        session_context={"history": history, "session_id": None},
        config=CONFIG,
    )
    assert result.decision == Decision.APPROVED


def test_session_escalates_on_pattern_match():
    history = [
        {"action_type": "check_balance", "parameters": {"account_id": "acc_123"}, "severity": 15},
    ]
    result = evaluate(
        action_type="send_payment",
        parameters={"amount": 50, "currency": "USD", "recipient": "alice"},
        session_context={"history": history, "session_id": "agent_1:1"},
        config=CONFIG,
    )
    assert result.decision == Decision.ESCALATED
    assert result.trigger == "session:pattern_matched"
    assert result.session_data.pattern_matched is True


def test_session_escalates_on_cumulative_threshold():
    history = [
        {"action_type": "check_balance", "parameters": {"account_id": "acc_123"}, "severity": 30},
        {"action_type": "check_balance", "parameters": {"account_id": "acc_456"}, "severity": 30},
        {"action_type": "check_balance", "parameters": {"account_id": "acc_789"}, "severity": 30},
    ]
    result = evaluate(
        action_type="check_balance",
        parameters={"amount": 50, "currency": "USD", "recipient": "alice"},
        session_context={"history": history, "session_id": "agent_1:1"},
        config=CONFIG,
    )
    assert result.decision == Decision.ESCALATED
    assert result.trigger == "session:cumulative_threshold"
    assert result.session_data.cumulative_severity == 90.0


def test_session_data_included_in_result():
    history = [{"action_type": "check_balance", "parameters": {"account_id": "acc_123"}, "severity": 15}]
    result = evaluate(
        action_type="check_balance",
        parameters={"account_id": "acc_123"},
        session_context={"history": history, "session_id": "agent_1:2"},
        config=CONFIG,
    )
    assert result.session_data.session_id == "agent_1:2"
    assert result.session_data.cumulative_severity == 15.0
    assert result.session_data.pattern_matched is False

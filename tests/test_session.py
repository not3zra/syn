import yaml
from pathlib import Path

from engine.session import (
    generate_session_id,
    find_risky_sequence,
    compute_cumulative_severity,
    score_session,
)


def load_sequences():
    path = Path(__file__).parent.parent / "engine" / "risky_sequences.yaml"
    return yaml.safe_load(path.read_text())


SEQUENCES = load_sequences()


def test_session_id_generation():
    sid = generate_session_id("agent_1", 1000)
    assert sid == "agent_1:1"  # 1000 // 600 = 1

    sid2 = generate_session_id("agent_1", 3500)
    assert sid2 == "agent_1:5"  # 3500 // 600 = 5

    sid3 = generate_session_id("agent_2", 1000)
    assert "agent_2" in sid3


def test_session_id_different_agents():
    s1 = generate_session_id("alice", 1000)
    s2 = generate_session_id("bob", 1000)
    assert s1 != s2


def test_no_risky_sequence_empty_history():
    assert find_risky_sequence([], "send_payment", SEQUENCES) is None


def test_no_risky_sequence_no_match():
    history = [{"action_type": "check_balance"}]
    assert find_risky_sequence(history, "check_balance", SEQUENCES) is None


def test_detect_check_balance_send_payment():
    history = [
        {"action_type": "check_balance"},
    ]
    match = find_risky_sequence(history, "send_payment", SEQUENCES)
    assert match is not None
    assert match["pair"] == ["check_balance", "send_payment"]


def test_detect_query_database_delete_file():
    history = [
        {"action_type": "query_database"},
    ]
    match = find_risky_sequence(history, "delete_file", SEQUENCES)
    assert match is not None
    assert match["pair"] == ["query_database", "delete_file"]


def test_no_match_wrong_order():
    history = [
        {"action_type": "send_payment"},
    ]
    assert find_risky_sequence(history, "check_balance", SEQUENCES) is None


def test_match_with_deeper_history():
    history = [
        {"action_type": "check_balance"},
        {"action_type": "check_balance"},
        {"action_type": "check_balance"},
    ]
    match = find_risky_sequence(history, "send_payment", SEQUENCES)
    assert match is not None
    assert match["pair"] == ["check_balance", "send_payment"]


def test_cumulative_severity_empty():
    assert compute_cumulative_severity([]) == 0.0


def test_cumulative_severity_single():
    history = [{"severity": 15}]
    assert compute_cumulative_severity(history) == 15.0


def test_cumulative_severity_sum():
    history = [{"severity": 15}, {"severity": 50}, {"severity": 10}]
    assert compute_cumulative_severity(history) == 75.0


def test_cumulative_severity_below_threshold():
    history = [{"severity": 15}, {"severity": 15}, {"severity": 15}]
    assert compute_cumulative_severity(history) == 45.0


def test_score_session_no_risk():
    history = [
        {"action_type": "check_balance", "severity": 15},
    ]
    result = score_session(history, "check_balance", SEQUENCES, threshold=70)
    assert result["pattern_matched"] is False
    assert result["cumulative_severity"] == 15.0


def test_score_session_pattern_matched():
    history = [
        {"action_type": "check_balance", "severity": 15},
    ]
    result = score_session(history, "send_payment", SEQUENCES, threshold=70)
    assert result["pattern_matched"] is True
    assert result["cumulative_severity"] == 15.0


def test_score_session_threshold_exceeded():
    history = [
        {"severity": 30},
        {"severity": 30},
        {"severity": 30},
    ]
    result = score_session(history, "check_balance", SEQUENCES, threshold=70)
    assert result["pattern_matched"] is False
    assert result["cumulative_severity"] == 90.0


def test_demo_constants():
    check_balance = 15
    send_payment = 50
    assert 3 * check_balance == 45
    assert 45 + send_payment == 95
    assert 45 < 70 < 95

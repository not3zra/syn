from typing import Any


def generate_session_id(agent_id: str, timestamp: int) -> str:
    bucket = timestamp // 600
    return f"{agent_id}:{bucket}"


def find_risky_sequence(
    history: list[dict[str, Any]],
    current_action_type: str,
    sequences_config: dict[str, Any],
) -> dict[str, Any] | None:
    if not history:
        return None

    sequences = sequences_config.get("sequences", [])

    last_action_type = history[-1].get("action_type", "") if history else ""
    recent_pair = (last_action_type, current_action_type)

    for seq in sequences:
        pair = seq.get("pair", [])
        if len(pair) >= 2 and recent_pair == (pair[0], pair[1]):
            return seq

    return None


def compute_cumulative_severity(history: list[dict[str, Any]]) -> float:
    return sum(h.get("severity", 0) for h in history)


def score_session(
    history: list[dict[str, Any]],
    current_action_type: str,
    sequences_config: dict[str, Any],
    threshold: float = 70.0,
) -> dict[str, Any]:
    pattern_matched = find_risky_sequence(history, current_action_type, sequences_config) is not None
    cumulative_severity = compute_cumulative_severity(history)

    return {
        "pattern_matched": pattern_matched,
        "cumulative_severity": cumulative_severity,
        "threshold_exceeded": cumulative_severity > threshold,
    }

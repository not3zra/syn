from typing import Any


def generate_session_id(agent_id: str, timestamp: int) -> str:
    bucket = timestamp // 600
    return f"{agent_id}:{bucket}"


def _is_subsequence(pattern: list[str], history_types: list[str]) -> bool:
    it = iter(history_types)
    return all(act in it for act in pattern)


def find_risky_patterns(
    history: list[dict[str, Any]],
    current_action_type: str,
    sequences_config: dict[str, Any],
) -> list[dict[str, Any]]:
    if not history:
        return []

    sequences = sequences_config.get("sequences", [])
    history_types = [h.get("action_type", "") for h in history] + [current_action_type]

    matches: list[dict[str, Any]] = []
    for seq in sequences:
        actions = seq.get("actions", [])
        if len(actions) >= 2 and _is_subsequence(actions, history_types):
            matches.append(seq)

    return matches


def compute_cumulative_severity(history: list[dict[str, Any]]) -> float:
    return sum(h.get("severity", 0) for h in history)


def _format_pattern_trigger(matches: list[dict[str, Any]]) -> str:
    parts = []
    for m in matches:
        actions = m.get("actions", [])
        parts.append("_".join(actions))
    return "+".join(parts)


def score_session(
    history: list[dict[str, Any]],
    current_action_type: str,
    sequences_config: dict[str, Any],
    threshold: float = 70.0,
) -> dict[str, Any]:
    matched_patterns = find_risky_patterns(history, current_action_type, sequences_config)
    cumulative_severity = compute_cumulative_severity(history)

    result: dict[str, Any] = {
        "pattern_matched": len(matched_patterns) > 0,
        "cumulative_severity": cumulative_severity,
        "threshold_exceeded": cumulative_severity > threshold,
        "matched_patterns": matched_patterns,
    }

    if matched_patterns:
        result["matched_patterns_str"] = _format_pattern_trigger(matched_patterns)
        result["matched_pair"] = _format_pattern_trigger(matched_patterns)

    return result

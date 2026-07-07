from engine.models import Decision, FactorScores


def apply_decision_tree(
    factor_scores: FactorScores, config: dict
) -> tuple[Decision | None, str | None]:
    decision_tree_thresholds = config.get("decision_tree", {})

    severity_floor = decision_tree_thresholds.get("severity_floor", 90)
    confidence_floor = decision_tree_thresholds.get("confidence_floor", 40)

    if factor_scores.severity > severity_floor:
        return Decision.BLOCKED, "decision_tree:severity_floor"

    if factor_scores.policy >= 100:
        return Decision.BLOCKED, "decision_tree:policy_floor"

    if factor_scores.confidence < confidence_floor:
        return Decision.ESCALATED, "decision_tree:confidence_floor"

    return None, None


def apply_session_branches(
    session_info: dict, config: dict
) -> tuple[Decision | None, str | None]:
    session_threshold = config.get("decision_tree", {}).get("session_threshold", 70)

    if session_info.get("pattern_matched"):
        pair = session_info.get("matched_pair", "unknown")
        return Decision.ESCALATED, f"session:pattern_matched:{pair}"

    if session_info.get("cumulative_severity", 0) > session_threshold:
        return Decision.ESCALATED, "session:cumulative_threshold"

    return None, None


def compute_weighted_score(factor_scores: FactorScores, config: dict) -> float:
    weights = config.get("weights", {})
    return (
        factor_scores.severity * weights.get("severity", 0.30)
        + factor_scores.policy * weights.get("policy", 0.20)
        + factor_scores.anomaly * weights.get("anomaly", 0.10)
        + factor_scores.data_sensitivity * weights.get("data_sensitivity", 0.15)
        + (100 - factor_scores.confidence) * weights.get("confidence", 0.05)
        + (100 - factor_scores.tool_trust) * weights.get("tool_trust", 0.20)
    )


def apply_weighted_decision(weighted_score: float, config: dict) -> Decision:
    thresholds = config.get("thresholds", {}).get("weighted_score", {})
    block_min = thresholds.get("block_min", 55.0)
    escalate_min = thresholds.get("escalate_min", 30.0)

    if weighted_score >= block_min:
        return Decision.BLOCKED
    if weighted_score >= escalate_min:
        return Decision.ESCALATED
    return Decision.APPROVED

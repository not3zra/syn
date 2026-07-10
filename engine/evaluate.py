from pathlib import Path

import yaml

from engine.models import Decision, FactorScores, SessionData, RiskEngineResult
from engine.severity import score_severity
from engine.policy import score_policy
from engine.anomaly import score_anomaly
from engine.data_sensitivity import score_data_sensitivity
from engine.confidence import score_confidence
from engine.tool_trust import score_tool_trust
from engine.session import score_session
from engine.regulatory import map_regulatory_tier, map_us_regime_flags
from engine.decision_tree import (
    apply_decision_tree,
    apply_session_branches,
    compute_weighted_score,
    apply_weighted_decision,
)

_seq_config_path = Path(__file__).resolve().parent / "risky_sequences.yaml"
DEFAULT_SEQUENCES = (
    yaml.safe_load(_seq_config_path.read_text()) if _seq_config_path.exists() else {}
)


def evaluate(
    action_type: str,
    parameters: dict,
    session_context: dict | None = None,
    config: dict | None = None,
) -> RiskEngineResult:
    if config is None:
        config = {}

    ctx = session_context or {}
    history = ctx.get("history", [])
    unbounded_history = ctx.get("unbounded_history", history)
    session_threshold = ctx.get("session_threshold", 70)

    sequences_config = config.get("sequences_config", DEFAULT_SEQUENCES)

    severity, severity_reason = score_severity(action_type, parameters, config)
    policy, policy_reason = score_policy(action_type, parameters, config)
    anomaly = score_anomaly(action_type, parameters, config, history)
    data_sensitivity, data_sensitivity_reason = score_data_sensitivity(
        action_type, parameters, config
    )
    confidence, confidence_reason = score_confidence(
        action_type, parameters, config, unbounded_history
    )
    tool_trust = score_tool_trust(action_type, parameters, config)

    factor_scores = FactorScores(
        severity=severity,
        policy=policy,
        anomaly=anomaly,
        data_sensitivity=data_sensitivity,
        confidence=confidence,
        tool_trust=tool_trust,
    )

    regulatory_tier = map_regulatory_tier(action_type, factor_scores, config)
    us_regime_flags = map_us_regime_flags(action_type, config)

    session_info = score_session(history, action_type, sequences_config, threshold=session_threshold)
    session_data = SessionData(
        session_id=ctx.get("session_id"),
        cumulative_severity=session_info["cumulative_severity"],
        pattern_matched=session_info["pattern_matched"],
    )

    session_decision, session_trigger = apply_session_branches(session_info, config)
    if session_decision is not None:
        if session_trigger and session_trigger.startswith("session:pattern_matched"):
            pair = session_info.get("matched_pair", "unknown")
            reason = (
                f"Recognized risky sequence '{pair}' "
                "(for example, a reconnaissance step followed by an action)."
            )
        else:
            reason = (
                f"Cumulative session severity {session_info['cumulative_severity']:.0f} "
                f"exceeds the threshold of {session_threshold}."
            )
        return RiskEngineResult(
            decision=session_decision,
            trigger=session_trigger or "session:escalated",
            reason=reason,
            factor_scores=factor_scores,
            session_data=session_data,
            regulatory_tier=regulatory_tier,
            us_regime_flags=us_regime_flags,
        )

    floor_decision, floor_trigger = apply_decision_tree(factor_scores, config)

    if floor_decision is not None:
        if floor_trigger == "decision_tree:severity_floor":
            reason = severity_reason
        elif floor_trigger == "decision_tree:policy_floor":
            reason = policy_reason
        elif floor_trigger == "decision_tree:confidence_floor":
            reason = confidence_reason
        elif floor_trigger == "decision_tree:data_sensitivity_floor":
            reason = data_sensitivity_reason
        else:
            reason = "A decision floor was triggered."
        return RiskEngineResult(
            decision=floor_decision,
            trigger=floor_trigger or "decision_tree:floor",
            reason=reason,
            factor_scores=factor_scores,
            session_data=session_data,
            regulatory_tier=regulatory_tier,
            us_regime_flags=us_regime_flags,
        )

    weighted_score = compute_weighted_score(factor_scores, config)
    decision = apply_weighted_decision(weighted_score, config)

    trigger = f"weighted_score:{decision.value}:{weighted_score:.1f}"

    top_factor = max(
        (("severity", severity), ("policy", policy), ("anomaly", anomaly),
         ("data_sensitivity", data_sensitivity), ("confidence", 100 - confidence),
         ("tool_trust", 100 - tool_trust)),
        key=lambda item: item[1],
    )
    reason = (
        f"Blended risk score {weighted_score:.0f} from the weighted factors; "
        f"the top driver is {top_factor[0]}."
    )

    return RiskEngineResult(
        decision=decision,
        trigger=trigger,
        reason=reason,
        factor_scores=factor_scores,
        session_data=session_data,
        regulatory_tier=regulatory_tier,
        us_regime_flags=us_regime_flags,
    )

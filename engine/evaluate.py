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
    session_threshold = ctx.get("session_threshold", 70)

    sequences_config = config.get("sequences_config", DEFAULT_SEQUENCES)

    severity = score_severity(action_type, parameters, config)
    policy = score_policy(action_type, parameters, config)
    anomaly = score_anomaly(action_type, parameters, config, history)
    data_sensitivity = score_data_sensitivity(action_type, parameters, config)
    confidence = score_confidence(action_type, parameters, config, history)
    tool_trust = score_tool_trust(action_type, parameters, config)

    factor_scores = FactorScores(
        severity=severity,
        policy=policy,
        anomaly=anomaly,
        data_sensitivity=data_sensitivity,
        confidence=confidence,
        tool_trust=tool_trust,
    )

    session_info = score_session(history, action_type, sequences_config, threshold=session_threshold)
    session_data = SessionData(
        session_id=ctx.get("session_id"),
        cumulative_severity=session_info["cumulative_severity"],
        pattern_matched=session_info["pattern_matched"],
    )

    session_decision, session_trigger = apply_session_branches(session_info, config)
    if session_decision is not None:
        return RiskEngineResult(
            decision=session_decision,
            trigger=session_trigger or "session:escalated",
            factor_scores=factor_scores,
            session_data=session_data,
        )

    floor_decision, floor_trigger = apply_decision_tree(factor_scores, config)

    if floor_decision is not None:
        return RiskEngineResult(
            decision=floor_decision,
            trigger=floor_trigger or "decision_tree:floor",
            factor_scores=factor_scores,
            session_data=session_data,
        )

    weighted_score = compute_weighted_score(factor_scores, config)
    decision = apply_weighted_decision(weighted_score, config)

    trigger = f"weighted_score:{decision.value}:{weighted_score:.1f}"

    return RiskEngineResult(
        decision=decision,
        trigger=trigger,
        factor_scores=factor_scores,
        session_data=session_data,
    )

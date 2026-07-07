from typing import Any

from engine.models import FactorScores


def map_regulatory_tier(
    action_type: str,
    factor_scores: FactorScores,
    config: dict[str, Any],
) -> str:
    mapping = config.get("regulatory_mapping", {})
    if not mapping:
        return "minimal_risk"

    prohibited = mapping.get("article_5_prohibited_practices", [])
    if action_type in prohibited:
        return "unacceptable_risk"

    high_risk_actions = mapping.get("high_risk_action_types", [])
    limited_risk_actions = mapping.get("limited_risk_action_types", [])

    hr_config = mapping.get("high_risk", {})
    min_severity_for_unknown = hr_config.get("min_severity_for_unknown_tool", 70)
    min_data_sensitivity = hr_config.get("min_data_sensitivity", 90)

    if action_type in high_risk_actions:
        return "high_risk"

    if factor_scores.tool_trust <= 40 and factor_scores.severity >= min_severity_for_unknown:
        return "high_risk"

    if factor_scores.data_sensitivity >= min_data_sensitivity:
        return "high_risk"

    if action_type in limited_risk_actions:
        return "limited_risk"

    return "minimal_risk"


def map_us_regime_flags(
    action_type: str,
    config: dict[str, Any],
) -> list[str]:
    mapping = config.get("regulatory_mapping", {})
    if not mapping:
        return []

    financial_actions = mapping.get("us_financial_action_types", [])

    flags: list[str] = []
    if action_type in financial_actions:
        flags.append("FINRA")
        flags.append("SEC")

    return flags

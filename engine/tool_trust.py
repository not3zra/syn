TOOL_TRUST_SCORES = {
    "official": 100.0,
    "verified": 80.0,
    "unknown": 40.0,
    "unsigned": 10.0,
}


def score_tool_trust(action_type: str, parameters: dict, config: dict) -> float:
    tool_config = config.get("tools", {}).get(action_type)
    if not tool_config:
        return TOOL_TRUST_SCORES["unknown"]

    tier = tool_config.get("tool_trust_tier", "unknown")
    return TOOL_TRUST_SCORES.get(tier, TOOL_TRUST_SCORES["unknown"])

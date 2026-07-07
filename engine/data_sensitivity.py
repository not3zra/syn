import re


def score_data_sensitivity(action_type: str, parameters: dict, config: dict) -> float:
    tool_config = config.get("tools", {}).get(action_type)
    if not tool_config:
        return 30.0

    rules = tool_config.get("data_sensitivity_rules", [])
    max_score = 0.0

    for rule in rules:
        field = rule.get("field")
        pattern = rule.get("pattern")
        param_value = parameters.get(field)

        if param_value is None or not isinstance(param_value, str):
            continue

        if re.search(pattern, param_value, re.IGNORECASE):
            max_score = max(max_score, float(rule["score"]))

    return max_score

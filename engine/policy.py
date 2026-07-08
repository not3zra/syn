import re


def score_policy(action_type: str, parameters: dict, config: dict) -> float:
    tool_config = config.get("tools", {}).get(action_type)
    if not tool_config:
        return 0.0

    policy_rules = tool_config.get("policy_rules", [])
    if not policy_rules:
        return 0.0

    max_score = 0.0
    for rule in policy_rules:
        condition = rule.get("condition", {})
        field = condition.get("field")
        operator = condition.get("operator")
        value = condition.get("value")

        param_value = parameters.get(field)
        if param_value is None:
            continue

        matched = False
        if operator in (">", "gt"):
            try:
                matched = float(param_value) > float(value)
            except (ValueError, TypeError):
                matched = False
        elif operator in ("<", "lt"):
            try:
                matched = float(param_value) < float(value)
            except (ValueError, TypeError):
                matched = False
        elif operator in (">=", "gte"):
            try:
                matched = float(param_value) >= float(value)
            except (ValueError, TypeError):
                matched = False
        elif operator in ("<=", "lte"):
            try:
                matched = float(param_value) <= float(value)
            except (ValueError, TypeError):
                matched = False
        elif operator == "==":
            matched = param_value == value
        elif operator in ("!=", "neq"):
            matched = param_value != value
        elif operator == "in":
            if isinstance(value, list):
                matched = param_value in value
            else:
                matched = param_value == value
        elif operator == "not_in":
            if isinstance(value, list):
                matched = param_value not in value
            else:
                matched = param_value != value
        elif operator == "matches":
            if isinstance(param_value, str) and isinstance(value, str):
                matched = bool(re.search(value, param_value, re.IGNORECASE))

        if matched:
            max_score = max(max_score, float(rule["score"]))

    return max_score

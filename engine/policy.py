import re


def score_policy(action_type: str, parameters: dict, config: dict) -> tuple[float, str]:
    tool_config = config.get("tools", {}).get(action_type)
    if not tool_config:
        return 0.0, "No policy rules are registered for this tool."

    policy_rules = tool_config.get("policy_rules", [])
    if not policy_rules:
        return 0.0, "No policy rules are registered for this tool."

    max_score = 0.0
    matched_reasons = []
    for rule in policy_rules:
        condition = rule.get("condition", {})
        field = condition.get("field")
        operator = condition.get("operator")
        value = condition.get("value")

        param_value = parameters.get(field)
        if param_value is None:
            continue

        matched = False
        reason = ""
        if operator in (">", "gt"):
            try:
                matched = float(param_value) > float(value)
            except (ValueError, TypeError):
                matched = False
            reason = f"{field} {param_value} exceeds the allowed limit ({value})."
        elif operator in ("<", "lt"):
            try:
                matched = float(param_value) < float(value)
            except (ValueError, TypeError):
                matched = False
            reason = f"{field} {param_value} is below the allowed minimum ({value})."
        elif operator in (">=", "gte"):
            try:
                matched = float(param_value) >= float(value)
            except (ValueError, TypeError):
                matched = False
            reason = f"{field} {param_value} meets or exceeds the threshold ({value})."
        elif operator in ("<=", "lte"):
            try:
                matched = float(param_value) <= float(value)
            except (ValueError, TypeError):
                matched = False
            reason = f"{field} {param_value} is within the allowed limit ({value})."
        elif operator == "==":
            matched = param_value == value
            reason = f"{field} equals {value}."
        elif operator in ("!=", "neq"):
            matched = param_value != value
            reason = f"{field} is {param_value} (must not be {value})."
        elif operator == "in":
            if isinstance(value, list):
                matched = param_value in value
            else:
                matched = param_value == value
            reason = f"{field} is in the disallowed set {value}."
        elif operator == "not_in":
            if isinstance(value, list):
                matched = param_value not in value
            else:
                matched = param_value != value
            reason = f"{field} is not in the allowed set {value}."
        elif operator == "matches":
            if isinstance(param_value, str) and isinstance(value, str):
                matched = bool(re.search(value, param_value, re.IGNORECASE))
            reason = f"{field} matches the forbidden pattern '{value}'."

        if matched:
            max_score = max(max_score, float(rule["score"]))
            matched_reasons.append(reason)

    if max_score == 0.0:
        return 0.0, "No policy rules were violated."

    return max_score, "Policy violation: " + " ".join(matched_reasons)

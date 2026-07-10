import re


def score_data_sensitivity(action_type: str, parameters: dict, config: dict) -> tuple[float, str]:
    tool_config = config.get("tools", {}).get(action_type)
    if not tool_config:
        return 30.0, "No data-sensitivity profile is registered for this tool."

    rules = tool_config.get("data_sensitivity_rules", [])
    max_score = 0.0
    matched_fields = []

    for rule in rules:
        field = rule.get("field")
        pattern = rule.get("pattern")
        param_value = parameters.get(field)

        if param_value is None or not isinstance(param_value, str):
            continue

        if re.search(pattern, param_value, re.IGNORECASE):
            score = float(rule["score"])
            max_score = max(max_score, score)
            matched_fields.append(f"{field}='{param_value}' (pattern '{pattern}')")

    if max_score == 0.0:
        return 0.0, "No sensitive-data fields (PII or regulated data) detected in the request."

    return max_score, "Sensitive data matched: " + "; ".join(matched_fields) + "."

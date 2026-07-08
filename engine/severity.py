def _match_max_amount_rule(rule: dict, amount: float) -> float | None:
    max_amt = rule.get("max_amount")
    if max_amt is None or amount <= max_amt:
        return float(rule["score"])
    return None


def _match_path_pattern_rule(rule: dict, param_value: str) -> float | None:
    pattern = rule.get("path_pattern", "")
    import re
    if re.search(pattern, param_value):
        return float(rule["score"])
    return None


def _generic_severity(rules: list[dict], parameters: dict) -> float:
    amount = parameters.get("amount")
    for rule in rules:
        if "max_amount" in rule and amount is not None:
            score = _match_max_amount_rule(rule, float(amount))
            if score is not None:
                return score
        if "path_pattern" in rule:
            for val in parameters.values():
                if isinstance(val, str):
                    score = _match_path_pattern_rule(rule, val)
                    if score is not None:
                        return score
    catch_all = next((r for r in rules if "max_amount" in r and r["max_amount"] is None), None)
    if catch_all:
        return float(catch_all["score"])
    return 50.0


def score_severity(action_type: str, parameters: dict, config: dict) -> float:
    tool_config = config.get("tools", {}).get(action_type)
    if not tool_config:
        return 50.0

    rules = tool_config.get("severity_rules", [])

    if action_type == "send_payment":
        amount = parameters.get("amount", 0)
        for rule in rules:
            max_amt = rule.get("max_amount")
            if max_amt is None:
                return float(rule["score"])
            if amount <= max_amt:
                return float(rule["score"])
        return float(rules[-1]["score"])

    if action_type == "delete_file":
        file_path = parameters.get("file_path", "")
        for rule in rules:
            pattern = rule.get("path_pattern", "")
            import re
            if re.search(pattern, file_path):
                return float(rule["score"])
        return 50.0

    if action_type == "query_database":
        query = parameters.get("query", "")
        query_upper = query.strip().upper()
        if query_upper.startswith(("DROP", "ALTER", "TRUNCATE", "CREATE")):
            return 90.0
        if query_upper.startswith(("INSERT", "UPDATE", "DELETE")):
            return 40.0
        if query_upper.startswith("SELECT"):
            return 10.0
        return 30.0

    if action_type == "check_balance":
        return 15.0

    return _generic_severity(rules, parameters)

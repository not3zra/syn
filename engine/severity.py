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

    return 50.0

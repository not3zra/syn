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


def _generic_severity(rules: list[dict], parameters: dict) -> tuple[float, str]:
    amount_raw = parameters.get("amount")
    try:
        amount = float(amount_raw) if amount_raw is not None else None
    except (TypeError, ValueError):
        amount = None
    for rule in rules:
        if "max_amount" in rule and amount is not None:
            score = _match_max_amount_rule(rule, float(amount))
            if score is not None:
                return score, f"Parameter value {amount:g} matched a severity rule."
        if "path_pattern" in rule:
            for val in parameters.values():
                if isinstance(val, str):
                    score = _match_path_pattern_rule(rule, val)
                    if score is not None:
                        return (
                            score,
                            f"Parameter value '{val}' matched a path severity rule.",
                        )
    catch_all = next((r for r in rules if "max_amount" in r and r["max_amount"] is None), None)
    if catch_all:
        return float(catch_all["score"]), "Matched the catch-all severity rule."
    return 50.0, "No severity rule matched; defaulting to moderate risk."


def score_severity(action_type: str, parameters: dict, config: dict) -> tuple[float, str]:
    tool_config = config.get("tools", {}).get(action_type)
    if not tool_config:
        return 50.0, "No severity profile is registered for this tool; treated as moderate risk."

    rules = tool_config.get("severity_rules", [])

    if action_type == "send_payment":
        amount_raw = parameters.get("amount")
        try:
            amount = float(amount_raw) if amount_raw is not None else None
        except (TypeError, ValueError):
            amount = None
        # A payment with a missing, non-numeric, or non-positive amount
        # is invalid and must never be auto-approved.
        if amount is None or amount <= 0:
            return (
                95.0,
                f"Payment has a missing or non-positive amount ({amount_raw!r}); "
                "a valid positive amount is required before it can be approved.",
            )
        for rule in rules:
            max_amt = rule.get("max_amount")
            if max_amt is None:
                return (
                    float(rule["score"]),
                    f"Payment amount {amount:g} exceeds every low-risk threshold.",
                )
            if amount <= max_amt:
                return (
                    float(rule["score"]),
                    f"Payment amount {amount:g} is within the low-risk band (up to {max_amt:g}).",
                )
        return float(rules[-1]["score"]), f"Payment amount {amount:g} is in the highest severity band."

    if action_type == "delete_file":
        file_path = parameters.get("file_path", "")
        for rule in rules:
            pattern = rule.get("path_pattern", "")
            import re
            if re.search(pattern, file_path):
                return (
                    float(rule["score"]),
                    f"File path '{file_path}' matches a protected-path pattern ('{pattern}').",
                )
        return 50.0, f"File path '{file_path}' is outside any protected path."

    if action_type == "query_database":
        query = parameters.get("query", "")
        query_upper = query.strip().upper()
        if query_upper.startswith(("DROP", "ALTER", "TRUNCATE", "CREATE")):
            return (
                90.0,
                "Query issues a destructive DDL statement (DROP/ALTER/TRUNCATE/CREATE) that can "
                "alter or destroy data.",
            )
        if query_upper.startswith(("INSERT", "UPDATE", "DELETE")):
            return 40.0, "Query mutates data (INSERT/UPDATE/DELETE)."
        if query_upper.startswith("SELECT"):
            return 10.0, "Query is a read-only SELECT."
        return 30.0, "Query is not a recognized read or write statement."

    if action_type == "check_balance":
        return 15.0, "Read-only balance check."

    return _generic_severity(rules, parameters)

def score_confidence(
    action_type: str, parameters: dict, config: dict, history: list | None = None
) -> float:
    if not history:
        return 20.0

    relevant = [h for h in history if h.get("action_type") == action_type]
    if len(relevant) < 2:
        return 30.0

    if len(relevant) < 5:
        return 50.0

    if len(relevant) < 10:
        return 70.0

    return 90.0

def score_confidence(
    action_type: str, parameters: dict, config: dict, history: list | None = None
) -> tuple[float, str]:
    if not history:
        return 50.0, "No prior activity recorded for this agent; trust starts neutral."

    relevant = [h for h in history if h.get("action_type") == action_type]
    count = len(relevant)
    if count < 1:
        return (
            30.0,
            f"The agent has never run '{action_type}' before; trust is at a low baseline.",
        )

    if count < 5:
        return (
            50.0,
            f"The agent has run '{action_type}' {count} time(s); trust is still building.",
        )

    if count < 10:
        return (
            70.0,
            f"The agent has run '{action_type}' {count} times; trust is moderately established.",
        )

    return 90.0, f"The agent has run '{action_type}' {count} times; trust is well established."

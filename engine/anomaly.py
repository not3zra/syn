def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def score_anomaly(
    action_type: str, parameters: dict, config: dict, history: list | None = None
) -> float:
    if not history:
        return 0.0

    if len(history) < 3:
        return 5.0

    amounts = [
        v
        for h in history
        if h.get("action_type") == action_type
        for v in [_to_float(h.get("parameters", {}).get("amount"))]
        if v is not None
    ]
    if len(amounts) < 2:
        return 5.0

    current = _to_float(parameters.get("amount"))
    if current is None:
        return 5.0

    mean = sum(amounts) / len(amounts)
    if mean == 0:
        return 5.0

    variance = sum((x - mean) ** 2 for x in amounts) / len(amounts)
    std_dev = variance ** 0.5

    if std_dev == 0:
        return 0.0 if abs(current - mean) / mean < 0.5 else 50.0

    z_score = abs(current - mean) / std_dev

    if z_score > 3.0:
        return 80.0
    if z_score > 2.0:
        return 50.0
    if z_score > 1.5:
        return 20.0

    return 5.0

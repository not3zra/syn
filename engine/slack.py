from typing import Any

import httpx


class SlackNotifier:
    def __init__(self, webhook_url: str | None = None):
        self._webhook_url = webhook_url

    def send_escalation(self, entry: dict[str, Any]) -> bool:
        if not self._webhook_url:
            return False

        action_type = entry.get("action_type", "unknown")
        decision = entry.get("decision", "unknown")
        trigger = entry.get("trigger", "unknown")

        risk_score: str | float = entry.get("factor_scores", {}).get("severity", 0)
        if trigger.startswith("session:cumulative_threshold"):
            risk_score = entry.get("session_data", {}).get("cumulative_severity", 0)
        elif trigger.startswith("session:pattern_matched"):
            risk_score = entry.get("session_data", {}).get("cumulative_severity", 0)
        elif trigger.startswith("decision_tree:confidence_floor"):
            risk_score = entry.get("factor_scores", {}).get("confidence", 0)
        elif trigger.startswith("weighted_score:"):
            parts = trigger.split(":")
            if len(parts) >= 3:
                try:
                    risk_score = float(parts[-1])
                except (ValueError, TypeError):
                    pass

        label = "Risk Score"
        if trigger.startswith("session:"):
            label = "Cumulative Risk"
        elif trigger.startswith("weighted_score:"):
            label = "Weighted Score"
        elif trigger.startswith("decision_tree:"):
            label = "Driving Factor"

        explanation = entry.get("explanation", "No explanation available")
        timestamp = entry.get("timestamp", "")

        message = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🚨 Escalated Action: {action_type}",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Decision:*\n{decision}"},
                        {"type": "mrkdwn", "text": f"*Trigger:*\n{trigger}"},
                        {"type": "mrkdwn", "text": f"*{label}:*\n{risk_score}"},
                        {"type": "mrkdwn", "text": f"*Timestamp:*\n{timestamp}"},
                    ],
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Explanation:*\n{explanation}"},
                },
            ]
        }

        try:
            resp = httpx.post(self._webhook_url, json=message, timeout=10)
            return resp.is_success
        except Exception:
            return False

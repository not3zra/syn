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
        risk_score = entry.get("factor_scores", {}).get("severity", 0)
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
                        {"type": "mrkdwn", "text": f"*Risk Score:*\n{risk_score}"},
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

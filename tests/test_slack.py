from engine.slack import SlackNotifier


class TestSlackNotifier:
    def test_noop_without_webhook(self):
        slack = SlackNotifier()
        result = slack.send_escalation({"action_type": "send_payment", "decision": "escalated"})
        assert result is False

    def test_returns_false_on_bad_url(self):
        slack = SlackNotifier(webhook_url="https://invalid.webhook.example/notfound")
        result = slack.send_escalation({"action_type": "send_payment", "decision": "escalated"})
        assert result is False

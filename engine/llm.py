from abc import ABC, abstractmethod
from typing import Any


class LLMClient(ABC):
    @abstractmethod
    def generate(
        self,
        prompt: str,
        output_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...


def _get_mock_explanation(action_type: str, decision: str, trigger: str) -> str:
    explanations = {
        "severity_floor": (
            f"The {action_type} action was blocked because its severity score exceeded the "
            f"maximum threshold. This action carries inherent risk that cannot be mitigated."
        ),
        "policy_floor": (
            f"The {action_type} action was blocked because it violates an explicit security policy rule. "
            f"Policy violations are automatically denied regardless of other risk factors."
        ),
        "confidence_floor": (
            f"The {action_type} action was escalated for human review because the system has "
            f"insufficient historical data to assess this action with confidence. "
            f"More data is needed before automated decisions can be made."
        ),
        "pattern_matched": (
            f"The {action_type} action was escalated because it matches a known risky sequence pattern. "
            f"This pair of actions in sequence has been flagged as potentially harmful."
        ),
        "cumulative_threshold": (
            f"The {action_type} action was escalated because the cumulative risk across all "
            f"actions in this session has exceeded the safety threshold. "
            f"Multiple medium-risk actions together warrant human review."
        ),
    }

    base = f"The {action_type} action was {decision}."
    for key, text in explanations.items():
        if key in trigger:
            return text
    return (
        f"The {action_type} action was {decision} based on the combined assessment of all "
        f"six risk factors. {base.capitalize()} after the weighted risk score evaluation."
    )


class MockLLMClient(LLMClient):
    def __init__(self) -> None:
        self._call_count = 0

    def generate(
        self,
        prompt: str,
        output_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._call_count += 1

        if output_schema and output_schema.get("type") == "bootstrap_rules":
            return self._mock_bootstrap_rules(prompt)

        action_type = "the action"
        decision = "evaluated"
        trigger = "unknown"

        for line in prompt.split("\n"):
            if "Action type:" in line:
                parts = line.split("Action type:")
                if len(parts) > 1:
                    action_type = parts[1].strip().split(",")[0].strip()
            if "Decision:" in line:
                parts = line.split("Decision:")
                if len(parts) > 1:
                    decision = parts[1].strip().split(",")[0].strip()
            if "Triggered by:" in line:
                parts = line.split("Triggered by:")
                if len(parts) > 1:
                    trigger = parts[1].strip()

        explanation = _get_mock_explanation(action_type, decision, trigger)
        remediation = (
            f"To proceed with this {action_type} action, please request a security review "
            f"or contact your administrator for approval."
        )

        return {
            "explanation": explanation,
            "remediation": remediation,
        }

    def _mock_bootstrap_rules(self, prompt: str) -> dict[str, Any]:
        tool_names = [
            "send_payment", "delete_file", "query_database", "check_balance"
        ]
        tools_with_schemas = []
        for line in prompt.split("\n"):
            if '"tool_name"' in line or "'tool_name'" in line:
                continue
            for name in tool_names:
                if name in line:
                    if name not in tools_with_schemas:
                        tools_with_schemas.append(name)

        rules = []
        for name in tools_with_schemas:
            rule = {
                "tool_name": name,
                "severity_rules": [],
                "policy_rules": [],
                "data_sensitivity_rules": [],
                "tool_trust_tier": "official",
                "anomaly_lookback": 20,
                "reasoning": f"Generated security rules for {name} based on fintech context.",
            }
            if name == "send_payment":
                rule["severity_rules"] = [
                    {"max_amount": 1000, "score": 20},
                    {"max_amount": 5000, "score": 50},
                    {"max_amount": 50000, "score": 80},
                    {"max_amount": None, "score": 95},
                ]
                rule["policy_rules"] = [
                    {
                        "description": "No payments above $5,000 to external recipients without approval",
                        "condition": {"field": "amount", "operator": ">", "value": 5000},
                        "score": 100,
                    }
                ]
                rule["data_sensitivity_rules"] = [
                    {"field": "recipient", "pattern": "external", "score": 40},
                    {"field": "currency", "pattern": ".*", "score": 0},
                ]
            elif name == "delete_file":
                rule["severity_rules"] = [
                    {"path_pattern": "/etc/", "score": 95},
                    {"path_pattern": "/data/prod/", "score": 90},
                    {"path_pattern": ".*", "score": 60},
                ]
                rule["data_sensitivity_rules"] = [
                    {"field": "file_path", "pattern": "(customer|users|accounts)", "score": 80},
                    {"field": "file_path", "pattern": ".*", "score": 10},
                ]
                rule["tool_trust_tier"] = "verified"
                rule["anomaly_lookback"] = 10
            elif name == "query_database":
                rule["severity_rules"] = [
                    {"query_type": "ddl", "score": 90},
                    {"query_type": "dml", "score": 40},
                    {"query_type": "select", "score": 10},
                    {"query_type": None, "score": 30},
                ]
                rule["data_sensitivity_rules"] = [
                    {"field": "query", "pattern": "(DROP|ALTER|TRUNCATE|DELETE|INSERT|UPDATE)", "score": 100},
                    {"field": "query", "pattern": "(users|customers|accounts|pii|ssn)", "score": 70},
                    {"field": "query", "pattern": ".*", "score": 10},
                ]
                rule["policy_rules"] = [
                    {
                        "description": "No destructive DDL operations",
                        "condition": {"field": "query", "operator": "matches", "value": "^(DROP|ALTER|TRUNCATE|DELETE|INSERT|UPDATE)"},
                        "score": 100,
                    }
                ]
            elif name == "check_balance":
                rule["severity_rules"] = [{"max_amount": None, "score": 15}]
                rule["data_sensitivity_rules"] = [
                    {"field": "account_id", "pattern": ".*", "score": 20},
                ]

            rules.append(rule)

        return {"tools": rules}


class FallbackLLMClient(LLMClient):
    def generate(
        self,
        prompt: str,
        output_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "explanation": (
                "This action was evaluated by the deterministic governance engine. "
                "An AI-powered explanation is not available with the current configuration."
            ),
            "remediation": (
                "Contact your system administrator for assistance with this action."
            ),
        }


def create_llm_client(config: dict[str, Any]) -> LLMClient:
    provider = config.get("provider", "mock")

    if provider == "mock":
        return MockLLMClient()
    if provider == "fallback":
        return FallbackLLMClient()

    raise ValueError(f"Unknown LLM provider: {provider}")


def build_explanation_prompt(
    action_type: str,
    decision: str,
    trigger: str,
    factor_scores: dict[str, float],
) -> str:
    scores_str = ", ".join(f"{k}: {v}" for k, v in factor_scores.items())
    return (
        f"You are explaining a security decision made by a deterministic AI governance system.\n"
        f"Context: Action type: {action_type}, Decision: {decision}, Triggered by: {trigger}\n"
        f"Factor scores (context only): {scores_str}\n"
        f"Explain in 2 sentences why the decision was made, focused on the trigger: \"{trigger}\".\n"
        f"Do not infer other reasons."
    )

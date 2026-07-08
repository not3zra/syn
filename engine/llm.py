import json
import os
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


def _format_pair(trigger: str) -> str:
    parts = trigger.split(":")
    if len(parts) >= 3:
        raw = parts[2]
        segs = raw.split("_")
        if len(segs) == 4:
            return f"{segs[0]}_{segs[1]} followed by {segs[2]}_{segs[3]}"
    return ""


def _get_mock_explanation(action_type: str, decision: str, trigger: str, top_factor: str | None = None) -> str:
    if "pattern_matched" in trigger:
        pair_str = _format_pair(trigger)
        if pair_str:
            return (
                f"The {action_type} action was escalated because it matches a known "
                f"risky sequence pattern: {pair_str}. "
                f"This pair of actions in sequence has been flagged as potentially harmful."
            )
        return (
            f"The {action_type} action was escalated because it matches a known risky sequence pattern. "
            f"This pair of actions in sequence has been flagged as potentially harmful."
        )

    if "cumulative_threshold" in trigger:
        return (
            f"The {action_type} action was escalated because the cumulative risk across all "
            f"actions in this session has exceeded the safety threshold. "
            f"Multiple medium-risk actions together warrant human review."
        )

    if "severity_floor" in trigger:
        return (
            f"The {action_type} action was blocked because its severity score exceeded the "
            f"maximum threshold. This action carries inherent risk that cannot be mitigated."
        )

    if "policy_floor" in trigger:
        return (
            f"The {action_type} action was blocked because it violates an explicit security policy rule. "
            f"Policy violations are automatically denied regardless of other risk factors."
        )

    if "confidence_floor" in trigger:
        return (
            f"The {action_type} action was escalated for human review because the system has "
            f"insufficient historical data to assess this action with confidence. "
            f"More data is needed before automated decisions can be made."
        )

    base = f"The {action_type} action was {decision}."
    if top_factor:
        return (
            f"The {action_type} action was {decision} based on the combined assessment of all "
            f"six risk factors. The most significant contributing factor was {top_factor}, "
            f"which notably influenced the weighted risk score evaluation."
        )
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

        top_factor = None
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
            if "The most significant contributing factor is " in line:
                top_factor = line.split("The most significant contributing factor is ")[1].strip().rstrip(".")

        explanation = _get_mock_explanation(action_type, decision, trigger, top_factor=top_factor)
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
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.groq.com/openai/v1",
        model: str = "llama-3.3-70b-versatile",
    ):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.base_url = base_url
        self.model = model
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return
        if not self.api_key:
            raise ValueError("GROQ_API_KEY or OPENAI_API_KEY is required")
        from openai import OpenAI
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def generate(
        self,
        prompt: str,
        output_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._ensure_client()

        if output_schema and output_schema.get("type") == "bootstrap_rules":
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a security policy generator for an AI governance system. "
                            "Respond with valid JSON containing a 'tools' array. "
                            "Each tool object must have: tool_name, severity_rules, policy_rules, "
                            "data_sensitivity_rules, tool_trust_tier, anomaly_lookback, reasoning. "
                            "Return ONLY valid JSON — no explanation, no markdown."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=800,
            )
            text = response.choices[0].message.content or "{}"
            try:
                result = json.loads(text)
                return {
                    "tools": result.get("tools", []),
                }
            except json.JSONDecodeError:
                return {"tools": []}

        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a security governance assistant. "
                        "Respond with valid JSON using keys 'explanation' and 'remediation'."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=300,
        )
        text = response.choices[0].message.content or "{}"
        try:
            result = json.loads(text)
            return {
                "explanation": result.get("explanation", ""),
                "remediation": result.get("remediation", ""),
            }
        except json.JSONDecodeError:
            return {
                "explanation": text,
                "remediation": "Contact your administrator for assistance.",
            }


class FireworksLLMClient(FallbackLLMClient):
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.fireworks.ai/inference/v1",
        model: str = "accounts/fireworks/models/llama-v3p3-70b-instruct",
    ):
        self.api_key = api_key or os.environ.get("FIREWORKS_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.base_url = base_url
        self.model = model
        self._client = None


def create_llm_client(config: dict[str, Any]) -> LLMClient:
    provider = config.get("provider", "mock")

    if provider == "mock":
        return MockLLMClient()
    if provider in ("fallback", "groq"):
        return FallbackLLMClient(
            api_key=config.get("api_key"),
            base_url=config.get("base_url", "https://api.groq.com/openai/v1"),
            model=config.get("model", "llama-3.3-70b-versatile"),
        )
    if provider == "fireworks":
        return FireworksLLMClient(
            api_key=config.get("api_key"),
            base_url=config.get("base_url", "https://api.fireworks.ai/inference/v1"),
            model=config.get("model", "accounts/fireworks/models/llama-v3p3-70b-instruct"),
        )

    raise ValueError(f"Unknown LLM provider: {provider}")


def build_explanation_prompt(
    action_type: str,
    decision: str,
    trigger: str,
    factor_scores: dict[str, float],
    top_factor: str | None = None,
) -> str:
    scores_str = ", ".join(f"{k}: {v}" for k, v in factor_scores.items())
    prompt = (
        f"You are explaining a security decision made by a deterministic AI governance system.\n"
        f"Context: Action type: {action_type}, Decision: {decision}, Triggered by: {trigger}\n"
        f"Factor scores (context only): {scores_str}\n"
        f"Explain in 2 sentences why the decision was made, focused on the trigger: \"{trigger}\".\n"
    )
    if top_factor:
        prompt += f"The most significant contributing factor is {top_factor}. Mention this factor in your explanation.\n"
    prompt += "Do not infer other reasons."
    return prompt

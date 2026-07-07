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

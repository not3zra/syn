from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, Query
from pydantic import BaseModel

from engine.evaluate import evaluate as risk_evaluate
from engine.llm import create_llm_client, build_explanation_prompt
from engine.audit import AuditStore
from engine.slack import SlackNotifier

REGISTERED_TOOLS: dict[str, dict[str, Any]] = {
    "send_payment": {
        "description": "Send a payment to a recipient",
        "parameters": {
            "amount": {"type": "number", "description": "Payment amount"},
            "currency": {"type": "string", "description": "Currency code"},
            "recipient": {"type": "string", "description": "Recipient identifier"},
        },
    },
    "delete_file": {
        "description": "Delete a file at the specified path",
        "parameters": {
            "file_path": {"type": "string", "description": "Path to the file to delete"},
        },
    },
    "query_database": {
        "description": "Execute a read-only database query",
        "parameters": {
            "query": {"type": "string", "description": "SQL query string"},
        },
    },
}

config_path = Path(__file__).resolve().parent.parent / "engine" / "policy_config.yaml"
POLICY_CONFIG = yaml.safe_load(config_path.read_text())

reg_path = Path(__file__).resolve().parent.parent / "engine" / "regulatory_mapping.yaml"
REG_CONFIG = yaml.safe_load(reg_path.read_text())

FULL_CONFIG = {**POLICY_CONFIG, "regulatory_mapping": REG_CONFIG}

llm_config_path = Path(__file__).resolve().parent.parent / "engine" / "llm_config.yaml"
LLM_CONFIG = yaml.safe_load(llm_config_path.read_text())
LLM_CLIENT = create_llm_client(LLM_CONFIG)

audit_db_path = Path(__file__).resolve().parent.parent / "data" / "audit.db"
audit_db_path.parent.mkdir(parents=True, exist_ok=True)
AUDIT_STORE = AuditStore(str(audit_db_path))

SLACK_WEBHOOK_URL = None
SLACK_NOTIFIER = SlackNotifier(webhook_url=SLACK_WEBHOOK_URL)

app = FastAPI(title="syn-gateway")


class ToolCallRequest(BaseModel):
    action_type: str
    parameters: dict


class DecisionResponse(BaseModel):
    decision: str
    trigger: str
    factor_scores: dict
    session_data: dict
    regulatory_tier: str
    us_regime_flags: list
    action_type: str
    parameters_abstracted: dict
    timestamp: str
    explanation: str | None = None
    remediation: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tools")
def list_tools():
    return [
        {
            "name": name,
            "description": info["description"],
            "parameters": info["parameters"],
        }
        for name, info in REGISTERED_TOOLS.items()
    ]


@app.get("/timeline")
def list_timeline(outcome: str | None = Query(None)):
    return AUDIT_STORE.list_all(outcome=outcome)


@app.post("/intercept")
def intercept(req: ToolCallRequest) -> DecisionResponse:
    known_tools = POLICY_CONFIG.get("tools", {})
    if req.action_type not in known_tools:
        resp = DecisionResponse(
            decision="blocked",
            trigger="gateway:unknown_tool",
            factor_scores={
                "severity": 0,
                "policy": 100,
                "anomaly": 0,
                "data_sensitivity": 0,
                "confidence": 0,
                "tool_trust": 0,
            },
            session_data={
                "session_id": None,
                "cumulative_severity": 0,
                "pattern_matched": False,
            },
            regulatory_tier="minimal_risk",
            us_regime_flags=[],
            action_type=req.action_type,
            parameters_abstracted={},
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        AUDIT_STORE.append(resp.model_dump())
        return resp

    result = risk_evaluate(
        action_type=req.action_type,
        parameters=req.parameters,
        session_context={"history": [], "session_id": None},
        config=FULL_CONFIG,
    )

    prompt = build_explanation_prompt(
        action_type=req.action_type,
        decision=result.decision.value,
        trigger=result.trigger,
        factor_scores=result.factor_scores.to_dict(),
    )
    llm_output = LLM_CLIENT.generate(prompt)

    resp = DecisionResponse(
        decision=result.decision.value,
        trigger=result.trigger,
        factor_scores=result.factor_scores.to_dict(),
        session_data=result.session_data.to_dict(),
        regulatory_tier=result.regulatory_tier,
        us_regime_flags=result.us_regime_flags,
        action_type=req.action_type,
        parameters_abstracted={
            "amount_category": "low",
            "recipient_type": "internal",
        },
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        explanation=llm_output.get("explanation"),
        remediation=llm_output.get("remediation"),
    )

    AUDIT_STORE.append(resp.model_dump())

    if result.decision.value == "escalated":
        SLACK_NOTIFIER.send_escalation(resp.model_dump())

    return resp

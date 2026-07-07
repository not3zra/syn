from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI
from pydantic import BaseModel

from engine.evaluate import evaluate as risk_evaluate
from engine.models import Decision

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


@app.post("/intercept")
def intercept(req: ToolCallRequest) -> DecisionResponse:
    result = risk_evaluate(
        action_type=req.action_type,
        parameters=req.parameters,
        session_context={"history": [], "session_id": None},
        config=POLICY_CONFIG,
    )

    return DecisionResponse(
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
    )

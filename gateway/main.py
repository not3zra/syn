from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

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
    return DecisionResponse(
        decision="approved",
        trigger="hardcoded_fake",
        factor_scores={
            "severity": 0,
            "policy": 0,
            "anomaly": 0,
            "data_sensitivity": 0,
            "confidence": 100,
            "tool_trust": 100,
        },
        session_data={
            "session_id": None,
            "cumulative_severity": 0,
            "pattern_matched": False,
        },
        regulatory_tier="minimal_risk",
        us_regime_flags=[],
        action_type=req.action_type,
        parameters_abstracted={
            "amount_category": "low",
            "recipient_type": "internal",
        },
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )

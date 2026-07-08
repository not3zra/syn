import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from pydantic import BaseModel

load_dotenv()

from engine.evaluate import evaluate as risk_evaluate
from engine.execution import execute_tool
from engine.llm import create_llm_client, build_explanation_prompt
from engine.audit import AuditStore
from engine.slack import SlackNotifier
from engine.session import generate_session_id
from engine.bootstrap import (
    introspect_tools,
    generate_rules,
    rules_to_yaml,
    validate_generated_yaml,
    write_policy_config,
)

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

bootstrap_config_path = Path(__file__).resolve().parent.parent / "engine" / "policy_config.bootstrap.yaml"
_bootstrap_config: dict | None = None
_bootstrap_mtime: float = 0


def _get_merged_tools() -> dict:
    global _bootstrap_config, _bootstrap_mtime
    base = POLICY_CONFIG.get("tools", {})

    try:
        mtime = bootstrap_config_path.stat().st_mtime
        if mtime != _bootstrap_mtime:
            _bootstrap_config = yaml.safe_load(bootstrap_config_path.read_text())
            _bootstrap_mtime = mtime
    except (FileNotFoundError, OSError):
        _bootstrap_config = None

    if _bootstrap_config:
        return {**base, **(_bootstrap_config.get("tools", {}))}
    return base

audit_db_path_env = os.environ.get("SYN_AUDIT_DB_PATH")
if audit_db_path_env:
    audit_db_path = Path(audit_db_path_env)
else:
    audit_db_path = Path(__file__).resolve().parent.parent / "data" / "audit.db"
audit_db_path.parent.mkdir(parents=True, exist_ok=True)
AUDIT_STORE = AuditStore(str(audit_db_path))

SLACK_WEBHOOK_URL = os.environ.get("SYN_SLACK_WEBHOOK_URL")
SLACK_NOTIFIER = SlackNotifier(webhook_url=SLACK_WEBHOOK_URL)

app = FastAPI(title="syn-gateway")


class ToolCallRequest(BaseModel):
    action_type: str
    parameters: dict
    agent_id: str = "default"
    mode: str = "live"


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
    execution: dict | None = None
    explanation: str | None = None
    remediation: str | None = None
    simulation: bool = False
    rollback_plan: str | None = None
    expires_at: str | None = None


class BootstrapIntrospectRequest(BaseModel):
    api_base: str | None = None
    manual_schemas: list[dict] | None = None


class BootstrapApproveRequest(BaseModel):
    yaml_content: str
    target_path: str | None = None


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


@ app.post("/bootstrap/introspect")
def bootstrap_introspect(req: BootstrapIntrospectRequest):
    try:
        schemas = req.manual_schemas or introspect_tools(api_base=req.api_base)
        rules = generate_rules(LLM_CLIENT, schemas)
        yaml_str = rules_to_yaml(rules)
        errors = validate_generated_yaml(yaml_str)
        return {
            "schemas": schemas,
            "rules": rules,
            "yaml": yaml_str,
            "valid": len(errors) == 0,
            "errors": errors,
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/bootstrap/approve")
def bootstrap_approve(req: BootstrapApproveRequest):
    errors = validate_generated_yaml(req.yaml_content)
    if errors:
        return {"success": False, "errors": errors}
    target = Path(req.target_path) if req.target_path else config_path.with_suffix(".bootstrap.yaml")
    write_policy_config(req.yaml_content, target)
    return {"success": True, "path": str(target)}


class ResolveRequest(BaseModel):
    outcome: str  # "approved" or "denied"


@app.post("/resolve/{entry_id}")
def resolve_escalation(entry_id: int, req: ResolveRequest):
    AUDIT_STORE.mark_resolved(entry_id)
    result = {"success": True, "execution": None}
    if req.outcome == "approved":
        entry_data = AUDIT_STORE.list_all(outcome="escalated", limit=100)
        action_type = None
        params = None
        for e in entry_data:
            if e.get("id") == entry_id:
                action_type = e.get("action_type")
                params = e.get("parameters")
                break
        if action_type:
            result["execution"] = execute_tool(action_type or "unknown", params or {})
    return result


@app.get("/timeline")
def list_timeline(outcome: str | None = Query(None)):
    return AUDIT_STORE.list_all(outcome=outcome)


@app.post("/intercept")
def intercept(req: ToolCallRequest) -> DecisionResponse:
    AUDIT_STORE.expire_old()
    session_id = generate_session_id(req.agent_id, int(time.time()))
    is_simulation = req.mode == "simulation"
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    merged_tools = _get_merged_tools()
    if req.action_type not in merged_tools:
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
                "session_id": session_id,
                "cumulative_severity": 0,
                "pattern_matched": False,
            },
            regulatory_tier="minimal_risk",
            us_regime_flags=[],
            action_type=req.action_type,
            parameters_abstracted={},
            timestamp=now_iso,
            simulation=is_simulation,
        )
        if not is_simulation:
            AUDIT_STORE.append(resp.model_dump(), session_id=session_id)
        return resp

    eval_config = {**FULL_CONFIG, "tools": merged_tools}
    session_history = AUDIT_STORE.get_session_history(session_id)
    result = risk_evaluate(
        action_type=req.action_type,
        parameters=req.parameters,
        session_context={"history": session_history, "session_id": session_id},
        config=eval_config,
    )

    top_factor: str | None = None
    if result.trigger.startswith("weighted_score:"):
        weights = POLICY_CONFIG.get("weights", {})
        raw = result.factor_scores.to_dict()
        contributions: dict[str, float] = {}
        for factor, w in [
            ("severity", weights.get("severity", 0.30)),
            ("policy", weights.get("policy", 0.20)),
            ("anomaly", weights.get("anomaly", 0.10)),
            ("data_sensitivity", weights.get("data_sensitivity", 0.15)),
            ("confidence", weights.get("confidence", 0.05)),
            ("tool_trust", weights.get("tool_trust", 0.20)),
        ]:
            if factor in ("confidence", "tool_trust"):
                contributions[factor] = (100 - raw.get(factor, 0)) * w
            else:
                contributions[factor] = raw.get(factor, 0) * w
        top_factor = max(contributions, key=contributions.get)

    prompt = build_explanation_prompt(
        action_type=req.action_type,
        decision=result.decision.value,
        trigger=result.trigger,
        factor_scores=result.factor_scores.to_dict(),
        top_factor=top_factor,
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
        timestamp=now_iso,
        explanation=llm_output.get("explanation"),
        remediation=llm_output.get("remediation"),
        simulation=is_simulation,
    )

    if not is_simulation:
        if result.decision.value == "approved":
            resp.execution = execute_tool(req.action_type, req.parameters)

        if result.decision.value == "escalated":
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat().replace("+00:00", "Z")
            resp.rollback_plan = "If denied, the action will not be executed."
            resp.expires_at = expires_at

        entry = resp.model_dump()
        entry["parameters"] = req.parameters
        AUDIT_STORE.append(entry, session_id=session_id)

        if result.decision.value == "escalated":
            SLACK_NOTIFIER.send_escalation(resp.model_dump())

    return resp

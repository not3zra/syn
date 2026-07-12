import asyncio
import hmac
import json
import logging
import os
import time
import uuid
from collections import defaultdict, deque
from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_var.get() or "-"
        return True


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(request_id)s] %(name)s %(levelname)s: %(message)s",
)
for handler in logging.root.handlers:
    handler.addFilter(_RequestIdFilter())

load_dotenv()

from engine.evaluate import evaluate as risk_evaluate
from engine.execution import execute_tool
from engine.llm import LLMStatus, create_llm_client, build_explanation_prompt
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
    "check_balance": {
        "description": "Check account balance",
        "parameters": {
            "account_id": {"type": "string", "description": "Account identifier"},
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

domain_config_path = Path(__file__).resolve().parent.parent / "engine" / "domain_config.yaml"
DOMAIN_CONFIG = yaml.safe_load(domain_config_path.read_text()) if domain_config_path.exists() else {}

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

# ---------------------------------------------------------------------------
# Demo-token tripwire (NOT real auth).
#
# This gate exists purely as an anti-footgun for the public demo: it stops a
# casual visitor from mutating the shared demo state (approving tools,
# resolving escalations, etc.) without the baked-in token. The token is
# inlined into the public client bundle (see frontend wiring, #36) and is
# therefore fully extractable by anyone who opens DevTools. Do NOT treat this
# as authentication or authorization. Real auth is tracked separately (#19).
#
# When DEMO_TOKEN is unset the check is a no-op, so local dev, curl,
# test_workflow.sh, and the pytest suite keep working unchanged.
# ---------------------------------------------------------------------------

_DEMO_TOKEN_ENV = "DEMO_TOKEN"
_FLY_APP_NAME_ENV = "FLY_APP_NAME"
_DEMO_TOKEN_HEADER = "X-Demo-Token"


def _expected_demo_token() -> str | None:
    token = os.environ.get(_DEMO_TOKEN_ENV)
    return token if token else None


def require_demo_token(request: Request) -> None:
    """FastAPI dependency that gates a mutating endpoint behind X-Demo-Token.

    No-op when DEMO_TOKEN is unset. Reused by the admin reset endpoint (#35).
    """
    expected = _expected_demo_token()
    if expected is None:
        return
    provided = request.headers.get(_DEMO_TOKEN_HEADER)
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid X-Demo-Token",
            headers={"WWW-Authenticate": _DEMO_TOKEN_HEADER},
        )


def assert_demo_token_configured_for_production() -> None:
    """Fail loud in production when the tripwire token is missing.

    On Fly (FLY_APP_NAME set) shipping without DEMO_TOKEN means the demo is
    open to anyone — refuse to start rather than deploy insecurely.
    """
    if os.environ.get(_FLY_APP_NAME_ENV) and _expected_demo_token() is None:
        raise RuntimeError(
            "DEMO_TOKEN must be set when running on Fly (FLY_APP_NAME is set). "
            "Refusing to start: the demo-token tripwire would be a no-op and the "
            "public demo would be unprotected."
        )


_last_llm_status: LLMStatus | None = None


@asynccontextmanager
async def _lifespan(app: FastAPI):
    global _last_llm_status
    assert_demo_token_configured_for_production()
    loop = asyncio.get_event_loop()
    _last_llm_status = await loop.run_in_executor(_THREAD_POOL, LLM_CLIENT.check_connection)
    yield


app = FastAPI(title="syn-gateway", lifespan=_lifespan)

_THREAD_POOL = ThreadPoolExecutor(max_workers=4)

_RATE_LIMIT = int(os.environ.get("SYN_RATE_LIMIT", "100"))
_RATE_WINDOW = int(os.environ.get("SYN_RATE_WINDOW_SECONDS", "60"))


class _RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, deque] = defaultdict(deque)

    def check(self, ip: str) -> bool:
        now = time.monotonic()
        bucket = self._buckets[ip]
        while bucket and bucket[0] < now - self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.max_requests:
            return False
        bucket.append(now)
        return True


_rate_limiter = _RateLimiter(_RATE_LIMIT, _RATE_WINDOW)


_ALLOW_ORIGINS = os.environ.get("SYN_ALLOW_ORIGINS", "*").split(",")
# NOTE: credentials are disabled because origins are wildcard. Enabling
# allow_credentials with "*" lets any website make credentialed
# cross-origin requests. Re-enable only with a fixed allow_origins list.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOW_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_MAX_BODY_SIZE = int(os.environ.get("SYN_MAX_BODY_SIZE", str(1024 * 1024)))  # default 1MB


_METHODS_WITH_BODY = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def _enforce_body_size_limit(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > _MAX_BODY_SIZE:
                # We have not read the body; close the connection so the
                # server does not try to reuse a socket with unread bytes.
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"Request body exceeds {_MAX_BODY_SIZE} byte limit"},
                    headers={"Connection": "close"},
                )
        except ValueError:
            pass
        return await call_next(request)

    # No Content-Length header. We deliberately do NOT stream the body
    # to enforce the cap: Starlette's request.stream() raises
    # ClientDisconnect mid-iteration in this uvicorn/Starlette version,
    # which corrupts the connection and can crash the worker. Instead we
    # reject any body-carrying method that omits Content-Length (covers
    # chunked transfer encoding and other unknown-size bodies), so an
    # attacker cannot bypass the size limit by omitting the header.
    if request.method in _METHODS_WITH_BODY:
        return JSONResponse(
            status_code=411,
            content={
                "detail": "Length Required: send a Content-Length header "
                f"(max {_MAX_BODY_SIZE} bytes)"
            },
        )
    return await call_next(request)


@app.middleware("http")
async def _add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    token = _request_id_var.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        _request_id_var.reset(token)


EXCLUDED_RATE_LIMIT_PATHS = {"/health"}


@app.middleware("http")
async def _rate_limit(request: Request, call_next):
    if request.url.path not in EXCLUDED_RATE_LIMIT_PATHS:
        ip = _client_ip(request)
        if not _rate_limiter.check(ip):
            return JSONResponse(
                status_code=429,
                content={"detail": f"Rate limit exceeded: {_RATE_LIMIT} requests per {_RATE_WINDOW}s"},
            )
    return await call_next(request)


def _trusted_proxy_enabled() -> bool:
    return os.environ.get("SYN_TRUSTED_PROXY", "").lower() in ("true", "1", "yes")


def _client_ip(request: Request) -> str:
    # By default we do NOT trust client-supplied proxy headers — an
    # attacker can spoof X-Forwarded-For / X-Real-IP to evade the rate
    # limit. Only honor them when a trusted reverse proxy is explicitly
    # configured via SYN_TRUSTED_PROXY=true.
    if _trusted_proxy_enabled():
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
    return request.client.host if request.client else "unknown"


class ToolCallRequest(BaseModel):
    action_type: str
    parameters: dict
    agent_id: str = "default"
    mode: str = "live"
    session_intent: str | None = None
    session_id: str | None = None


class DecisionResponse(BaseModel):
    decision: str
    trigger: str
    reason: str | None = None
    factor_scores: dict
    session_data: dict
    request_id: str | None = None
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


def _sanitize_bootstrap_path(target_path: str | None, config_path: Path) -> Path:
    """Validate and resolve a bootstrap target path, preventing directory traversal.

    Relative paths are resolved against config_path's parent directory.
    Absolute paths must resolve inside the config directory.
    """
    base_dir = config_path.parent.resolve()
    if target_path is None:
        return config_path.with_suffix(".bootstrap.yaml")
    candidate = (base_dir / target_path).resolve()
    try:
        candidate.relative_to(base_dir)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Path traversal detected: '{target_path}' is outside the allowed base directory '{base_dir}'",
        )
    return candidate


def _background_bootstrap_generate(tool_name: str, parameters: dict):
    """Background task: generate bootstrap rules for an unknown tool and store as pending."""
    pid = None
    try:
        schema = {
            "name": tool_name,
            "description": f"Unknown tool: {tool_name}",
            "parameters": {k: {"type": "string"} for k in parameters},
        }
        schemas = [schema]
        pid = AUDIT_STORE.create_pending_rule(
            tool_name=tool_name,
            proposed_yaml="",
            schemas_json=json.dumps(schemas),
            status="generating",
        )
        rules = generate_rules(LLM_CLIENT, schemas, domain_config=DOMAIN_CONFIG)
        if not rules:
            raise ValueError("LLM returned no rules. The generation may have timed out or the model produced an unexpected response.")
        yaml_str = rules_to_yaml(rules)
        errors = validate_generated_yaml(yaml_str)
        if errors:
            raise ValueError(f"Validation errors: {'; '.join(errors)}")
        AUDIT_STORE.update_pending_rule(pid, yaml_str)
    except Exception as e:
        if pid is not None:
            AUDIT_STORE.mark_pending_rule_error(pid, str(e))
        else:
            fallback_pid = AUDIT_STORE.create_pending_rule(
                tool_name=tool_name,
                proposed_yaml="",
                schemas_json=json.dumps([{"name": tool_name, "parameters": {k: {"type": "string"} for k in parameters}}]),
            )
            AUDIT_STORE.mark_pending_rule_error(fallback_pid, str(e))


@app.get("/health")
def health():
    if _last_llm_status is None:
        return {"status": "ok", "llm": None}
    return {"status": "ok", "llm": asdict(_last_llm_status)}


@app.get("/health/llm")
def health_llm():
    global _last_llm_status
    _last_llm_status = LLM_CLIENT.check_connection()
    if _last_llm_status is None:
        return {"status": "ok", "llm": None}
    return {"status": "ok", "llm": asdict(_last_llm_status)}


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


@ app.post("/bootstrap/introspect", dependencies=[Depends(require_demo_token)])
def bootstrap_introspect(req: BootstrapIntrospectRequest):
    try:
        if req.manual_schemas is not None:
            schemas = req.manual_schemas
        elif req.api_base:
            schemas = introspect_tools(api_base=req.api_base)
        else:
            schemas = [
                {"name": name, "description": info["description"], "parameters": info["parameters"]}
                for name, info in REGISTERED_TOOLS.items()
            ]
        if not schemas:
            return {"schemas": [], "rules": [], "yaml": "tools: {}", "valid": True, "errors": []}
        rules = generate_rules(LLM_CLIENT, schemas, domain_config=DOMAIN_CONFIG)
        if not rules:
            return {"error": "The LLM returned no rules. The generation may have timed out or the model produced an unexpected response. Please try again."}
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


@app.post("/bootstrap/approve", dependencies=[Depends(require_demo_token)])
def bootstrap_approve(req: BootstrapApproveRequest):
    errors = validate_generated_yaml(req.yaml_content)
    if errors:
        return {"success": False, "errors": errors}
    target = _sanitize_bootstrap_path(req.target_path, config_path)
    write_policy_config(req.yaml_content, target)
    return {"success": True, "path": str(target)}


@app.get("/bootstrap/pending")
def bootstrap_pending():
    return AUDIT_STORE.list_pending_rules()


@app.get("/bootstrap/config")
def bootstrap_config():
    if bootstrap_config_path.exists():
        return {"yaml": bootstrap_config_path.read_text()}
    return {"yaml": "tools: {}\n"}


class ApproveToolRequest(BaseModel):
    reviewed_by: str = "demo-admin"


@app.post("/bootstrap/approve/{tool_name}", dependencies=[Depends(require_demo_token)])
def bootstrap_approve_tool(tool_name: str, req: ApproveToolRequest):
    rule = AUDIT_STORE.get_pending_rule_by_tool(tool_name)
    if not rule or rule["status"] != "pending":
        return {"success": False, "error": f"No pending rule found for tool '{tool_name}'"}
    proposed_yaml = rule["proposed_yaml"]
    if not proposed_yaml:
        return {"success": False, "error": f"Pending rule for '{tool_name}' has no YAML content"}
    try:
        data = yaml.safe_load(proposed_yaml)
    except yaml.YAMLError as e:
        return {"success": False, "error": f"Invalid YAML: {e}"}
    bootstrap_path = config_path.with_suffix(".bootstrap.yaml")
    existing: dict = {}
    if bootstrap_path.exists():
        existing = yaml.safe_load(bootstrap_path.read_text()) or {}
    merged = {**existing, "tools": {**(existing.get("tools", {})), tool_name: data.get("tools", {}).get(tool_name, {})}}
    write_policy_config(yaml.dump(merged), bootstrap_path)
    AUDIT_STORE.approve_pending_rule(tool_name, reviewed_by=req.reviewed_by)
    AUDIT_STORE.append({
        "decision": "bootstrap_approved",
        "trigger": "manual_review",
        "action_type": tool_name,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "reviewed_by": req.reviewed_by,
        "reason": f"Tool '{tool_name}' was manually approved via bootstrap review.",
    })
    return {"success": True, "tool_name": tool_name}


@app.post("/bootstrap/reject/{tool_name}", dependencies=[Depends(require_demo_token)])
def bootstrap_reject_tool(tool_name: str, req: ApproveToolRequest):
    rule = AUDIT_STORE.get_pending_rule_by_tool(tool_name)
    if not rule or rule["status"] != "pending":
        return {"success": False, "error": f"No pending rule found for tool '{tool_name}'"}
    AUDIT_STORE.reject_pending_rule(tool_name, reviewed_by=req.reviewed_by)
    AUDIT_STORE.append({
        "decision": "bootstrap_rejected",
        "trigger": "manual_review",
        "action_type": tool_name,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "reviewed_by": req.reviewed_by,
    })
    return {"success": True, "tool_name": tool_name}


class UpdatePendingYamlRequest(BaseModel):
    proposed_yaml: str


@app.put("/bootstrap/pending/{tool_name}", dependencies=[Depends(require_demo_token)])
def bootstrap_update_pending(tool_name: str, req: UpdatePendingYamlRequest):
    rule = AUDIT_STORE.get_pending_rule_by_tool(tool_name)
    if not rule or rule["status"] not in ("pending", "generating"):
        return {"success": False, "error": f"No pending rule found for tool '{tool_name}'"}
    AUDIT_STORE.update_pending_rule(rule["id"], req.proposed_yaml)
    return {"success": True, "tool_name": tool_name}


@app.post("/bootstrap/approve-all", dependencies=[Depends(require_demo_token)])
def bootstrap_approve_all(req: ApproveToolRequest):
    pending = AUDIT_STORE.list_pending_rules()
    if not pending:
        return {"success": False, "error": "No pending rules to approve"}
    bootstrap_path = config_path.with_suffix(".bootstrap.yaml")
    existing: dict = {}
    if bootstrap_path.exists():
        existing = yaml.safe_load(bootstrap_path.read_text()) or {}
    merged_tools = dict(existing.get("tools", {}))
    for rule in pending:
        try:
            data = yaml.safe_load(rule["proposed_yaml"])
            if data and "tools" in data:
                merged_tools[rule["tool_name"]] = data["tools"].get(rule["tool_name"], {})
        except yaml.YAMLError:
            pass
    merged = {**existing, "tools": merged_tools}
    write_policy_config(yaml.dump(merged), bootstrap_path)
    reviewed_by = req.reviewed_by
    for rule in pending:
        AUDIT_STORE.approve_pending_rule(rule["tool_name"], reviewed_by=reviewed_by)
        AUDIT_STORE.append({
            "decision": "bootstrap_approved",
            "trigger": "manual_review",
            "action_type": rule["tool_name"],
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "reviewed_by": reviewed_by,
            "reason": f"Tool '{rule['tool_name']}' was approved via bulk bootstrap review.",
        })
    return {"success": True, "approved_count": len(pending)}


class RetryRequest(BaseModel):
    tool_name: str
    parameters: dict = {}


@app.post("/bootstrap/retry/{rule_id}", dependencies=[Depends(require_demo_token)])
def bootstrap_retry(rule_id: int, req: RetryRequest):
    rows = AUDIT_STORE._conn.execute(
        "SELECT * FROM pending_rules WHERE id = ?", (rule_id,)
    ).fetchall()
    if not rows:
        return {"success": False, "error": f"No rule found with id {rule_id}"}
    row = dict(rows[0])
    if row["status"] != "error":
        return {"success": False, "error": f"Rule {rule_id} is not in error state"}
    # Re-trigger generation
    try:
        schema = {
            "name": row["tool_name"],
            "description": f"Unknown tool: {row['tool_name']}",
            "parameters": {k: {"type": "string"} for k in req.parameters},
        }
        schemas = [schema]
        rules = generate_rules(LLM_CLIENT, schemas, domain_config=DOMAIN_CONFIG)
        yaml_str = rules_to_yaml(rules)
        errors = validate_generated_yaml(yaml_str)
        if errors:
            raise ValueError(f"Validation errors: {'; '.join(errors)}")
        AUDIT_STORE.retry_pending_rule(rule_id, yaml_str, json.dumps(schemas))
        return {"success": True, "rule_id": rule_id}
    except Exception as e:
        AUDIT_STORE.mark_pending_rule_error(rule_id, str(e))
        return {"success": False, "error": str(e), "rule_id": rule_id}


class ResolveRequest(BaseModel):
    outcome: str  # "approved" or "denied"


@app.post("/resolve/{entry_id}", dependencies=[Depends(require_demo_token)])
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


@app.post("/admin/reset", dependencies=[Depends(require_demo_token)])
def admin_reset() -> dict[str, Any]:
    """Reset the public demo to a clean slate without shell access.

    Mirrors the manual `rm -f data/audit.db` + `printf 'tools: {}\\n' >
    engine/policy_config.bootstrap.yaml` we run between judging sessions, but
    done inside the live connection: it empties the audit store
    (decisions + pending_rules + sessions) and restores the bootstrap
    config to its baseline `tools: {}`. The merged-tools cache reloads on the
    next request because the file mtime changes.

    Token-gated (reuses #34's `require_demo_token` dependency).
    """
    cleared = AUDIT_STORE.reset()
    # Restore the bootstrap baseline; bumping mtime triggers a merged-tools
    # cache reload on the next _get_merged_tools() call.
    write_policy_config("tools: {}\n", bootstrap_config_path)
    return {
        "success": True,
        "cleared": cleared,
        "bootstrap_baseline": "tools: {}",
    }


@app.post("/intercept", dependencies=[Depends(require_demo_token)])
async def intercept(
    req: ToolCallRequest,
    request: Request,
    background_tasks: BackgroundTasks = None,
) -> DecisionResponse:
    request_id = getattr(request.state, "request_id", None)
    retention_days = int(os.environ.get("SYN_AUDIT_RETENTION_DAYS", "90"))
    AUDIT_STORE.expire_old(retention_days=retention_days)
    trigger_note = None
    session_id = generate_session_id(req.agent_id, int(time.time()))

    if req.session_intent == "start":
        session_id = AUDIT_STORE.create_session(req.agent_id)
    elif req.session_intent == "continue":
        session = AUDIT_STORE.get_session(req.session_id) if req.session_id else None
        if session and session.get("status") == "active" and session.get("closed_at") is None:
            session_id = session["id"]
        else:
            trigger_note = "session:fallback_timebucket"
    elif req.session_intent == "end":
        if req.session_id:
            AUDIT_STORE.close_session(req.session_id)

    is_simulation = (req.mode or "").lower() == "simulation"
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    merged_tools = _get_merged_tools()
    if req.action_type not in merged_tools:
        trigger = "gateway:unknown_tool"
        if trigger_note:
            trigger = f"{trigger_note}+{trigger}"
        final_trigger = trigger
        resp = DecisionResponse(
            decision="blocked",
            trigger=trigger,
            reason="Tool is not registered in the policy; unknown tools are blocked by default.",
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
            request_id=request_id,
        )
        if not is_simulation:
            AUDIT_STORE.append(resp.model_dump(), session_id=session_id, agent_id=req.agent_id)
        if background_tasks and not is_simulation:
            background_tasks.add_task(_background_bootstrap_generate, req.action_type, req.parameters)
        return resp

    eval_config = {**FULL_CONFIG, "tools": merged_tools}
    windowed_history = AUDIT_STORE.get_agent_recent_history(req.agent_id, window_minutes=30)
    unbounded_history = AUDIT_STORE.get_agent_recent_history(req.agent_id, window_minutes=None)
    result = risk_evaluate(
        action_type=req.action_type,
        parameters=req.parameters,
        session_context={
            "history": windowed_history,
            "unbounded_history": unbounded_history,
            "session_id": session_id,
        },
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

    final_trigger = result.trigger
    if trigger_note:
        final_trigger = f"{trigger_note}+{final_trigger}"

    prompt = build_explanation_prompt(
        action_type=req.action_type,
        decision=result.decision.value,
        trigger=final_trigger,
        reason=result.reason,
        factor_scores=result.factor_scores.to_dict(),
        top_factor=top_factor,
    )
    loop = asyncio.get_event_loop()
    llm_output = await loop.run_in_executor(_THREAD_POOL, LLM_CLIENT.generate, prompt)

    resp = DecisionResponse(
        decision=result.decision.value,
        trigger=final_trigger,
        reason=result.reason,
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
        request_id=request_id,
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
        AUDIT_STORE.append(entry, session_id=session_id, agent_id=req.agent_id)

        if result.decision.value == "escalated":
            SLACK_NOTIFIER.send_escalation(resp.model_dump())

    return resp

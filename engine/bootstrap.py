from __future__ import annotations

import ipaddress
import json
import socket
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from engine.llm import LLMClient

_domain_config_path = Path(__file__).resolve().parent / "domain_config.yaml"
DEFAULT_DOMAIN_CONFIG: dict[str, str] = (
    yaml.safe_load(_domain_config_path.read_text())
    if _domain_config_path.exists()
    else {
        "industry": "Financial services (payments, banking)",
        "regulatory": "EU AI Act, GDPR, FINRA/SEC",
        "risk_priorities": "Prevent unauthorized payments, protect customer PII, prevent data exfiltration",
    }
)

BOOTSTRAP_PROMPT_TEMPLATE = """You are a security policy generator for an AI governance system called "syn".
Industry: {industry}
Regulatory: {regulatory}
Risk priorities: {risk_priorities}

Given the following MCP tool schemas, generate security policy rules for each tool.
Return structured JSON with the following per-tool fields:
- tool_name: the name of the tool
- severity_rules: list of rules with either max_amount or path_pattern or query_type, and a score (0-100)
- policy_rules: list of policy conditions with description, condition (field, operator, value), score
- data_sensitivity_rules: list of field/pattern pairs with score
- tool_trust_tier: one of "official", "verified", "unknown"
- anomaly_lookback: integer (number of past calls to consider)
- reasoning: short explanation of why these rules were chosen

Tool schemas:
{schemas_json}

Return ONLY valid JSON — no explanation, no markdown."""


def _is_safe_introspect_url(url: str) -> bool:
    """Reject non-HTTP(S) URLs and any host that resolves to a
    private, loopback, link-local, reserved, or multicast address.

    Prevents Server-Side Request Forgery via the user-supplied
    `api_base` (e.g. http://169.254.169.254/ or http://localhost:port).
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        return False
    for info in infos:
        try:
            addr = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
        ):
            return False
    return True


def introspect_tools(
    api_base: str | None = None,
    manual_path: str | None = None,
) -> list[dict[str, Any]]:
    if manual_path:
        with open(manual_path) as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return data.get("tools", data.get("result", [data]))
    if api_base:
        if not _is_safe_introspect_url(api_base):
            raise ValueError(
                "api_base must be an http(s) URL resolving to a public host "
                "(private, loopback, and link-local addresses are rejected)"
            )
        import httpx
        resp = httpx.get(f"{api_base}/tools", timeout=10)
        resp.raise_for_status()
        return resp.json()
    raise ValueError("Either api_base or manual_path must be provided")


def build_bootstrap_prompt(
    tool_schemas: list[dict[str, Any]],
    domain_config: dict[str, str] | None = None,
) -> str:
    schemas_json = json.dumps(tool_schemas, indent=2)
    dc = domain_config or DEFAULT_DOMAIN_CONFIG
    return BOOTSTRAP_PROMPT_TEMPLATE.format(
        schemas_json=schemas_json,
        industry=dc.get("industry", ""),
        regulatory=dc.get("regulatory", ""),
        risk_priorities=dc.get("risk_priorities", ""),
    )


def generate_rules(
    client: LLMClient,
    tool_schemas: list[dict[str, Any]],
    domain_config: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    prompt = build_bootstrap_prompt(tool_schemas, domain_config=domain_config)
    output = client.generate(prompt, output_schema={"type": "bootstrap_rules"})
    return output.get("tools", [])


def _yaml_quote(val: str) -> str:
    if val in ("null", "true", "false", "yes", "no", "on", "off"):
        return f"'{val}'"
    special = {":", "#", "{", "}", "[", "]", ",", "&", "*", "?", "|", "-", "<", ">", "=", "!", "%", "@", "`", "$"}
    if any(c in val for c in special) or "\\" in val:
        escaped = val.replace("'", "''")
        return f"'{escaped}'"
    return val


def _render_yaml_list(items: list, indent: int, key: str | None = None) -> list[str]:
    lines: list[str] = []
    if key is not None:
        lines.append(f"{' ' * indent}{key}:")
    for item in items:
        if isinstance(item, dict):
            lines.append(f"{' ' * (indent + 2)}-")
            for sk, sv in item.items():
                if sk is None:
                    continue
                lines.append(_render_yaml_val(sv, indent + 4, key=sk))
        elif isinstance(item, list):
            lines.append(f"{' ' * (indent + 2)}-")
            lines.extend(_render_yaml_list(item, indent + 4))
        elif item is None:
            lines.append(f"{' ' * (indent + 2)}- null")
        else:
            pad = " " * (indent + 2)
            it = _yaml_quote(str(item)) if isinstance(item, str) else str(item)
            lines.append(f"{pad}- {it}")
    return lines


def _render_yaml_val(val: Any, indent: int, key: str | None = None) -> str:
    if val is None:
        pad = " " * indent
        prefix = f"{pad}{key}:" if key else f"{pad}-"
        return f"{prefix} null"
    if isinstance(val, bool):
        pad = " " * indent
        prefix = f"{pad}{key}:" if key else f"{pad}-"
        return f"{prefix} {'true' if val else 'false'}"
    if isinstance(val, (int, float)):
        pad = " " * indent
        prefix = f"{pad}{key}:" if key else f"{pad}-"
        return f"{prefix} {val}"
    if isinstance(val, str):
        pad = " " * indent
        prefix = f"{pad}{key}:" if key else f"{pad}-"
        return f"{prefix} {_yaml_quote(val)}"
    if isinstance(val, dict):
        pad = " " * indent
        if key is None:
            lines = [f"{pad}-"]
        else:
            lines = [f"{pad}{key}:"]
        for sk, sv in val.items():
            if sk is None:
                continue
            lines.append(_render_yaml_val(sv, indent + 2, key=sk))
        return "\n".join(lines)
    if isinstance(val, list):
        return "\n".join(_render_yaml_list(val, indent, key=key))
    pad = " " * indent
    prefix = f"{pad}{key}:" if key else f"{pad}-"
    return f"{prefix} {val}"


def rules_to_yaml(tools: list[dict[str, Any]]) -> str:
    if not tools:
        return "tools: {}"
    lines = ["tools:"]
    for tool in tools:
        name = tool.get("tool_name") or "unknown"
        reasoning = tool.get("reasoning", "")
        lines.append(f"  {name}:")
        if reasoning:
            for comment_line in reasoning.strip().split("\n"):
                lines.append(f"    # {comment_line}")
        sev = tool.get("severity_rules", [])
        if sev:
            lines.append("    severity_rules:")
            for r in sev:
                lines.append("      -")
                for k, v in r.items():
                    lines.append(_render_yaml_val(v, 8, key=k))
        pol = tool.get("policy_rules", [])
        if pol:
            lines.append("    policy_rules:")
            for r in pol:
                lines.append("      -")
                for k, v in r.items():
                    lines.append(_render_yaml_val(v, 8, key=k))
        ds = tool.get("data_sensitivity_rules", [])
        if ds:
            lines.append("    data_sensitivity_rules:")
            for r in ds:
                lines.append("      -")
                for k, v in r.items():
                    lines.append(_render_yaml_val(v, 8, key=k))
        trust = tool.get("tool_trust_tier")
        if trust:
            lines.append(f"    tool_trust_tier: {trust}")
        lookback = tool.get("anomaly_lookback")
        if lookback is not None:
            lines.append(f"    anomaly_lookback: {lookback}")
    return "\n".join(lines)


def validate_generated_yaml(yaml_str: str) -> list[str]:
    errors: list[str] = []
    try:
        data = yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        return [f"YAML parse error: {e}"]

    if not isinstance(data, dict):
        return ["Root must be a mapping"]

    tools = data.get("tools")
    if not isinstance(tools, dict):
        return ["Missing or invalid 'tools' mapping"]

    for tool_name, tool_config in tools.items():
        if not isinstance(tool_config, dict):
            errors.append(f"  {tool_name}: must be a mapping")
            continue
        trust = tool_config.get("tool_trust_tier")
        if trust and trust not in ("official", "verified", "unknown"):
            errors.append(f"  {tool_name}: invalid tool_trust_tier '{trust}'")
        lookback = tool_config.get("anomaly_lookback")
        if lookback is not None and not (isinstance(lookback, int) and lookback > 0):
            errors.append(f"  {tool_name}: anomaly_lookback must be a positive integer")

        for rule_type in ("severity_rules", "policy_rules", "data_sensitivity_rules"):
            rules = tool_config.get(rule_type, [])
            if not isinstance(rules, list):
                errors.append(f"  {tool_name}: {rule_type} must be a list")

    return errors


def write_policy_config(yaml_str: str, config_path: str | Path) -> None:
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml_str)

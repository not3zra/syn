from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

from engine.llm import LLMClient

BOOTSTRAP_PROMPT_TEMPLATE = """You are a security policy generator for an AI governance system called "syn".
Industry: Financial services (payments, banking)
Regulatory: EU AI Act, GDPR, FINRA/SEC
Risk priorities: Prevent unauthorized payments, protect customer PII, prevent data exfiltration

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
        import httpx
        resp = httpx.get(f"{api_base}/tools", timeout=10)
        resp.raise_for_status()
        return resp.json()
    raise ValueError("Either api_base or manual_path must be provided")


def build_bootstrap_prompt(tool_schemas: list[dict[str, Any]]) -> str:
    schemas_json = json.dumps(tool_schemas, indent=2)
    return BOOTSTRAP_PROMPT_TEMPLATE.format(schemas_json=schemas_json)


def generate_rules(
    client: LLMClient,
    tool_schemas: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    prompt = build_bootstrap_prompt(tool_schemas)
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


def _render_yaml_val(val: Any, indent: int, key: str | None = None) -> str:
    pad = " " * indent
    prefix = f"{pad}{key}:" if key else f"{pad}-"
    if val is None:
        return f"{prefix} null"
    if isinstance(val, bool):
        return f"{prefix} {'true' if val else 'false'}"
    if isinstance(val, (int, float)):
        return f"{prefix} {val}"
    if isinstance(val, str):
        return f"{prefix} {_yaml_quote(val)}"
    if isinstance(val, dict):
        lines = [f"{pad}{key}:"]
        for sk, sv in val.items():
            lines.append(_render_yaml_val(sv, indent + 2, key=sk))
        return "\n".join(lines)
    if isinstance(val, list):
        lines = [f"{pad}{key}:"]
        for item in val:
            lines.append(_render_yaml_val(item, indent + 2))
        return "\n".join(lines)
    return f"{prefix} {val}"


def rules_to_yaml(tools: list[dict[str, Any]]) -> str:
    lines = ["tools:"]
    for tool in tools:
        name = tool.get("tool_name", "unknown")
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

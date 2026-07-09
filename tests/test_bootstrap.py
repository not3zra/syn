from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from engine.bootstrap import (
    BOOTSTRAP_PROMPT_TEMPLATE,
    build_bootstrap_prompt,
    generate_rules,
    introspect_tools,
    rules_to_yaml,
    validate_generated_yaml,
    write_policy_config,
)
from engine.llm import MockLLMClient


class TestIntrospectTools:
    def test_raises_without_args(self):
        with pytest.raises(ValueError, match="api_base or manual_path"):
            introspect_tools()

    def test_manual_json_file(self):
        schemas = [
            {
                "name": "send_payment",
                "description": "Send a payment",
                "parameters": {"amount": {"type": "number"}},
            }
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(schemas, f)
            f.flush()
            result = introspect_tools(manual_path=f.name)
            assert result == schemas
        Path(f.name).unlink()

    def test_manual_json_with_tools_key(self):
        data = {
            "tools": [
                {
                    "name": "send_payment",
                    "description": "Send a payment",
                    "parameters": {},
                }
            ]
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            result = introspect_tools(manual_path=f.name)
            assert result == data["tools"]
        Path(f.name).unlink()


class TestBuildBootstrapPrompt:
    def test_includes_schemas(self):
        schemas = [{"name": "send_payment", "parameters": {"amount": {"type": "number"}}}]
        prompt = build_bootstrap_prompt(schemas)
        assert "send_payment" in prompt
        assert "Financial services" in prompt

    def test_includes_all_schemas(self):
        schemas = [
            {"name": "send_payment", "parameters": {}},
            {"name": "delete_file", "parameters": {}},
        ]
        prompt = build_bootstrap_prompt(schemas)
        assert "send_payment" in prompt
        assert "delete_file" in prompt

    def test_formats_schemas_as_json(self):
        schemas = [{"name": "test_tool"}]
        prompt = build_bootstrap_prompt(schemas)
        assert '"test_tool"' in prompt

    def test_default_domain_values_in_prompt(self):
        schemas = [{"name": "test_tool", "parameters": {}}]
        prompt = build_bootstrap_prompt(schemas)
        assert "Financial services (payments, banking)" in prompt
        assert "EU AI Act, GDPR, FINRA/SEC" in prompt
        assert "Prevent unauthorized payments" in prompt

    def test_custom_domain_config_in_prompt(self):
        schemas = [{"name": "test_tool", "parameters": {}}]
        custom_config = {
            "industry": "Healthcare (HIPAA)",
            "regulatory": "HIPAA, HITECH",
            "risk_priorities": "Protect patient records, prevent data breaches",
        }
        prompt = build_bootstrap_prompt(schemas, domain_config=custom_config)
        assert "Healthcare (HIPAA)" in prompt
        assert "HIPAA, HITECH" in prompt
        assert "Protect patient records" in prompt
        assert "Financial services" not in prompt


class TestGenerateRules:
    def test_returns_list_of_rules(self):
        client = MockLLMClient()
        schemas = [{"name": "send_payment", "parameters": {"amount": {"type": "number"}}}]
        rules = generate_rules(client, schemas)
        assert isinstance(rules, list)
        assert len(rules) > 0

    def test_each_rule_has_required_fields(self):
        client = MockLLMClient()
        schemas = [{"name": "send_payment", "parameters": {"amount": {"type": "number"}}}]
        rules = generate_rules(client, schemas)
        for rule in rules:
            assert "tool_name" in rule
            assert "severity_rules" in rule
            assert "data_sensitivity_rules" in rule
            assert "tool_trust_tier" in rule
            assert "anomaly_lookback" in rule
            assert "reasoning" in rule

    def test_generates_multiple_tools(self):
        client = MockLLMClient()
        schemas = [
            {"name": "send_payment", "parameters": {}},
            {"name": "delete_file", "parameters": {}},
        ]
        rules = generate_rules(client, schemas)
        assert len(rules) >= 2

    def test_verify_structure(self):
        client = MockLLMClient()
        schemas = [{"name": "send_payment", "parameters": {"amount": {"type": "number"}}}]
        rules = generate_rules(client, schemas)
        rule = rules[0]
        for sr in rule["severity_rules"]:
            assert "score" in sr
        for dr in rule["data_sensitivity_rules"]:
            assert "field" in dr
            assert "pattern" in dr
            assert "score" in dr


class TestRulesToYAML:
    def test_empty_tools(self):
        yaml_str = rules_to_yaml([])
        assert yaml_str == "tools:"

    def test_single_tool_with_minimal_fields(self):
        tools = [
            {
                "tool_name": "send_payment",
                "severity_rules": [{"max_amount": 1000, "score": 20}],
                "policy_rules": [],
                "data_sensitivity_rules": [],
                "tool_trust_tier": "official",
                "anomaly_lookback": 20,
                "reasoning": "test reason",
            }
        ]
        yaml_str = rules_to_yaml(tools)
        assert "send_payment:" in yaml_str
        assert "# test reason" in yaml_str
        assert "severity_rules:" in yaml_str
        assert "max_amount: 1000" in yaml_str
        assert "score: 20" in yaml_str
        assert "tool_trust_tier: official" in yaml_str
        assert "anomaly_lookback: 20" in yaml_str

    def test_parses_back_to_valid_yaml(self):
        tools = [
            {
                "tool_name": "send_payment",
                "severity_rules": [{"max_amount": 1000, "score": 20}],
                "policy_rules": [],
                "data_sensitivity_rules": [{"field": "recipient", "pattern": "external", "score": 40}],
                "tool_trust_tier": "official",
                "anomaly_lookback": 20,
                "reasoning": "Payments need limits",
            }
        ]
        yaml_str = rules_to_yaml(tools)
        data = yaml.safe_load(yaml_str)
        assert "tools" in data
        assert "send_payment" in data["tools"]
        tp = data["tools"]["send_payment"]
        assert tp["tool_trust_tier"] == "official"
        assert tp["anomaly_lookback"] == 20
        assert len(tp["severity_rules"]) == 1
        assert len(tp["data_sensitivity_rules"]) == 1

    def test_policy_rules_in_yaml(self):
        tools = [
            {
                "tool_name": "send_payment",
                "severity_rules": [],
                "policy_rules": [
                    {
                        "description": "No high payments",
                        "condition": {"field": "amount", "operator": ">", "value": 5000},
                        "score": 100,
                    }
                ],
                "data_sensitivity_rules": [],
                "tool_trust_tier": "official",
                "anomaly_lookback": 20,
                "reasoning": "",
            }
        ]
        yaml_str = rules_to_yaml(tools)
        data = yaml.safe_load(yaml_str)
        pr = data["tools"]["send_payment"]["policy_rules"]
        assert len(pr) == 1
        assert pr[0]["description"] == "No high payments"
        assert pr[0]["condition"]["operator"] == ">"

    def test_reasoning_comment_with_multiple_lines(self):
        tools = [
            {
                "tool_name": "test_tool",
                "severity_rules": [],
                "policy_rules": [],
                "data_sensitivity_rules": [],
                "tool_trust_tier": "official",
                "anomaly_lookback": 10,
                "reasoning": "Line one\nLine two",
            }
        ]
        yaml_str = rules_to_yaml(tools)
        assert "# Line one" in yaml_str
        assert "# Line two" in yaml_str

    def test_null_values_handled(self):
        tools = [
            {
                "tool_name": "test_tool",
                "severity_rules": [{"max_amount": None, "score": 15}],
                "policy_rules": [],
                "data_sensitivity_rules": [],
                "tool_trust_tier": "official",
                "anomaly_lookback": 10,
                "reasoning": "",
            }
        ]
        yaml_str = rules_to_yaml(tools)
        assert "null" in yaml_str


class TestValidateGeneratedYAML:
    def test_valid_yaml(self):
        yaml_str = """tools:
  send_payment:
    severity_rules: []
    policy_rules: []
    data_sensitivity_rules: []
    tool_trust_tier: official
    anomaly_lookback: 20"""
        errors = validate_generated_yaml(yaml_str)
        assert errors == []

    def test_missing_tools(self):
        yaml_str = """other: true"""
        errors = validate_generated_yaml(yaml_str)
        assert any("Missing" in e for e in errors)

    def test_invalid_trust_tier(self):
        yaml_str = """tools:
  send_payment:
    severity_rules: []
    policy_rules: []
    data_sensitivity_rules: []
    tool_trust_tier: super_admin
    anomaly_lookback: 20"""
        errors = validate_generated_yaml(yaml_str)
        assert any("invalid tool_trust_tier" in e for e in errors)

    def test_invalid_yaml_syntax(self):
        errors = validate_generated_yaml("tools:\n  bad yaml:\n : : :")
        assert len(errors) > 0
        assert any("parse" in e.lower() for e in errors)

    def test_non_positive_lookback(self):
        yaml_str = """tools:
  test:
    severity_rules: []
    policy_rules: []
    data_sensitivity_rules: []
    tool_trust_tier: official
    anomaly_lookback: -5"""
        errors = validate_generated_yaml(yaml_str)
        assert any("positive" in e for e in errors)

    def test_rules_must_be_lists(self):
        yaml_str = """tools:
  test:
    severity_rules: not_a_list
    policy_rules: []
    data_sensitivity_rules: []
    tool_trust_tier: official
    anomaly_lookback: 10"""
        errors = validate_generated_yaml(yaml_str)
        assert any("severity_rules" in e for e in errors)


class TestWritePolicyConfig:
    def test_writes_yaml_to_file(self):
        yaml_str = "tools:\n  test:\n    tool_trust_tier: official"
        with tempfile.NamedTemporaryFile(mode="r", suffix=".yaml", delete=False) as f:
            temp_path = f.name
        write_policy_config(yaml_str, temp_path)
        content = Path(temp_path).read_text()
        assert content == yaml_str
        Path(temp_path).unlink()

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = Path(tmpdir) / "nested" / "sub" / "policy.yaml"
            write_policy_config("tools: {}", str(nested))
            assert nested.exists()
            nested.unlink()


class TestEndToEndFlow:
    def test_full_bootstrap_flow(self):
        client = MockLLMClient()
        schemas = [
            {"name": "send_payment", "parameters": {"amount": {"type": "number", "description": "Payment amount"}}},
            {"name": "delete_file", "parameters": {"file_path": {"type": "string", "description": "Path to delete"}}},
        ]
        rules = generate_rules(client, schemas)
        assert len(rules) >= 2

        yaml_str = rules_to_yaml(rules)
        errors = validate_generated_yaml(yaml_str)
        assert errors == []

        data = yaml.safe_load(yaml_str)
        assert "tools" in data
        for tool_name in ("send_payment", "delete_file"):
            assert tool_name in data["tools"]

    def test_llm_call_count_increments(self):
        client = MockLLMClient()
        schemas = [{"name": "send_payment", "parameters": {}}]
        before = client._call_count
        generate_rules(client, schemas)
        assert client._call_count == before + 1

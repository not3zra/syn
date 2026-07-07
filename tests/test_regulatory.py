import yaml
from pathlib import Path

from engine.regulatory import map_regulatory_tier, map_us_regime_flags
from engine.models import FactorScores


def load_mapping():
    path = Path(__file__).parent.parent / "engine" / "regulatory_mapping.yaml"
    return {"regulatory_mapping": yaml.safe_load(path.read_text())}


REG_CONFIG = load_mapping()


class TestEUTierMapping:
    def test_minimal_risk_default(self):
        scores = FactorScores()
        tier = map_regulatory_tier("send_payment", scores, REG_CONFIG)
        assert tier == "minimal_risk"

    def test_unacceptable_risk_social_scoring(self):
        scores = FactorScores()
        tier = map_regulatory_tier("social_scoring", scores, REG_CONFIG)
        assert tier == "unacceptable_risk"

    def test_unacceptable_risk_biometric_categorization(self):
        scores = FactorScores()
        tier = map_regulatory_tier("real_time_biometric_categorization", scores, REG_CONFIG)
        assert tier == "unacceptable_risk"

    def test_unacceptable_risk_subliminal_manipulation(self):
        scores = FactorScores()
        tier = map_regulatory_tier("subliminal_manipulation", scores, REG_CONFIG)
        assert tier == "unacceptable_risk"

    def test_unacceptable_risk_exploitation(self):
        scores = FactorScores()
        tier = map_regulatory_tier("exploitation_of_vulnerabilities", scores, REG_CONFIG)
        assert tier == "unacceptable_risk"

    def test_high_risk_biometric_identification(self):
        scores = FactorScores()
        tier = map_regulatory_tier("biometric_identification", scores, REG_CONFIG)
        assert tier == "high_risk"

    def test_high_risk_unsigned_tool_high_severity(self):
        scores = FactorScores(severity=80, tool_trust=10)
        tier = map_regulatory_tier("send_payment", scores, REG_CONFIG)
        assert tier == "high_risk"

    def test_high_risk_unknown_tool_high_severity(self):
        scores = FactorScores(severity=70, tool_trust=40)
        tier = map_regulatory_tier("delete_file", scores, REG_CONFIG)
        assert tier == "high_risk"

    def test_high_risk_high_data_sensitivity(self):
        scores = FactorScores(data_sensitivity=95)
        tier = map_regulatory_tier("send_payment", scores, REG_CONFIG)
        assert tier == "high_risk"

    def test_not_high_risk_unknown_tool_low_severity(self):
        scores = FactorScores(severity=50, tool_trust=40)
        tier = map_regulatory_tier("send_payment", scores, REG_CONFIG)
        assert tier == "minimal_risk"

    def test_not_high_risk_high_severity_trusted_tool(self):
        scores = FactorScores(severity=85, tool_trust=100)
        tier = map_regulatory_tier("send_payment", scores, REG_CONFIG)
        assert tier == "minimal_risk"

    def test_limited_risk_chatbot(self):
        scores = FactorScores()
        tier = map_regulatory_tier("chatbot", scores, REG_CONFIG)
        assert tier == "limited_risk"

    def test_limited_risk_deepfake(self):
        scores = FactorScores()
        tier = map_regulatory_tier("deepfake_generation", scores, REG_CONFIG)
        assert tier == "limited_risk"


class TestUSRegimeFlags:
    def test_financial_action_gets_flags(self):
        flags = map_us_regime_flags("send_payment", REG_CONFIG)
        assert "FINRA" in flags
        assert "SEC" in flags

    def test_non_financial_no_flags(self):
        flags = map_us_regime_flags("delete_file", REG_CONFIG)
        assert flags == []

    def test_multiple_financial_actions(self):
        for action in ["send_payment", "update_account", "trade_execution", "payment_processing"]:
            flags = map_us_regime_flags(action, REG_CONFIG)
            assert "FINRA" in flags, f"{action} should have FINRA flag"
            assert "SEC" in flags, f"{action} should have SEC flag"


class TestCriticalGuard:
    """Regression guard: No extreme input produces unacceptable_risk
    unless the action_type is literally an Article 5 prohibited practice."""

    def test_no_false_unacceptable_risk(self):
        prohibited = {
            "social_scoring", "real_time_biometric_categorization",
            "subliminal_manipulation", "exploitation_of_vulnerabilities",
        }

        action_types = [
            "send_payment", "delete_file", "query_database",
            "biometric_identification", "chatbot",
            "unknown_tool", "trade_execution",
        ]

        severity_values = [0, 50, 70, 90, 100]
        data_sensitivity_values = [0, 50, 80, 90, 100]
        tool_trust_values = [10, 40, 50, 80, 100]

        for action in action_types:
            for sev in severity_values:
                for ds in data_sensitivity_values:
                    for tt in tool_trust_values:
                        scores = FactorScores(
                            severity=sev,
                            data_sensitivity=ds,
                            tool_trust=tt,
                        )
                        tier = map_regulatory_tier(action, scores, REG_CONFIG)
                        if tier == "unacceptable_risk":
                            assert action in prohibited, (
                                f"Only Article 5 practices should get 'unacceptable_risk', "
                                f"but '{action}' (sev={sev}, ds={ds}, tt={tt}) got it"
                            )

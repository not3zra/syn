from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Decision(str, Enum):
    APPROVED = "approved"
    ESCALATED = "escalated"
    BLOCKED = "blocked"


@dataclass
class FactorScores:
    severity: float = 0.0
    policy: float = 0.0
    anomaly: float = 0.0
    data_sensitivity: float = 0.0
    confidence: float = 100.0
    tool_trust: float = 100.0

    def to_dict(self) -> dict[str, float]:
        return {
            "severity": self.severity,
            "policy": self.policy,
            "anomaly": self.anomaly,
            "data_sensitivity": self.data_sensitivity,
            "confidence": self.confidence,
            "tool_trust": self.tool_trust,
        }


@dataclass
class SessionData:
    session_id: str | None = None
    cumulative_severity: float = 0.0
    pattern_matched: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "cumulative_severity": self.cumulative_severity,
            "pattern_matched": self.pattern_matched,
        }


@dataclass
class RiskEngineResult:
    decision: Decision
    trigger: str
    factor_scores: FactorScores
    reason: str | None = None
    session_data: SessionData = field(default_factory=SessionData)
    regulatory_tier: str = "minimal_risk"
    us_regime_flags: list[str] = field(default_factory=list)

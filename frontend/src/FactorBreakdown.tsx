import type { FactorScores } from './types';
import { CompactGauge } from './RiskGauge';

const FACTOR_LABELS: Record<keyof FactorScores, string> = {
  severity: 'Severity',
  policy: 'Policy',
  anomaly: 'Anomaly',
  data_sensitivity: 'Data Sensitivity',
  confidence: 'Confidence',
  tool_trust: 'Tool Trust',
};

function getColor(score: number, isInverted: boolean): string {
  const effective = isInverted ? 100 - score : score;
  if (effective >= 70) return 'var(--red)';
  if (effective >= 40) return 'var(--yellow)';
  return 'var(--green)';
}

const INVERTED = new Set(['confidence', 'tool_trust']);

interface FactorBreakdownProps {
  scores: FactorScores;
}

export function FactorBreakdown({ scores }: FactorBreakdownProps) {
  const entries = Object.entries(FACTOR_LABELS) as [keyof FactorScores, string][];

  return (
    <div className="factor-breakdown">
      <h3 className="section-title">Factor Scores</h3>
      <div className="factor-table">
        {entries.map(([key, label]) => {
          const score = scores[key];
          const color = getColor(score, INVERTED.has(key));
          return (
            <div key={key} className="factor-row">
              <div className="factor-info">
                <span className="factor-name">{label}</span>
                <span className="factor-score" style={{ color }}>
                  {score}
                </span>
              </div>
              <CompactGauge score={INVERTED.has(key) ? 100 - score : score} color={color} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

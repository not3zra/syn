import type { FactorScores } from './types';
import { CompactGauge } from './RiskGauge';

const FACTOR_LABELS: Record<keyof FactorScores, string> = {
  severity: 'Severity',
  policy: 'Policy',
  anomaly: 'Anomaly',
  data_sensitivity: 'Data sensitivity',
  confidence: 'Confidence',
  tool_trust: 'Tool trust',
};

const INVERTED = new Set(['confidence', 'tool_trust']);

interface FactorBreakdownProps {
  scores: FactorScores;
}

export function FactorBreakdown({ scores }: FactorBreakdownProps) {
  const entries = Object.entries(FACTOR_LABELS) as [keyof FactorScores, string][];

  function band(score: number, isInverted: boolean): 'is-low' | 'is-mid' | 'is-high' {
    const effective = isInverted ? 100 - score : score;
    if (effective >= 70) return 'is-high';
    if (effective >= 40) return 'is-mid';
    return 'is-low';
  }

  return (
    <div className="factor-breakdown">
      <h3 className="section-title">Factor scores</h3>
      <div className="factor-table">
        {entries.map(([key, label]) => {
          const score = scores[key];
          const inverted = INVERTED.has(key);
          const cls = band(score, inverted);
          return (
            <div key={key} className="factor-row">
              <div className="factor-info">
                <span className="factor-name">{label}</span>
                <span className={`factor-score ${cls}`}>{score}</span>
              </div>
              <CompactGauge score={score} inverted={inverted} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

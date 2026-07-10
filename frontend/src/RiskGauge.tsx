interface RiskGaugeProps {
  score: number;
  label: string;
  size?: 'sm' | 'md' | 'lg';
}

function band(score: number): 'is-low' | 'is-mid' | 'is-high' {
  if (score >= 70) return 'is-high';
  if (score >= 40) return 'is-mid';
  return 'is-low';
}

export function RiskGauge({ score, label, size = 'md' }: RiskGaugeProps) {
  const height = size === 'sm' ? 6 : size === 'lg' ? 14 : 10;
  const cls = band(score);

  return (
    <div className="gauge">
      <div className="gauge-head">
        <span className="gauge-label">{label}</span>
        <span className={`gauge-score ${cls}`}>{Math.round(score)}</span>
      </div>
      <div className="gauge-track" style={{ height }}>
        <div
          className={`gauge-fill ${cls}`}
          style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
        />
      </div>
    </div>
  );
}

export function CompactGauge({ score, inverted = false }: { score: number; inverted?: boolean }) {
  const effective = inverted ? 100 - score : score;
  return (
    <span className="compact-gauge">
      <span
        className={`compact-gauge-fill ${band(effective)}`}
        style={{ width: `${Math.min(100, Math.max(0, effective))}%` }}
      />
    </span>
  );
}

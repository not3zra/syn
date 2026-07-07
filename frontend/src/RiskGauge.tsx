interface RiskGaugeProps {
  score: number;
  label: string;
  size?: 'sm' | 'md' | 'lg';
}

function getColor(score: number): string {
  if (score >= 70) return 'var(--red)';
  if (score >= 40) return 'var(--yellow)';
  return 'var(--green)';
}

export function RiskGauge({ score, label, size = 'md' }: RiskGaugeProps) {
  const height = size === 'sm' ? 6 : size === 'lg' ? 14 : 10;
  const color = getColor(score);

  return (
    <div className="risk-gauge">
      <div className="risk-gauge-header">
        <span className="risk-gauge-label">{label}</span>
        <span
          className="risk-gauge-score"
          style={{ color }}
        >
          {Math.round(score)}
        </span>
      </div>
      <div
        className="risk-gauge-track"
        style={{ height, background: 'var(--border)' }}
      >
        <div
          className="risk-gauge-fill"
          style={{
            width: `${score}%`,
            height: '100%',
            background: color,
            boxShadow: `0 0 8px ${color}40`,
            borderRadius: height / 2,
          }}
        />
      </div>
    </div>
  );
}

export function CompactGauge({ score, color }: { score: number; color?: string }) {
  const c = color || getColor(score);
  return (
    <span className="compact-gauge">
      <span
        className="compact-gauge-fill"
        style={{ width: `${score}%`, background: c }}
      />
    </span>
  );
}

import { useMemo } from 'react';
import type { DecisionResponse } from './types';
import { RiskGauge } from './RiskGauge';
import { FactorBreakdown } from './FactorBreakdown';
import { ExpiryTimer } from './ExpiryTimer';
import { SynMark } from './SynMark';

function formatTimestamp(ts: string): string {
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts;
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZoneName: 'short',
  });
}

function computeOverallRisk(scores: DecisionResponse['factor_scores']): number {
  const { severity, policy, anomaly, data_sensitivity, confidence, tool_trust } = scores;
  return Math.round(
    severity * 0.30 +
    policy * 0.20 +
    anomaly * 0.10 +
    data_sensitivity * 0.15 +
    (100 - confidence) * 0.05 +
    (100 - tool_trust) * 0.20
  );
}

function parseTrigger(trigger: string): string {
  const parts = trigger.split(':');
  if (parts.length >= 3) {
    const [, area, ...details] = parts;
    const areaStr = area.replace(/_/g, ' ');
    const detailStr = details.join(': ').replace(/->/g, ' → ').replace(/\+/g, ', ');
    return `${areaStr}: ${detailStr}`;
  }
  if (parts.length >= 2) return parts[1].replace(/_/g, ' ');
  return trigger;
}

const ICONS: Record<string, string> = { approved: '✓', escalated: '!', blocked: '✕' };

interface TrustReceiptProps {
  data: DecisionResponse;
}

export function TrustReceipt({ data }: TrustReceiptProps) {
  const overallRisk = useMemo(() => computeOverallRisk(data.factor_scores), [data.factor_scores]);
  const isEscalated = data.decision === 'escalated';
  const auditRef = `syn-${new Date(data.timestamp).getTime().toString(36)}`;

  return (
    <div className="receipt">
      <div className="receipt-head">
        <div className="receipt-brand">
          <span className="mark"><SynMark size={18} /></span>
          <span className="title">syn</span>
        </div>
        <span className="receipt-tag">Trust Receipt</span>
      </div>

      <div className={`decision-banner is-${data.decision}`}>
        <span className="icon">{ICONS[data.decision] ?? '·'}</span>
        <span>{data.decision}</span>
      </div>

      {data.simulation && (
        <div className="banner-sim">
          <SynMark size={13} /> Simulation · no side effects
        </div>
      )}

      <div className="receipt-body">
        <div className="receipt-section">
          <div className="kv">
            <span className="kv-key">Action</span>
            <span className="kv-val mono">{data.action_type}</span>
          </div>
          <div className="kv">
            <span className="kv-key">Trigger</span>
            <span className="kv-val mono trigger-text">{parseTrigger(data.trigger)}</span>
          </div>
          {data.regulatory_tier && (
            <div className="kv">
              <span className="kv-key">Regulatory</span>
              <div className="chips">
                <span className="chip chip-tier">{data.regulatory_tier.replace(/_/g, ' ')}</span>
                {data.us_regime_flags.map(f => (
                  <span key={f} className="chip chip-flag">{f}</span>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="receipt-section">
          <div className="gauges">
            <RiskGauge score={overallRisk} label="Action risk" size="lg" />
            <RiskGauge
              score={Math.min(data.session_data.cumulative_severity, 100)}
              label="Session risk"
              size="lg"
            />
          </div>
        </div>

        <div className="receipt-section">
          <FactorBreakdown scores={data.factor_scores} />
        </div>

        {data.explanation && (
          <div className="receipt-section">
            <h3 className="section-title">Explanation</h3>
            <p className="text-block">{data.explanation}</p>
          </div>
        )}

        {data.remediation && (
          <div className="receipt-section">
            <h3 className="section-title">Remediation</h3>
            <p className="text-block muted">{data.remediation}</p>
          </div>
        )}

        {isEscalated && (
          <div className="receipt-section">
            <h3 className="section-title">Rollback plan</h3>
            <p className="text-block muted">{data.rollback_plan || 'Pending human review.'}</p>
            {data.expires_at && <ExpiryTimer expiresAt={data.expires_at} />}
          </div>
        )}
      </div>

      <div className="receipt-foot">
        <div className="foot-row">
          <span className="foot-key">Timestamp</span>
          <span className="foot-val">{formatTimestamp(data.timestamp)}</span>
        </div>
        <div className="foot-row">
          <span className="foot-key">Audit ref</span>
          <span className="foot-val">{auditRef}</span>
        </div>
      </div>
    </div>
  );
}

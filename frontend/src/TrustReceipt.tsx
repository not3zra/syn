import { useMemo } from 'react';
import type { DecisionResponse } from './types';
import { RiskGauge } from './RiskGauge';
import { FactorBreakdown } from './FactorBreakdown';
import { ExpiryTimer } from './ExpiryTimer';

function getDecisionColor(decision: string): { bg: string; border: string; text: string; label: string } {
  switch (decision) {
    case 'approved':
      return { bg: 'var(--green-bg)', border: 'var(--green-border)', text: 'var(--green)', label: 'Approved' };
    case 'escalated':
      return { bg: 'var(--yellow-bg)', border: 'var(--yellow-border)', text: 'var(--yellow)', label: 'Escalated' };
    case 'blocked':
      return { bg: 'var(--red-bg)', border: 'var(--red-border)', text: 'var(--red)', label: 'Blocked' };
    default:
      return { bg: 'var(--blue-bg)', border: 'var(--border-light)', text: 'var(--text-secondary)', label: decision };
  }
}

function formatTimestamp(ts: string): string {
  const d = new Date(ts);
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
    const [, area] = parts;
    return area.replace(/_/g, ' ');
  }
  if (parts.length >= 2) {
    return parts[1].replace(/_/g, ' ');
  }
  return trigger;
}

interface TrustReceiptProps {
  data: DecisionResponse;
}

export function TrustReceipt({ data }: TrustReceiptProps) {
  const style = getDecisionColor(data.decision);
  const overallRisk = useMemo(() => computeOverallRisk(data.factor_scores), [data.factor_scores]);
  const isEscalated = data.decision === 'escalated';

  return (
    <div className="receipt">
      <div className="receipt-header">
        <div className="receipt-brand">
          <span className="receipt-logo">◆</span>
          <span className="receipt-title">syn</span>
        </div>
        <span className="receipt-id">Trust Receipt</span>
      </div>

      <div
        className="decision-badge"
        style={{ background: style.bg, borderColor: style.border, color: style.text }}
      >
        <span className="decision-icon">
          {data.decision === 'approved' ? '✓' : data.decision === 'blocked' ? '✕' : '!'}
        </span>
        <span className="decision-label">{style.label}</span>
      </div>

      <div className="receipt-body">
        <div className="receipt-section">
          <div className="detail-row">
            <span className="detail-label">Action</span>
            <span className="detail-value mono">{data.action_type}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Trigger</span>
            <span className="detail-value mono trigger-text">{parseTrigger(data.trigger)}</span>
          </div>
          {data.regulatory_tier && (
            <div className="detail-row">
              <span className="detail-label">Regulatory</span>
              <div className="badge-group">
                <span className="badge badge-tier">{data.regulatory_tier.replace(/_/g, ' ')}</span>
                {data.us_regime_flags.map(f => (
                  <span key={f} className="badge badge-flag">{f}</span>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="receipt-section">
          <div className="gauges-row">
            <div className="gauge-col">
              <RiskGauge score={overallRisk} label="Action Risk" size="lg" />
            </div>
            <div className="gauge-col">
              <RiskGauge
                score={Math.min(data.session_data.cumulative_severity, 100)}
                label="Session Risk"
                size="lg"
              />
            </div>
          </div>
        </div>

        <div className="receipt-section">
          <FactorBreakdown scores={data.factor_scores} />
        </div>

        {data.explanation && (
          <div className="receipt-section">
            <h3 className="section-title">Explanation</h3>
            <p className="explanation-text">{data.explanation}</p>
          </div>
        )}

        {data.remediation && (
          <div className="receipt-section">
            <h3 className="section-title">Remediation</h3>
            <p className="remediation-text">{data.remediation}</p>
          </div>
        )}

        {isEscalated && (
          <div className="receipt-section">
            <h3 className="section-title">Rollback Plan</h3>
            <p className="remediation-text">
              The action has been escalated for human review. If denied, the action will not be executed.
              Pending approvals auto-expire after 4 hours.
            </p>
            <ExpiryTimer timestamp={data.timestamp} />
          </div>
        )}
      </div>

      <div className="receipt-footer">
        <div className="footer-row">
          <span className="footer-label">Timestamp</span>
          <span className="footer-value mono">{formatTimestamp(data.timestamp)}</span>
        </div>
        <div className="footer-row">
          <span className="footer-label">Audit Ref</span>
          <span className="footer-value mono">
            syn-{data.timestamp ? new Date(data.timestamp).getTime().toString(36) : Date.now().toString(36)}
          </span>
        </div>
      </div>
    </div>
  );
}

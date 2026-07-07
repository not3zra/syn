import { useState, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || '';

interface ToolRule {
  tool_name: string;
  severity_rules: Array<Record<string, number | string | null>>;
  policy_rules: Array<{
    description: string;
    condition: Record<string, string | number>;
    score: number;
  }>;
  data_sensitivity_rules: Array<Record<string, string | number>>;
  tool_trust_tier: string;
  anomaly_lookback: number;
  reasoning: string;
}

interface BootstrapResult {
  schemas: Array<Record<string, unknown>>;
  rules: ToolRule[];
  yaml: string;
  valid: boolean;
  errors: string[];
}

export function BootstrapReview() {
  const [result, setResult] = useState<BootstrapResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editableYaml, setEditableYaml] = useState('');
  const [approved, setApproved] = useState(false);

  const handleIntrospect = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setApproved(false);

    try {
      const res = await fetch(`${API_BASE}/bootstrap/introspect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ manual_schemas: null }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: BootstrapResult & { error?: string } = await res.json();
      if (data.error) throw new Error(data.error);
      setResult(data);
      setEditableYaml(data.yaml);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Introspection failed');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleManual = useCallback(async () => {
    const raw = window.prompt('Paste tool schemas as JSON array:');
    if (!raw) return;

    setLoading(true);
    setError(null);
    setResult(null);
    setApproved(false);

    try {
      const schemas = JSON.parse(raw);
      const res = await fetch(`${API_BASE}/bootstrap/introspect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ manual_schemas: schemas }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: BootstrapResult & { error?: string } = await res.json();
      if (data.error) throw new Error(data.error);
      setResult(data);
      setEditableYaml(data.yaml);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Manual introspection failed');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleApprove = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/bootstrap/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ yaml_content: editableYaml }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data.success) {
        setApproved(true);
      } else {
        setError(data.errors?.join('\n') || 'Validation failed');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Approve failed');
    } finally {
      setLoading(false);
    }
  }, [editableYaml]);

  const handleYamlChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setEditableYaml(e.target.value);
  }, []);

  return (
    <div className="receipt" style={{ maxWidth: '720px' }}>
      <div className="receipt-header">
        <div className="receipt-brand">
          <span className="receipt-logo">◆</span>
          <span className="receipt-title">syn</span>
        </div>
        <span className="receipt-id">Bootstrap Review</span>
      </div>

      <div className="receipt-body">
        <div className="receipt-section">
          <h3 className="section-title">Generate Security Rules</h3>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.5', marginBottom: '8px' }}>
             Introspect MCP tool schemas and generate policy rules via LLM. Review, edit, and approve the result.
          </p>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button className="submit-btn" onClick={handleIntrospect} disabled={loading}>
              {loading ? 'Generating...' : 'Introspect Tools'}
            </button>
            <button
              className="submit-btn"
              onClick={handleManual}
              disabled={loading}
              style={{ background: 'var(--bg-card)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}
            >
              Manual JSON
            </button>
          </div>
        </div>

        {error && (
          <div className="error-msg" style={{ whiteSpace: 'pre-wrap' }}>{error}</div>
        )}

        {result && !result.valid && (
          <div className="error-msg">
            Validation errors:
            {result.errors.map((e, i) => <div key={i}>{e}</div>)}
          </div>
        )}

        {result && result.rules.length > 0 && (
          <>
            <div className="receipt-section">
              <h3 className="section-title">Generated Rules</h3>
              {result.rules.map(rule => (
                <div key={rule.tool_name} style={{
                  background: 'var(--bg-raised)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '12px',
                  marginBottom: '8px',
                  fontSize: '12px',
                }}>
                  <div style={{ fontWeight: '600', marginBottom: '6px', color: 'var(--accent)' }}>
                    {rule.tool_name}
                  </div>
                  <div style={{ color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Trust: {rule.tool_trust_tier} &middot; Lookback: {rule.anomaly_lookback}
                  </div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                    Severity rules: {rule.severity_rules.length} &middot;
                    Policy rules: {rule.policy_rules.length} &middot;
                    Data sensitivity rules: {rule.data_sensitivity_rules.length}
                  </div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '11px', fontStyle: 'italic', marginTop: '4px' }}>
                    {rule.reasoning}
                  </div>
                </div>
              ))}
            </div>

            <div className="receipt-section">
              <h3 className="section-title">Policy YAML (editable)</h3>
              <textarea
                className="input-textarea"
                value={editableYaml}
                onChange={handleYamlChange}
                rows={16}
                spellCheck={false}
                style={{ fontSize: '11px', fontFamily: 'var(--font-sans)' }}
              />
            </div>

            <div className="receipt-section" style={{ flexDirection: 'row', gap: '8px' }}>
              <button
                className="submit-btn"
                onClick={handleApprove}
                disabled={loading || approved}
                style={{ flex: 1 }}
              >
                {approved ? 'Approved ✓' : loading ? 'Writing...' : 'Approve All & Write Config'}
              </button>
            </div>

            {approved && (
              <div style={{
                background: 'var(--green-bg)',
                border: '1px solid var(--green-border)',
                borderRadius: 'var(--radius-sm)',
                padding: '12px',
                color: 'var(--green)',
                fontSize: '13px',
                fontWeight: '600',
                textAlign: 'center',
              }}>
                Policy configuration written successfully.
              </div>
            )}
          </>
        )}

        {loading && !result && (
          <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
            Generating security rules from tool schemas...
          </div>
        )}

        {!result && !loading && !error && (
          <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)', fontSize: '12px' }}>
            Click "Introspect Tools" to auto-detect schemas, or "Manual JSON" to paste them.
          </div>
        )}
      </div>
    </div>
  );
}

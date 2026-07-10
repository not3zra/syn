import { useState, useCallback, useEffect } from 'react';
import { apiFetch } from './api';

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

interface PendingRule {
  id: number;
  tool_name: string;
  proposed_yaml: string;
  schemas_json: string;
  status: 'pending' | 'error';
  error_message: string | null;
  generation_attempts: number;
  created_at: string;
}

function DiffView({ yaml }: { yaml: string }) {
  const lines = yaml.split('\n');
  return (
    <pre style={{
      fontSize: '11px',
      fontFamily: 'var(--font-sans)',
      lineHeight: '1.6',
      overflowX: 'auto',
      whiteSpace: 'pre',
      margin: 0,
    }}>
      {lines.map((line, i) => (
        <div key={i} style={{
          background: line.startsWith('---') || line.startsWith('+++') || line.startsWith('@@')
            ? 'transparent'
            : 'rgba(34, 197, 94, 0.08)',
          padding: '0 8px',
          display: 'flex',
        }}>
          <span style={{ color: 'var(--text-muted)', width: '24px', flexShrink: 0, userSelect: 'none' }}>{i + 1}</span>
          <span style={{ color: 'var(--green)', width: '16px', flexShrink: 0, userSelect: 'none' }}>+</span>
          <span style={{ color: 'var(--text-primary)' }}>{line}</span>
        </div>
      ))}
    </pre>
  );
}

export function BootstrapReview() {
  const [tab, setTab] = useState<'generate' | 'pending'>('generate');
  const [result, setResult] = useState<BootstrapResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editableYaml, setEditableYaml] = useState('');
  const [approved, setApproved] = useState(false);
  const [pendingRules, setPendingRules] = useState<PendingRule[]>([]);
  const [pendingLoading, setPendingLoading] = useState(false);
  const [flashMessage, setFlashMessage] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});

  const fetchPending = useCallback(async (showFlash = false) => {
    setPendingLoading(true);
    try {
      const res = await apiFetch('/bootstrap/pending');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: PendingRule[] = await res.json();
      setPendingRules(data);
      if (showFlash && data.length > 0) {
        setFlashMessage(`${data.length} new rule${data.length > 1 ? 's' : ''} pending review`);
        setTimeout(() => setFlashMessage(null), 5000);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load pending rules');
    } finally {
      setPendingLoading(false);
    }
  }, []);

  useEffect(() => {
    if (tab === 'pending') {
      fetchPending(true);
    }
  }, [tab, fetchPending]);

  const handleIntrospect = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setApproved(false);

    try {
      const res = await apiFetch('/bootstrap/introspect', {
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
      const res = await apiFetch('/bootstrap/introspect', {
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
      const res = await apiFetch('/bootstrap/approve', {
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

  const handleApproveTool = useCallback(async (toolName: string) => {
    setActionLoading(prev => ({ ...prev, [toolName]: true }));
    try {
      const res = await apiFetch(`/bootstrap/approve/${toolName}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reviewed_by: 'demo-admin' }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!data.success) throw new Error(data.error || 'Approve failed');
      setFlashMessage(`Approved rules for "${toolName}"`);
      setTimeout(() => setFlashMessage(null), 3000);
      fetchPending();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Approve failed');
    } finally {
      setActionLoading(prev => ({ ...prev, [toolName]: false }));
    }
  }, [fetchPending]);

  const handleRejectTool = useCallback(async (toolName: string) => {
    setActionLoading(prev => ({ ...prev, [toolName]: true }));
    try {
      const res = await apiFetch(`/bootstrap/reject/${toolName}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reviewed_by: 'demo-admin' }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!data.success) throw new Error(data.error || 'Reject failed');
      setFlashMessage(`Rejected rules for "${toolName}"`);
      setTimeout(() => setFlashMessage(null), 3000);
      fetchPending();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Reject failed');
    } finally {
      setActionLoading(prev => ({ ...prev, [toolName]: false }));
    }
  }, [fetchPending]);

  const handleApproveAll = useCallback(async () => {
    setActionLoading(prev => ({ ...prev, _all: true }));
    try {
      const res = await apiFetch('/bootstrap/approve-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reviewed_by: 'demo-admin' }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!data.success) throw new Error(data.error || 'Approve all failed');
      setFlashMessage(`Approved ${data.approved_count} rule${data.approved_count > 1 ? 's' : ''}`);
      setTimeout(() => setFlashMessage(null), 3000);
      fetchPending();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Approve all failed');
    } finally {
      setActionLoading(prev => ({ ...prev, _all: false }));
    }
  }, [fetchPending]);

  const handleRetry = useCallback(async (rule: PendingRule) => {
    setActionLoading(prev => ({ ...prev, [`retry_${rule.id}`]: true }));
    try {
      const res = await apiFetch(`/bootstrap/retry/${rule.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool_name: rule.tool_name, parameters: {} }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!data.success) throw new Error(data.error || 'Retry failed');
      setFlashMessage(`Retrying generation for "${rule.tool_name}"`);
      setTimeout(() => setFlashMessage(null), 3000);
      fetchPending();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Retry failed');
    } finally {
      setActionLoading(prev => ({ ...prev, [`retry_${rule.id}`]: false }));
    }
  }, [fetchPending]);

  const pendingCount = pendingRules.length;
  const errorCount = pendingRules.filter(r => r.status === 'error').length;

  return (
    <div className="receipt" style={{ maxWidth: '720px' }}>
      <div className="receipt-header">
        <div className="receipt-brand">
          <span className="receipt-logo">◆</span>
          <span className="receipt-title">syn</span>
        </div>
        <span className="receipt-id">Bootstrap Review</span>
      </div>

      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)' }}>
        <button
          onClick={() => setTab('generate')}
          style={{
            flex: 1,
            padding: '12px',
            background: 'none',
            border: 'none',
            color: tab === 'generate' ? 'var(--accent)' : 'var(--text-muted)',
            fontWeight: 600,
            fontSize: '12px',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            cursor: 'pointer',
            borderBottom: tab === 'generate' ? '2px solid var(--accent)' : '2px solid transparent',
            fontFamily: 'var(--font-display)',
          }}
        >
          Generate
        </button>
        <button
          onClick={() => setTab('pending')}
          style={{
            flex: 1,
            padding: '12px',
            background: 'none',
            border: 'none',
            color: tab === 'pending' ? 'var(--accent)' : 'var(--text-muted)',
            fontWeight: 600,
            fontSize: '12px',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            cursor: 'pointer',
            borderBottom: tab === 'pending' ? '2px solid var(--accent)' : '2px solid transparent',
            fontFamily: 'var(--font-display)',
            position: 'relative',
          }}
        >
          Pending Approvals
          {pendingCount > 0 && (
            <span style={{
              position: 'absolute',
              top: '6px',
              right: '8px',
              background: 'var(--accent)',
              color: 'white',
              fontSize: '10px',
              borderRadius: '8px',
              padding: '1px 6px',
              fontWeight: 700,
              lineHeight: '1.4',
            }}>
              {pendingCount}
            </span>
          )}
        </button>
      </div>

      {flashMessage && (
        <div style={{
          margin: '12px 20px 0',
          padding: '10px 12px',
          background: 'var(--accent)',
          color: 'white',
          borderRadius: 'var(--radius-sm)',
          fontSize: '12px',
          fontWeight: 600,
          textAlign: 'center',
        }}>
          {flashMessage}
        </div>
      )}

      {tab === 'generate' && (
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
      )}

      {tab === 'pending' && (
        <div className="receipt-body">
          {error && (
            <div className="error-msg" style={{ whiteSpace: 'pre-wrap' }}>{error}</div>
          )}

          <div className="receipt-section">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 className="section-title">
                Pending Rules
                {pendingCount > 0 && (
                  <span style={{ color: 'var(--text-secondary)', marginLeft: '8px', fontWeight: 400, textTransform: 'none' }}>
                    ({pendingCount} pending{errorCount > 0 ? `, ${errorCount} error` : ''})
                  </span>
                )}
              </h3>
              {pendingCount > 0 && (
                <button
                  className="submit-btn"
                  onClick={handleApproveAll}
                  disabled={actionLoading['_all']}
                  style={{ padding: '6px 12px', fontSize: '11px' }}
                >
                  {actionLoading['_all'] ? 'Approving...' : 'Approve All'}
                </button>
              )}
            </div>
          </div>

          {pendingLoading && (
            <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
              Loading pending rules...
            </div>
          )}

          {!pendingLoading && pendingRules.length === 0 && !error && (
            <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)', fontSize: '12px' }}>
              No rules pending review. Rules appear here when an unknown tool is intercepted and bootstrap generation completes.
            </div>
          )}

          {!pendingLoading && pendingRules.map(rule => (
            <div key={rule.id} style={{
              background: 'var(--bg-raised)',
              borderRadius: 'var(--radius-sm)',
              border: rule.status === 'error' ? '1px solid var(--red-border)' : '1px solid transparent',
              overflow: 'hidden',
            }}>
              <div style={{
                padding: '12px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                borderBottom: '1px solid var(--border)',
              }}>
                <div>
                  <span style={{ fontWeight: 600, color: 'var(--accent)', fontSize: '13px' }}>
                    {rule.tool_name}
                  </span>
                  <span style={{
                    marginLeft: '8px',
                    fontSize: '10px',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    background: rule.status === 'error' ? 'var(--red-bg)' : 'var(--yellow-bg)',
                    color: rule.status === 'error' ? 'var(--red)' : 'var(--yellow)',
                    border: `1px solid ${rule.status === 'error' ? 'var(--red-border)' : 'var(--yellow-border)'}`,
                  }}>
                    {rule.status === 'error' ? 'error' : 'pending'}
                  </span>
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  Attempt {rule.generation_attempts}
                </div>
              </div>

              {rule.status === 'error' && rule.error_message && (
                <div style={{
                  padding: '8px 12px',
                  background: 'var(--red-bg)',
                  borderBottom: '1px solid var(--red-border)',
                  fontSize: '11px',
                  color: 'var(--red)',
                  lineHeight: '1.4',
                }}>
                  {rule.error_message}
                </div>
              )}

              {rule.proposed_yaml && (
                <div style={{
                  padding: '8px 12px',
                  background: 'var(--bg-card)',
                  maxHeight: '200px',
                  overflow: 'auto',
                  borderBottom: '1px solid var(--border)',
                }}>
                  <DiffView yaml={rule.proposed_yaml} />
                </div>
              )}

              <div style={{ padding: '8px 12px', display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
                {rule.status === 'error' ? (
                  <button
                    className="submit-btn"
                    onClick={() => handleRetry(rule)}
                    disabled={actionLoading[`retry_${rule.id}`]}
                    style={{
                      padding: '6px 12px',
                      fontSize: '11px',
                      background: 'var(--bg-card)',
                      color: 'var(--text-primary)',
                      border: '1px solid var(--border)',
                    }}
                  >
                    {actionLoading[`retry_${rule.id}`] ? 'Retrying...' : 'Retry generation'}
                  </button>
                ) : (
                  <>
                    <button
                      className="submit-btn"
                      onClick={() => handleApproveTool(rule.tool_name)}
                      disabled={actionLoading[rule.tool_name]}
                      style={{
                        padding: '6px 12px',
                        fontSize: '11px',
                        background: 'var(--green-bg)',
                        color: 'var(--green)',
                        border: '1px solid var(--green-border)',
                      }}
                    >
                      {actionLoading[rule.tool_name] ? '...' : 'Approve'}
                    </button>
                    <button
                      className="submit-btn"
                      onClick={() => handleRejectTool(rule.tool_name)}
                      disabled={actionLoading[rule.tool_name]}
                      style={{
                        padding: '6px 12px',
                        fontSize: '11px',
                        background: 'var(--red-bg)',
                        color: 'var(--red)',
                        border: '1px solid var(--red-border)',
                      }}
                    >
                      Reject
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}

          {!pendingLoading && pendingRules.length > 0 && (
            <div style={{ textAlign: 'center', padding: '8px' }}>
              <button
                className="submit-btn"
                onClick={() => fetchPending()}
                disabled={pendingLoading}
                style={{
                  padding: '8px 16px',
                  fontSize: '11px',
                  background: 'var(--bg-card)',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border)',
                  width: '100%',
                }}
              >
                Refresh
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
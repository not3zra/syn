import { useState, useCallback, useEffect } from 'react';
import { apiFetch } from './api';
import { BrandMark } from './BrandMark';

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
  status: 'pending' | 'error' | 'generating';
  error_message: string | null;
  generation_attempts: number;
  created_at: string;
}

type DiffRow = { type: 'add' | 'del' | 'ctx'; text: string };

function extractToolBody(yamlStr: string, toolName: string): string {
  const lines = yamlStr.split('\n');
  let capturing = false;
  const body: string[] = [];
  for (const line of lines) {
    const toolMatch = line.match(/^  ([A-Za-z0-9_.-]+):\s*$/);
    if (toolMatch) {
      if (toolMatch[1] === toolName) {
        capturing = true;
      } else if (capturing) {
        break;
      }
      continue;
    }
    if (capturing) body.push(line);
  }
  return body.join('\n');
}

function lineDiff(oldText: string, newText: string): DiffRow[] {
  const a = oldText.split('\n');
  const b = newText.split('\n');
  const n = a.length;
  const m = b.length;
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const rows: DiffRow[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      rows.push({ type: 'ctx', text: a[i] });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      rows.push({ type: 'del', text: a[i] });
      i++;
    } else {
      rows.push({ type: 'add', text: b[j] });
      j++;
    }
  }
  while (i < n) rows.push({ type: 'del', text: a[i++] });
  while (j < m) rows.push({ type: 'add', text: b[j++] });
  return rows;
}

function DiffView({ yaml, toolName, currentYaml }: { yaml: string; toolName?: string; currentYaml: string | null }) {
  const isFullDiff = !toolName;
  const newBody = isFullDiff ? yaml : extractToolBody(yaml, toolName);
  const oldBody = currentYaml ? (isFullDiff ? currentYaml : extractToolBody(currentYaml, toolName)) : '';
  const isNew = !oldBody.trim();
  const rows: DiffRow[] = isNew
    ? yaml.split('\n').map((text) => ({ type: 'add' as const, text }))
    : lineDiff(oldBody, newBody);

  return (
    <div className="yaml-box">
      <div className="diff-legend">
        {isNew
          ? (isFullDiff ? 'All tools are new — entire block will be written' : `New tool — entire block will be added for "${toolName}"`)
          : (isFullDiff ? 'Changes vs current config' : `Changes vs current config for "${toolName}"`)}
      </div>
      {rows.map((row, i) => (
        <div className={`yaml-line is-${row.type}`} key={i}>
          <span className="ln">{i + 1}</span>
          <span className={`sign ${row.type}`}>
            {row.type === 'add' ? '+' : row.type === 'del' ? '-' : ' '}
          </span>
          <span className="txt">{row.text}</span>
        </div>
      ))}
    </div>
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
  const [currentConfigYaml, setCurrentConfigYaml] = useState<string | null>(null);
  const [flashMessage, setFlashMessage] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});
  const [showManualInput, setShowManualInput] = useState(false);
  const [manualInput, setManualInput] = useState('');
  const [editingToolName, setEditingToolName] = useState<string | null>(null);
  const [editYaml, setEditYaml] = useState('');

  const fetchCurrentConfig = useCallback(async () => {
    try {
      const cfg = await apiFetch('/bootstrap/config');
      if (cfg.ok) setCurrentConfigYaml((await cfg.json()).yaml);
    } catch { /* best-effort */ }
  }, []);

  const fetchPending = useCallback(async (showFlash = false) => {
    setPendingLoading(true);
    try {
      const res = await apiFetch('/bootstrap/pending');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: PendingRule[] = await res.json();
      setPendingRules(data);
      await fetchCurrentConfig();
      if (showFlash && data.length > 0) {
        const genCount = data.filter(r => r.status === 'generating').length;
        const pendCount = data.length - genCount;
        let msg = '';
        if (genCount > 0 && pendCount > 0) {
          msg = `${genCount} generating, ${pendCount} ready for review`;
        } else if (genCount > 0) {
          msg = `${genCount} rule${genCount > 1 ? 's' : ''} generating…`;
        } else {
          msg = `${data.length} new rule${data.length > 1 ? 's' : ''} pending review`;
        }
        setFlashMessage(msg);
        setTimeout(() => setFlashMessage(null), 5000);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load pending rules');
    } finally {
      setPendingLoading(false);
    }
  }, [fetchCurrentConfig]);

  useEffect(() => {
    if (tab === 'pending') fetchPending(true);
  }, [tab, fetchPending]);

  const hasGenerating = pendingRules.some(r => r.status === 'generating');

  useEffect(() => {
    if (tab !== 'pending') return;
    if (!hasGenerating) return;
    const id = setInterval(() => fetchPending(), 3000);
    return () => clearInterval(id);
  }, [tab, hasGenerating, fetchPending]);

  /* Cross-tab poll: notify the user even when on the Generate tab */
  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const res = await apiFetch('/bootstrap/pending');
        if (!res.ok) return;
        const data: PendingRule[] = await res.json();
        setPendingRules(data);
        if (tab !== 'pending' && data.some(r => r.status === 'generating')) {
          setFlashMessage('New tool intercepted — generating rules…');
          setTimeout(() => setFlashMessage(null), 5000);
        }
      } catch { /* ignore */ }
    }, 5000);
    return () => clearInterval(id);
  }, [tab]);

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
      fetchCurrentConfig();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Introspection failed');
    } finally {
      setLoading(false);
    }
  }, [fetchCurrentConfig]);

  const handleManualSubmit = useCallback(async () => {
    if (!manualInput.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setApproved(false);
    try {
      const schemas = JSON.parse(manualInput);
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
      setShowManualInput(false);
      setManualInput('');
      fetchCurrentConfig();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Manual introspection failed');
    } finally {
      setLoading(false);
    }
  }, [manualInput, fetchCurrentConfig]);

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
      if (data.success) setApproved(true);
      else setError(data.errors?.join('\n') || 'Validation failed');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Approve failed');
    } finally {
      setLoading(false);
    }
  }, [editableYaml]);

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

  const handleEditSave = useCallback(async (toolName: string) => {
    setActionLoading(prev => ({ ...prev, [`edit_${toolName}`]: true }));
    try {
      const res = await apiFetch(`/bootstrap/pending/${toolName}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ proposed_yaml: editYaml }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!data.success) throw new Error(data.error || 'Save failed');
      setEditingToolName(null);
      setEditYaml('');
      setFlashMessage(`Updated YAML for "${toolName}"`);
      setTimeout(() => setFlashMessage(null), 3000);
      fetchPending();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setActionLoading(prev => ({ ...prev, [`edit_${toolName}`]: false }));
    }
  }, [editYaml, fetchPending]);

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
      <div className="receipt-head">
        <div className="receipt-brand">
          <BrandMark size={18} />
        </div>
        <span className="receipt-tag">Bootstrap Review</span>
      </div>

      <div className="tabs">
        <button className={`tab${tab === 'generate' ? ' active' : ''}`} onClick={() => setTab('generate')}>
          Generate
        </button>
        <button className={`tab${tab === 'pending' ? ' active' : ''}`} onClick={() => setTab('pending')}>
          Pending approvals
          {pendingCount > 0 && <span className="count">{pendingCount}</span>}
        </button>
      </div>

      {flashMessage && <div className="flash">{flashMessage}</div>}

      {tab === 'generate' && (
        <div className="receipt-body">
          <div className="receipt-section">
            <h3 className="section-title">Generate security rules</h3>
            <p className="muted-note">
              Introspect tool schemas and generate policy rules with the LLM. Review, edit, and approve the result.
            </p>
            <div className="btn-row">
              <button className="btn btn-primary" onClick={handleIntrospect} disabled={loading}>
                {loading ? 'Generating…' : 'Introspect tools'}
              </button>
              <button className="btn btn-ghost" onClick={() => setShowManualInput(o => !o)} disabled={loading}>
                {showManualInput ? 'Cancel' : 'Manual JSON'}
              </button>
            </div>

            {showManualInput && (
              <div style={{ marginTop: 8 }}>
                <textarea
                  className="textarea"
                  placeholder="Paste tool schemas as a JSON array of { name, description, parameters } objects…"
                  value={manualInput}
                  onChange={e => setManualInput(e.target.value)}
                  rows={6}
                  spellCheck={false}
                />
                <div className="btn-row" style={{ marginTop: 4 }}>
                  <button className="btn btn-primary btn-sm" onClick={handleManualSubmit} disabled={loading}>
                    {loading ? 'Submitting…' : 'Submit schemas'}
                  </button>
                </div>
              </div>
            )}
          </div>

          {error && <div className="error-msg">{error}</div>}

          {result && !result.valid && (
            <div className="error-msg">
              Validation errors:{'\n'}
              {result.errors.map((e, i) => (
                <span key={i}>{'• '}{e}{'\n'}</span>
              ))}
            </div>
          )}

          {result && result.rules.length > 0 && (
            <>
              <div className="receipt-section">
                <h3 className="section-title">Generated rules</h3>
                {result.rules.map(rule => (
                  <div className="tool-card" key={rule.tool_name}>
                    <div className="tool-card-head">
                      <span className="tool-name">{rule.tool_name}</span>
                      <span className="muted-note">Trust {rule.tool_trust_tier}</span>
                    </div>
                    <div className="tool-meta-row">
                      <span>Lookback {rule.anomaly_lookback}</span>
                      <span>Severity {rule.severity_rules.length}</span>
                      <span>Policy {rule.policy_rules.length}</span>
                      <span>Data {rule.data_sensitivity_rules.length}</span>
                    </div>
                    <div className="rule-desc-list">
                      {rule.policy_rules.length > 0 && (
                        <div className="rule-desc-group">
                          <span className="rule-desc-label">Policy rules</span>
                          {rule.policy_rules.map((pr, idx) => (
                            <div className="rule-desc-item" key={idx}>
                              <span className="rule-desc-bullet">•</span>
                              <span>{pr.description}</span>
                              <span className="rule-desc-score">score {pr.score}</span>
                            </div>
                          ))}
                        </div>
                      )}
                      {rule.data_sensitivity_rules.length > 0 && (
                        <div className="rule-desc-group">
                          <span className="rule-desc-label">Data sensitivity</span>
                          {rule.data_sensitivity_rules.map((ds, idx) => (
                            <div className="rule-desc-item" key={idx}>
                              <span className="rule-desc-bullet">•</span>
                              <span>{String(ds.field)}: {String(ds.pattern)}</span>
                              <span className="rule-desc-score">score {ds.score}</span>
                            </div>
                          ))}
                        </div>
                      )}
                      <div className="yaml-box" style={{ border: 'none', padding: '4px 0', marginTop: 4 }}>
                        {rule.reasoning}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="receipt-section">
                <h3 className="section-title">Diff vs current config</h3>
                <DiffView yaml={editableYaml} currentYaml={currentConfigYaml} />
              </div>

              <div className="receipt-section">
                <h3 className="section-title">Policy YAML (editable)</h3>
                <textarea
                  className="textarea"
                  value={editableYaml}
                  onChange={e => setEditableYaml(e.target.value)}
                  rows={14}
                  spellCheck={false}
                />
              </div>

              <div className="receipt-section">
                <button
                  className="btn btn-primary btn-block"
                  onClick={handleApprove}
                  disabled={loading || approved}
                >
                  {approved ? 'Approved ✓' : loading ? 'Writing…' : 'Approve and write config'}
                </button>
              </div>

              {approved && (
                <div className="flash" style={{ background: 'var(--approved-bg)', color: 'var(--approved)' }}>
                  Policy configuration written successfully.
                </div>
              )}
            </>
          )}

          {loading && !result && <div className="skeleton">Generating security rules from tool schemas…</div>}

          {!result && !loading && !error && (
            <div className="skeleton">Choose “Introspect tools” to auto-detect schemas, or “Manual JSON” to paste them.</div>
          )}
        </div>
      )}

      {tab === 'pending' && (
        <div className="receipt-body">
          {error && <div className="error-msg">{error}</div>}

          <div className="receipt-section">
            <div className="kv">
              <span className="kv-key">Pending rules</span>
              <span className="kv-val">
                {pendingCount} pending{errorCount > 0 ? `, ${errorCount} error` : ''}
              </span>
            </div>
            {pendingCount > 0 && (
              <button className="btn btn-ghost btn-sm" onClick={handleApproveAll} disabled={actionLoading['_all']}>
                {actionLoading['_all'] ? 'Approving…' : 'Approve all'}
              </button>
            )}
          </div>

          {pendingLoading && <div className="skeleton">Loading pending rules…</div>}

          {!pendingLoading && pendingRules.length === 0 && !error && (
            <div className="skeleton">
              No rules pending review. Rules appear here when an unknown tool is intercepted and bootstrap generation completes.<br />
              <span style={{ opacity: 0.6 }}>Note: simulation mode does not trigger bootstrap generation — switch to Live.</span>
            </div>
          )}

          {!pendingLoading && pendingRules.map(rule => (
            <div key={rule.id} className={`tool-card${rule.status === 'error' ? ' is-error' : ''}${rule.status === 'generating' ? ' is-generating' : ''}`}>
              <div className="tool-card-head">
                <div>
                  <span className="tool-name">{rule.tool_name}</span>
                  <span className={`status-pill is-${rule.status}`} style={{ marginLeft: 8 }}>
                    {rule.status === 'generating' ? 'generating…' : rule.status}
                  </span>
                </div>
                <span className="muted-note">Attempt {rule.generation_attempts}</span>
              </div>

              {rule.status === 'generating' && (
                <div className="skeleton" style={{ margin: '8px 0' }}>Generating security rules…</div>
              )}

              {rule.status === 'error' && rule.error_message && (
                <div className="tool-error">{rule.error_message}</div>
              )}

              {rule.status === 'pending' && rule.proposed_yaml && editingToolName === rule.tool_name ? (
                <textarea
                  className="textarea"
                  value={editYaml}
                  onChange={e => setEditYaml(e.target.value)}
                  rows={12}
                  spellCheck={false}
                  style={{ marginBottom: 4 }}
                />
              ) : rule.status === 'pending' && rule.proposed_yaml ? (
                <DiffView yaml={rule.proposed_yaml} toolName={rule.tool_name} currentYaml={currentConfigYaml} />
              ) : null}

              <div className="tool-actions">
                {rule.status === 'generating' ? (
                  <span className="muted-note">Auto-generating…</span>
                ) : rule.status === 'error' ? (
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => handleRetry(rule)}
                    disabled={actionLoading[`retry_${rule.id}`]}
                  >
                    {actionLoading[`retry_${rule.id}`] ? 'Retrying…' : 'Retry generation'}
                  </button>
                ) : editingToolName === rule.tool_name ? (
                  <>
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={() => handleEditSave(rule.tool_name)}
                      disabled={actionLoading[`edit_${rule.tool_name}`]}
                    >
                      {actionLoading[`edit_${rule.tool_name}`] ? 'Saving…' : 'Save'}
                    </button>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => { setEditingToolName(null); setEditYaml(''); }}
                    >
                      Cancel
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      className="btn btn-success btn-sm"
                      onClick={() => handleApproveTool(rule.tool_name)}
                      disabled={actionLoading[rule.tool_name]}
                    >
                      {actionLoading[rule.tool_name] ? '…' : 'Approve'}
                    </button>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => { setEditingToolName(rule.tool_name); setEditYaml(rule.proposed_yaml); }}
                    >
                      Edit
                    </button>
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => handleRejectTool(rule.tool_name)}
                      disabled={actionLoading[rule.tool_name]}
                    >
                      Reject
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}

          {!pendingLoading && pendingRules.length > 0 && (
            <div className="receipt-section">
              <button className="btn btn-ghost btn-block btn-sm" onClick={() => fetchPending()}>
                Refresh
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

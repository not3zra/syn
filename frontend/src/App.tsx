import { useState, useCallback, useEffect } from 'react';
import type { DecisionResponse, ToolInfo } from './types';
import { TrustReceipt } from './TrustReceipt';
import './App.css';

const API_BASE = import.meta.env.VITE_API_BASE || '';

const PRESET_TOOLS: Record<string, Record<string, string>> = {
  'send_payment': { amount: '100', currency: 'USD', recipient: 'alice' },
  'delete_file': { file_path: '/tmp/test.txt' },
  'query_database': { query: 'SELECT * FROM users' },
};

export default function App() {
  const [actionType, setActionType] = useState('send_payment');
  const [parameters, setParameters] = useState('{}');
  const [decision, setDecision] = useState<DecisionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tools, setTools] = useState<ToolInfo[]>([]);

  useEffect(() => {
    fetch(`${API_BASE}/tools`)
      .then(r => r.json())
      .then(setTools)
      .catch(() => {
        setTools([
          { name: 'send_payment', description: 'Send a payment', parameters: { amount: { type: 'number', description: 'Amount' } } },
          { name: 'delete_file', description: 'Delete a file', parameters: { file_path: { type: 'string', description: 'Path' } } },
          { name: 'query_database', description: 'Execute a query', parameters: { query: { type: 'string', description: 'SQL' } } },
        ]);
      });
  }, []);

  const handleToolChange = useCallback((tool: string) => {
    setActionType(tool);
    const preset = PRESET_TOOLS[tool];
    setParameters(JSON.stringify(preset || {}, null, 2));
  }, []);

  const handleSubmit = useCallback(async () => {
    setLoading(true);
    setError(null);
    setDecision(null);

    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(parameters);
    } catch {
      setError('Invalid JSON in parameters');
      setLoading(false);
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/intercept`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action_type: actionType, parameters: parsed }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: DecisionResponse = await res.json();
      setDecision(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed');
    } finally {
      setLoading(false);
    }
  }, [actionType, parameters]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-header">
          <span className="sidebar-logo">◆</span>
          <h1 className="sidebar-title">syn</h1>
          <span className="sidebar-sub">governance</span>
        </div>

        <div className="sidebar-section">
          <label className="input-label">Tool</label>
          <select
            className="input-select"
            value={actionType}
            onChange={e => handleToolChange(e.target.value)}
          >
            {tools.map(t => (
              <option key={t.name} value={t.name}>{t.name}</option>
            ))}
            <option value="unknown_tool">unknown_tool</option>
          </select>
        </div>

        <div className="sidebar-section">
          <label className="input-label">Parameters (JSON)</label>
          <textarea
            className="input-textarea"
            value={parameters}
            onChange={e => setParameters(e.target.value)}
            rows={8}
            spellCheck={false}
          />
        </div>

        <button
          className="submit-btn"
          onClick={handleSubmit}
          disabled={loading}
        >
          {loading ? 'Intercepting...' : 'Intercept Tool Call'}
        </button>

        {error && <div className="error-msg">{error}</div>}
      </aside>

      <main className="main-content">
        {decision ? (
          <TrustReceipt data={decision} />
        ) : (
          <div className="empty-state">
            <div className="empty-icon">◆</div>
            <h2>syn governance</h2>
            <p>Select a tool and parameters, then intercept to see the decision.</p>
          </div>
        )}
      </main>
    </div>
  );
}

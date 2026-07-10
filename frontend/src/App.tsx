import { useState, useCallback, useEffect } from 'react';
import type { DecisionResponse, ToolInfo } from './types';
import { Composer } from './Composer';
import { TrustReceipt } from './TrustReceipt';
import { BootstrapReview } from './BootstrapReview';
import { Timeline } from './Timeline';
import { SynMark } from './SynMark';
import { API_BASE, apiFetch } from './api';
import './App.css';

const AGENT_ID = crypto.randomUUID();

const PRESET_TOOLS: Record<string, Record<string, string>> = {
  send_payment: { amount: '100', currency: 'USD', recipient: 'alice' },
  delete_file: { file_path: '/tmp/test.txt' },
  query_database: { query: 'SELECT * FROM users' },
};

function ConsoleIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M7 9l3 3-3 3M13 15h4" />
    </svg>
  );
}

function BootstrapIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <line x1="4" y1="7" x2="20" y2="7" />
      <line x1="4" y1="12" x2="20" y2="12" />
      <line x1="4" y1="17" x2="20" y2="17" />
      <circle cx="9" cy="7" r="2" fill="var(--surface)" />
      <circle cx="15" cy="12" r="2" fill="var(--surface)" />
      <circle cx="8" cy="17" r="2" fill="var(--surface)" />
    </svg>
  );
}

export default function App() {
  const [view, setView] = useState<'console' | 'bootstrap'>('console');
  const [actionType, setActionType] = useState('send_payment');
  const [parameters, setParameters] = useState('{}');
  const [decision, setDecision] = useState<DecisionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [simulationMode, setSimulationMode] = useState(false);
  const [resetNonce, setResetNonce] = useState(0);

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
    setParameters(JSON.stringify(PRESET_TOOLS[tool] || {}, null, 2));
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
      const res = await apiFetch('/intercept', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action_type: actionType,
          parameters: parsed,
          agent_id: AGENT_ID,
          mode: simulationMode ? 'simulation' : 'live',
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: DecisionResponse = await res.json();
      setDecision(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed');
    } finally {
      setLoading(false);
    }
  }, [actionType, parameters, simulationMode]);

  const handleReset = useCallback(async () => {
    try {
      const res = await apiFetch('/admin/reset', { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setDecision(null);
      setError(null);
      setResetNonce(n => n + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Reset failed');
    }
  }, []);

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-brand">
          <SynMark size={20} />
          <span className="wordmark">syn</span>
          <span className="wordmark-sub">governance</span>
        </div>
        <div className="topbar-spacer" />
        <div className="topbar-status">
          <span className="dot" />
          <span>demo</span>
          <span className="mono">agent {AGENT_ID.slice(0, 8)}</span>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={handleReset}>Reset demo</button>
      </header>

      <nav className="rail" aria-label="Primary">
        <div className="rail-logo"><SynMark size={22} /></div>
        <div className="rail-nav">
          <button
            className={`rail-item${view === 'console' ? ' active' : ''}`}
            onClick={() => setView('console')}
          >
            <ConsoleIcon />
            Console
          </button>
          <button
            className={`rail-item${view === 'bootstrap' ? ' active' : ''}`}
            onClick={() => setView('bootstrap')}
          >
            <BootstrapIcon />
            Bootstrap
          </button>
        </div>
      </nav>

      <main className="stage">
        <div className="stage-inner">
          {view === 'console' ? (
            <>
              <Composer
                tools={tools}
                actionType={actionType}
                parameters={parameters}
                simulationMode={simulationMode}
                loading={loading}
                onToolChange={handleToolChange}
                onParamsChange={setParameters}
                onModeChange={setSimulationMode}
                onSubmit={handleSubmit}
              />
              {error && <div className="error-msg">{error}</div>}
              {decision ? (
                <TrustReceipt data={decision} />
              ) : (
                <div className="empty">
                  <div className="empty-mark"><SynMark size={40} /></div>
                  <h2>Govern a tool call</h2>
                  <p>Pick a tool and parameters, then intercept to see the decision, its exact trigger, and the full audit trail.</p>
                </div>
              )}
            </>
          ) : (
            <BootstrapReview />
          )}
        </div>
      </main>

      <Timeline refreshKey={resetNonce} />
    </div>
  );
}

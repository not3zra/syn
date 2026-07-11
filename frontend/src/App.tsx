import { useState, useCallback, useEffect } from 'react';
import type { DecisionResponse, ToolInfo } from './types';
import { Composer } from './Composer';
import { TrustReceipt } from './TrustReceipt';
import { BootstrapReview } from './BootstrapReview';
import { Timeline } from './Timeline';
import { BrandMark } from './BrandMark';
import { ResetGlyph } from './icons';
import { API_BASE, apiFetch } from './api';
import './App.css';

const AGENT_ID = crypto.randomUUID();

const PRESET_TOOLS: Record<string, Record<string, unknown>> = {
  send_payment: { amount: 100, currency: 'USD', recipient: 'alice' },
  delete_file: { file_path: '/tmp/test.txt' },
  query_database: { query: 'SELECT * FROM users' },
};

function EmptyState() {
  return (
    <div className="empty">
      <div className="empty-glyph"><BrandMark size={34} /></div>
      <h2>Intercept a tool call</h2>
      <p>
        Pick a tool and its parameters on the left, then intercept. syn scores the action,
        shows the exact trigger it fired on, and writes the decision to the audit trail.
      </p>
      <ul className="empty-points">
        <li>Approved, escalated, or blocked in a single pass</li>
        <li>Six deterministic risk factors, no black box</li>
        <li>Session patterns correlated across the agent</li>
      </ul>
    </div>
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
  const [loadingTools, setLoadingTools] = useState(true);
  const [simulationMode, setSimulationMode] = useState(false);
  const [refreshNonce, setRefreshNonce] = useState(0);
  const [isMobile, setIsMobile] = useState(false);
  const [mobileSubview, setMobileSubview] = useState<'intercept' | 'receipt' | 'timeline'>('intercept');

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 979px)');
    setIsMobile(mq.matches);
    const handler = (e: MediaQueryListEvent) => {
      setIsMobile(e.matches);
      setMobileSubview('receipt');
    };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  useEffect(() => {
    fetch(`${API_BASE}/tools`)
      .then(r => r.json())
      .then(t => { setTools(t); setLoadingTools(false); })
      .catch(() => {
        setTools([
          { name: 'send_payment', description: 'Send a payment', parameters: { amount: { type: 'number', description: 'Amount' } } },
          { name: 'delete_file', description: 'Delete a file', parameters: { file_path: { type: 'string', description: 'Path' } } },
          { name: 'query_database', description: 'Execute a query', parameters: { query: { type: 'string', description: 'SQL' } } },
        ]);
        setLoadingTools(false);
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
      setMobileSubview('receipt');
      setRefreshNonce(n => n + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed');
    } finally {
      setLoading(false);
    }
  }, [actionType, parameters, simulationMode]);

  const handleNewCall = useCallback(() => {
    setDecision(null);
    setError(null);
    setMobileSubview('intercept');
  }, []);

  const handleReset = useCallback(async () => {
    try {
      const res = await apiFetch('/admin/reset', { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setDecision(null);
      setError(null);
      setMobileSubview('intercept');
      setRefreshNonce(n => n + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Reset failed');
    }
  }, []);

  return (
    <div className={`app${view === 'bootstrap' ? ' app--bootstrap' : ''}${isMobile && view === 'console' ? ' app--mobile-console' : ''}`}>
      <header className="topbar">
<BrandMark size={26} />
        <span className="wordmark-sub">governance</span>
        <nav className="console-nav" aria-label="Views">
          <button
            className={`nav-link${view === 'console' ? ' active' : ''}`}
            onClick={() => setView('console')}
          >
            Console
          </button>
          <button
            className={`nav-link${view === 'bootstrap' ? ' active' : ''}`}
            onClick={() => setView('bootstrap')}
          >
            Bootstrap
          </button>
        </nav>
        <div className="topbar-spacer" />
        <div className="topbar-status">
          <span className="dot" />
          <span>demo</span>
          <span className="mono">agent {AGENT_ID.slice(0, 8)}</span>
        </div>
        {isMobile && decision ? (
          <button className="btn btn-ghost btn-sm" onClick={handleNewCall}>
            <ResetGlyph /> New call
          </button>
        ) : (
          <button className="btn btn-ghost btn-sm" onClick={handleReset}>
            <ResetGlyph /> <span className="reset-text">Reset demo</span>
          </button>
        )}
      </header>

      {view === 'console' ? (
        isMobile ? (
          <>
            <nav className="mobile-subnav">
              {decision ? (
                <>
                  <button className={mobileSubview === 'receipt' ? 'active' : ''} onClick={() => setMobileSubview('receipt')}>Receipt</button>
                  <button className={mobileSubview === 'timeline' ? 'active' : ''} onClick={() => setMobileSubview('timeline')}>Audit trail</button>
                </>
              ) : (
                <>
                  <button className={mobileSubview === 'intercept' ? 'active' : ''} onClick={() => setMobileSubview('intercept')}>Intercept</button>
                  <button className={mobileSubview === 'timeline' ? 'active' : ''} onClick={() => setMobileSubview('timeline')}>Audit trail</button>
                </>
              )}
            </nav>
            <main className="output" style={mobileSubview === 'timeline' ? { padding: 0 } : undefined}>
              {error && <div className="error-msg">{error}</div>}
              {!decision && mobileSubview === 'intercept' && (
                <p className="mobile-intro">syn scores each action against six risk factors and checks for dangerous session patterns before approving, escalating, or blocking.</p>
              )}
              {decision ? (
                mobileSubview === 'receipt' ? <TrustReceipt data={decision} /> : <Timeline refreshKey={refreshNonce} />
              ) : (
                mobileSubview === 'intercept' ? (
                  <Composer
                    tools={tools}
                    actionType={actionType}
                    parameters={parameters}
                    simulationMode={simulationMode}
                    loading={loading}
                    loadingTools={loadingTools}
                    onToolChange={handleToolChange}
                    onParamsChange={setParameters}
                    onModeChange={setSimulationMode}
                    onSubmit={handleSubmit}
                  />
                ) : <Timeline refreshKey={refreshNonce} />
              )}
            </main>
          </>
        ) : (
          <>
            <aside className="composer-pane">
              <Composer
                tools={tools}
                actionType={actionType}
                parameters={parameters}
                simulationMode={simulationMode}
                loading={loading}
                loadingTools={loadingTools}
                onToolChange={handleToolChange}
                onParamsChange={setParameters}
                onModeChange={setSimulationMode}
                onSubmit={handleSubmit}
              />
            </aside>
            <main className="output">
              <div className="output-main">
                {error && <div className="error-msg">{error}</div>}
                {decision ? <TrustReceipt data={decision} /> : <EmptyState />}
              </div>
            </main>
            <aside className="timeline-col">
              <Timeline refreshKey={refreshNonce} />
            </aside>
          </>
        )
      ) : (
        <main className="output output--full">
          <div className="output-inner">
            <BootstrapReview />
          </div>
        </main>
      )}
    </div>
  );
}

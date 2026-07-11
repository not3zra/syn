import { useState, useEffect, useCallback } from 'react';
import { apiFetch } from './api';

interface TimelineEntry {
  decision: 'approved' | 'escalated' | 'blocked' | string;
  action_type: string;
  agent_id: string;
  created_at: string;
  trigger?: string;
  reason?: string;
  entry?: Record<string, unknown>;
}

type Filter = 'all' | 'approved' | 'escalated' | 'blocked';

function shortId(id: string): string {
  if (!id) return '—';
  return id.slice(0, 8);
}

function formatTime(ts: string): string {
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts;
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

const FILTERS: Filter[] = ['all', 'approved', 'escalated', 'blocked'];

export function Timeline({ refreshKey = 0 }: { refreshKey?: number }) {
  const [entries, setEntries] = useState<TimelineEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<Filter>('all');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch('/timeline');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: TimelineEntry[] = await res.json();
      setEntries(data);
    } catch {
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  const visible = entries.filter(e => filter === 'all' || e.decision === filter);

  return (
    <section className="timeline-panel" aria-label="Audit trail">
      <header className="panel-head">
        <div className="panel-title-row">
          <span className="panel-title">Audit trail</span>
          <span className="panel-meta">
            <span className="panel-live"><span className="live-dot" />live</span>
            <span className="mono">{entries.length}</span>
          </span>
        </div>
        <div className="panel-filters">
          {FILTERS.map(f => (
            <button
              key={f}
              className={`filter-chip${filter === f ? ' active' : ''}`}
              onClick={() => setFilter(f)}
            >
              {f}
            </button>
          ))}
        </div>
      </header>
      <div className="panel-body">
        {loading ? (
          <div className="skeleton" style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: 20 }}>
            <div className="skel-line md" />
            <div className="skel-line lg" />
            <div className="skel-line md" style={{ width: '50%' }} />
          </div>
        ) : visible.length === 0 ? (
          <div className="skeleton">No decisions yet. Intercept a tool call to begin the trail.</div>
        ) : (
          <div className="timeline">
            {visible.map((e, i) => (
              <div className="timeline-item" key={`${e.created_at}-${i}`}>
                <span className={`timeline-node is-${e.decision}`} />
                <div className="timeline-card">
                  <div className="tl-top">
                    <span className="tl-action">{e.action_type}</span>
                    <span className={`tl-badge is-${e.decision}`}>{e.decision}</span>
                  </div>
                  <div className="tl-meta">
                    <span>{formatTime(e.created_at)}</span>
                    <span title={e.agent_id}>agent {shortId(e.agent_id)}</span>
                  </div>
                  {e.trigger && <div className="tl-trigger">{e.trigger}</div>}
                  {e.reason && <div className="tl-reason">{e.reason}</div>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

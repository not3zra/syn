import { useState, useEffect, useCallback } from 'react';
import { apiFetch } from './api';

interface TimelineEntry {
  decision: 'approved' | 'escalated' | 'blocked' | string;
  action_type: string;
  agent_id: string;
  created_at: string;
  trigger?: string;
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
    <aside className="panel">
      <div className="panel-head">
        <span className="panel-title">Audit Timeline</span>
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
      </div>
      <div className="panel-body">
        {loading ? (
          <div className="skeleton">Loading audit history…</div>
        ) : visible.length === 0 ? (
          <div className="skeleton">No decisions yet. Intercept a tool call to begin the trail.</div>
        ) : (
          <div className="timeline">
            {visible.map((e, i) => (
              <div className="timeline-item" key={`${e.created_at}-${i}`}>
                <span className={`timeline-node is-${e.decision}`} />
                <div className="timeline-card">
                  <div className="tl-action">{e.action_type}</div>
                  <div className="tl-meta">
                    <span className={`tl-badge is-${e.decision}`}>{e.decision}</span>
                    <span>{formatTime(e.created_at)}</span>
                    <span title={e.agent_id}>agent {shortId(e.agent_id)}</span>
                  </div>
                  {e.trigger && <div className="tl-trigger">{e.trigger}</div>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}

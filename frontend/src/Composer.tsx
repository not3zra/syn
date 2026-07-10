import type { ToolInfo } from './types';

interface ComposerProps {
  tools: ToolInfo[];
  actionType: string;
  parameters: string;
  simulationMode: boolean;
  loading: boolean;
  onToolChange: (tool: string) => void;
  onParamsChange: (value: string) => void;
  onModeChange: (sim: boolean) => void;
  onSubmit: () => void;
}

export function Composer({
  tools,
  actionType,
  parameters,
  simulationMode,
  loading,
  onToolChange,
  onParamsChange,
  onModeChange,
  onSubmit,
}: ComposerProps) {
  return (
    <section className="composer" aria-label="Intercept a tool call">
      <h2 className="composer-title">Intercept tool call</h2>
      <p className="composer-intro">
        syn scores this action against six risk factors and writes the decision to the audit trail.
      </p>

      <div className="seg" role="group" aria-label="Runtime mode">
        <button
          type="button"
          className={`seg-btn${!simulationMode ? ' active' : ''}`}
          onClick={() => onModeChange(false)}
        >
          Live
        </button>
        <button
          type="button"
          className={`seg-btn${simulationMode ? ' active' : ''}`}
          onClick={() => onModeChange(true)}
        >
          Simulation
        </button>
      </div>

      <div className="field">
        <label className="field-label" htmlFor="tool-select">Tool</label>
        <select
          id="tool-select"
          className="input"
          value={actionType}
          onChange={e => onToolChange(e.target.value)}
        >
          {tools.map(t => (
            <option key={t.name} value={t.name}>{t.name}</option>
          ))}
          <option value="unknown_tool">unknown_tool</option>
        </select>
      </div>

      <div className="field">
        <label className="field-label" htmlFor="params">Parameters (JSON)</label>
        <textarea
          id="params"
          className="textarea"
          value={parameters}
          onChange={e => onParamsChange(e.target.value)}
          spellCheck={false}
          rows={8}
        />
      </div>

      <button type="button" className="btn btn-primary btn-block" onClick={onSubmit} disabled={loading}>
        {loading ? 'Intercepting…' : 'Intercept tool call'}
      </button>
    </section>
  );
}

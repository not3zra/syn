export interface FactorScores {
  severity: number;
  policy: number;
  anomaly: number;
  data_sensitivity: number;
  confidence: number;
  tool_trust: number;
}

export interface SessionData {
  session_id: string | null;
  cumulative_severity: number;
  pattern_matched: boolean;
}

export interface DecisionResponse {
  decision: 'approved' | 'escalated' | 'blocked';
  trigger: string;
  factor_scores: FactorScores;
  session_data: SessionData;
  regulatory_tier: string;
  us_regime_flags: string[];
  action_type: string;
  parameters_abstracted: Record<string, string>;
  timestamp: string;
  explanation?: string;
  remediation?: string;
  simulation?: boolean;
  rollback_plan?: string;
  expires_at?: string;
}

export interface ToolInfo {
  name: string;
  description: string;
  parameters: Record<string, { type: string; description: string }>;
}

const STORAGE_KEY = 'syn_decision_';

export function saveDecision(key: string, decision: DecisionResponse) {
  localStorage.setItem(STORAGE_KEY + key, JSON.stringify(decision));
}

export function loadDecision(key: string): DecisionResponse | null {
  const raw = localStorage.getItem(STORAGE_KEY + key);
  return raw ? JSON.parse(raw) : null;
}

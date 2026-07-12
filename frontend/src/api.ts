const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/+$/, '');

const DEMO_TOKEN = import.meta.env.VITE_DEMO_TOKEN || '';

export { API_BASE };

function withDemoToken(headers?: HeadersInit): HeadersInit | undefined {
  if (!DEMO_TOKEN) return headers;
  return { ...(headers as Record<string, string> | undefined), 'X-Demo-Token': DEMO_TOKEN };
}

export function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers: withDemoToken(init.headers),
  });
}

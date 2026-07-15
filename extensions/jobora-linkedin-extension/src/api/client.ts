/**
 * Jobora API client for the extension background service worker.
 *
 * Tokens are stored in chrome.storage.local (NOT localStorage — that belongs to
 * the LinkedIn page). All fetch calls are made from the service worker context,
 * which bypasses CORS for hosts declared in host_permissions.
 *
 * The base URL is read from chrome.storage.local so it can be changed without
 * rebuilding the extension (useful for local dev vs production).
 */
import type { StoredAuth } from '../types/job';

// Production backend. Can be overridden via chrome.storage.local `jobora_api_base`
// (the "Server settings" section in the popup) for local dev.
// Baked in at build time (build.mjs vite `define`). Defaults to production;
// override for local dev with `JOBORA_API_BASE=http://localhost:8000/api npm run build`.
const DEFAULT_BASE =
  typeof __JOBORA_API_BASE__ !== 'undefined'
    ? __JOBORA_API_BASE__
    : 'https://jobara-api.onrender.com/api';

// ── Storage helpers ────────────────────────────────────────────────────────────

export async function getBaseUrl(): Promise<string> {
  const { jobora_api_base } = await chrome.storage.local.get('jobora_api_base');
  return (jobora_api_base as string | undefined) || DEFAULT_BASE;
}

export async function getAuth(): Promise<StoredAuth | null> {
  const { jobora_auth } = await chrome.storage.local.get('jobora_auth');
  return (jobora_auth as StoredAuth | undefined) ?? null;
}

export async function setAuth(auth: StoredAuth): Promise<void> {
  await chrome.storage.local.set({ jobora_auth: auth });
}

export async function clearAuth(): Promise<void> {
  await chrome.storage.local.remove('jobora_auth');
}

function expiresAt(accessToken: string): number {
  try {
    const payload = JSON.parse(atob(accessToken.split('.')[1]));
    return (payload.exp as number) * 1000;
  } catch {
    return 0;
  }
}

// ── Token refresh ──────────────────────────────────────────────────────────────

let _refreshInFlight: Promise<string> | null = null;

async function _doRefresh(refreshToken: string): Promise<string> {
  const base = await getBaseUrl();
  const res = await fetch(`${base}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!res.ok) throw new Error('Refresh failed');
  const data = await res.json() as { access_token: string; refresh_token?: string };
  const now = Date.now();
  await setAuth({
    access_token: data.access_token,
    refresh_token: data.refresh_token ?? refreshToken,
    expires_at: expiresAt(data.access_token) || now + 55 * 60 * 1000,
  });
  return data.access_token;
}

async function getValidToken(): Promise<string> {
  const auth = await getAuth();
  if (!auth) throw new Error('Not authenticated');
  // Proactively refresh if token expires in < 5 min
  if (Date.now() > auth.expires_at - 5 * 60 * 1000) {
    if (!_refreshInFlight) {
      _refreshInFlight = _doRefresh(auth.refresh_token).finally(() => {
        _refreshInFlight = null;
      });
    }
    return _refreshInFlight;
  }
  return auth.access_token;
}

// ── Core request ───────────────────────────────────────────────────────────────

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<T> {
  const base = await getBaseUrl();
  const token = await getValidToken();
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
  };
  let payload: string | undefined;
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(options.body);
  }

  let res = await fetch(`${base}${path}`, {
    method: options.method ?? 'GET',
    headers,
    body: payload,
  });

  // One silent retry after token refresh on 401
  if (res.status === 401) {
    const auth = await getAuth();
    if (auth) {
      try {
        const newToken = await _doRefresh(auth.refresh_token);
        res = await fetch(`${base}${path}`, {
          method: options.method ?? 'GET',
          headers: { ...headers, Authorization: `Bearer ${newToken}` },
          body: payload,
        });
      } catch {
        await clearAuth();
        throw new Error('Session expired. Please sign in again.');
      }
    }
  }

  if (res.status === 204) return null as T;

  const text = await res.text();
  let data: unknown;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }

  if (!res.ok) {
    const d = data as Record<string, unknown> | null;
    const msg = (d?.error ?? d?.detail ?? 'Request failed') as string;
    throw new Error(Array.isArray(msg) ? (msg[0] as { msg: string }).msg : msg);
  }
  return data as T;
}

// ── Public API ─────────────────────────────────────────────────────────────────

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) => request<T>(path, { method: 'POST', body }),
  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};

// ── Auth helpers ───────────────────────────────────────────────────────────────

export async function login(email: string, password: string) {
  const base = await getBaseUrl();
  const loginUrl = `${base}/auth/login`;
  console.log('[Jobora] login →', loginUrl);   // visible in SW DevTools → inspect SW
  const res = await fetch(loginUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json() as {
    access_token: string;
    refresh_token: string;
    error?: string;
    detail?: string;
  };
  if (!res.ok) throw new Error((data.error ?? data.detail ?? 'Login failed') as string);

  await setAuth({
    access_token: data.access_token,
    refresh_token: data.refresh_token,
    expires_at: expiresAt(data.access_token) || Date.now() + 55 * 60 * 1000,
  });
  return data;
}

export async function logout() {
  try {
    await api.post('/auth/logout', {});
  } finally {
    await clearAuth();
  }
}

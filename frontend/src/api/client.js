// Thin fetch wrapper that attaches the JWT and normalises errors.
// API base: same-origin "/api" by default (works behind the nginx proxy / Vite
// dev proxy). For split-host deploys (SPA and API on different domains), set
// VITE_API_BASE_URL at build time, e.g. "https://api.jobara.com/api".
const BASE = import.meta.env.VITE_API_BASE_URL || "/api";

export { BASE };

// --- Token helpers -----------------------------------------------------------

export function getToken() {
  return localStorage.getItem("jobora_token") || "";
}

export function setToken(token) {
  if (token) localStorage.setItem("jobora_token", token);
  else localStorage.removeItem("jobora_token");
}

export function getRefreshToken() {
  return localStorage.getItem("jobora_refresh_token") || "";
}

export function setRefreshToken(token) {
  if (token) localStorage.setItem("jobora_refresh_token", token);
  else localStorage.removeItem("jobora_refresh_token");
}

// Decode the expiry from a JWT without verifying (client-side, no secret).
// Returns the epoch-seconds `exp` claim, or 0 if unparseable.
export function tokenExp(token) {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.exp || 0;
  } catch {
    return 0;
  }
}

// --- Refresh logic -----------------------------------------------------------

// Singleton in-flight refresh promise so concurrent 401 responses only
// trigger one /auth/refresh call instead of N simultaneous ones.
let _refreshPromise = null;

async function _doRefresh() {
  const rt = getRefreshToken();
  if (!rt) throw new Error("No refresh token");
  const res = await fetch(`${BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: rt }),
  });
  if (!res.ok) throw new Error("Refresh failed");
  const data = await res.json();
  setToken(data.access_token);
  if (data.refresh_token) setRefreshToken(data.refresh_token);
  return data.access_token;
}

export async function attemptRefresh() {
  if (!_refreshPromise) {
    _refreshPromise = _doRefresh().finally(() => { _refreshPromise = null; });
  }
  return _refreshPromise;
}

// --- Core request ------------------------------------------------------------

async function request(path, { method = "GET", body, isForm = false } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let payload = body;
  if (body && !isForm) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  let res = await fetch(`${BASE}${path}`, { method, headers, body: payload });

  // On 401, attempt a silent token refresh and retry the original request once.
  // Skip if this IS the refresh call (avoid infinite loop).
  if (res.status === 401 && path !== "/auth/refresh" && getRefreshToken()) {
    try {
      const newToken = await attemptRefresh();
      const retryHeaders = { ...headers, Authorization: `Bearer ${newToken}` };
      res = await fetch(`${BASE}${path}`, { method, headers: retryHeaders, body: payload });
    } catch {
      // Refresh failed — clear both tokens so the app redirects to login.
      setToken("");
      setRefreshToken("");
      throw new Error("Session expired. Please sign in again.");
    }
  }

  if (res.status === 204) return null;

  let data = null;
  const text = await res.text();
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!res.ok) {
    const detail =
      (data && (data.error || data.detail)) ||
      (typeof data === "string" ? data : "Request failed");
    throw new Error(Array.isArray(detail) ? detail[0]?.msg || "Invalid input" : detail);
  }
  return data;
}

export const api = {
  get: (p) => request(p),
  post: (p, body) => request(p, { method: "POST", body }),
  put: (p, body) => request(p, { method: "PUT", body }),
  patch: (p, body) => request(p, { method: "PATCH", body }),
  del: (p) => request(p, { method: "DELETE" }),
  upload: (p, file) => {
    const fd = new FormData();
    fd.append("file", file);
    return request(p, { method: "POST", body: fd, isForm: true });
  },
  postForm: (p, fd) => request(p, { method: "POST", body: fd, isForm: true }),
};

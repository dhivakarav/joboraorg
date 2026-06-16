// Thin fetch wrapper that attaches the JWT and normalises errors.
// API base: same-origin "/api" by default (works behind the nginx proxy / Vite
// dev proxy). For split-host deploys (SPA and API on different domains), set
// VITE_API_BASE_URL at build time, e.g. "https://api.jobara.com/api".
const BASE = import.meta.env.VITE_API_BASE_URL || "/api";

export { BASE };

export function getToken() {
  return localStorage.getItem("jobora_token") || "";
}

export function setToken(token) {
  if (token) localStorage.setItem("jobora_token", token);
  else localStorage.removeItem("jobora_token");
}

async function request(path, { method = "GET", body, isForm = false } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let payload = body;
  if (body && !isForm) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const res = await fetch(`${BASE}${path}`, { method, headers, body: payload });

  if (res.status === 204) return null;

  let data = null;
  const text = await res.text();
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!res.ok) {
    // Backend error envelope is {error, request_id}; older paths use {detail}.
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
  // Multipart POST with arbitrary fields + optional files (FormData built by caller).
  postForm: (p, fd) => request(p, { method: "POST", body: fd, isForm: true }),
};

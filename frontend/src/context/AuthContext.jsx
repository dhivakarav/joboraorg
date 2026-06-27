import { createContext, useContext, useEffect, useRef, useState } from "react";
import {
  api,
  setToken,
  getToken,
  setRefreshToken,
  getRefreshToken,
  tokenExp,
  attemptRefresh,
} from "../api/client";

const AuthContext = createContext(null);

// Proactively refresh the access token 5 minutes before it expires so the
// user never hits an in-flight 401 from a naturally-expiring token.
const REFRESH_BEFORE_EXPIRY_MS = 5 * 60 * 1000;

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const refreshTimerRef = useRef(null);

  function _scheduleProactiveRefresh(accessToken) {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    const exp = tokenExp(accessToken);
    if (!exp) return;
    const msUntilRefresh = exp * 1000 - Date.now() - REFRESH_BEFORE_EXPIRY_MS;
    if (msUntilRefresh <= 0) return;
    refreshTimerRef.current = setTimeout(async () => {
      try {
        await attemptRefresh();
        const me = await api.get("/auth/me");
        setUser(me);
        _scheduleProactiveRefresh(getToken());
      } catch {
        setToken("");
        setRefreshToken("");
        setUser(null);
      }
    }, msUntilRefresh);
  }

  async function refresh() {
    if (!getToken() && !getRefreshToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      // If access token is present, try it directly first.
      if (getToken()) {
        const me = await api.get("/auth/me");
        setUser(me);
        _scheduleProactiveRefresh(getToken());
      } else {
        throw new Error("no access token");
      }
    } catch {
      // Access token missing or rejected — try the refresh token.
      if (getRefreshToken()) {
        try {
          await attemptRefresh();
          const me = await api.get("/auth/me");
          setUser(me);
          _scheduleProactiveRefresh(getToken());
        } catch {
          setToken("");
          setRefreshToken("");
          setUser(null);
        }
      } else {
        setToken("");
        setUser(null);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    return () => {
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function login(email, password) {
    const res = await api.post("/auth/login", { email, password });
    setToken(res.access_token);
    if (res.refresh_token) setRefreshToken(res.refresh_token);
    await refresh();
    return res;
  }

  async function logout() {
    // Revoke all tokens server-side (bumps token_version) so even a stolen
    // access token becomes invalid immediately, not just after it expires.
    try {
      if (getToken()) await api.post("/auth/logout", {});
    } catch {
      // Best-effort — clear locally even if the server call fails.
    }
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    setToken("");
    setRefreshToken("");
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refresh, setUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

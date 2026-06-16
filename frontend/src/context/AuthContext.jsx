import { createContext, useContext, useEffect, useState } from "react";
import { api, setToken, getToken } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api.get("/auth/me");
      setUser(me);
    } catch {
      setToken("");
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function login(email, password) {
    const res = await api.post("/auth/login", { email, password });
    setToken(res.access_token);
    await refresh();
    return res;
  }

  function logout() {
    setToken("");
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

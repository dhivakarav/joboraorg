import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const res = await login(email, password);
      navigate(res.is_admin ? "/admin/dashboard" : "/app/dashboard");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title="Welcome back" subtitle="Sign in to your Jobora account">
      <form onSubmit={submit} className="space-y-4">
        {error && <div className="badge border-danger/40 text-danger w-full justify-center py-2">{error}</div>}
        <div>
          <label className="label">Email</label>
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="label !mb-0">Password</label>
            <Link to="/forgot-password" className="text-xs text-muted hover:text-white underline underline-offset-2">
              Forgot password?
            </Link>
          </div>
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        <button className="btn-primary w-full" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-muted">
        No account?{" "}
        <Link to="/register" className="text-white underline underline-offset-4">
          Create one
        </Link>
      </p>
    </AuthShell>
  );
}

export function AuthShell({ title, subtitle, children }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-bg px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="text-4xl font-extrabold tracking-tight">Jobora</div>
          <div className="text-sm text-muted mt-1">Auto Job Applier</div>
        </div>
        <div className="card-elevated p-8">
          <h1 className="text-xl font-semibold">{title}</h1>
          <p className="text-sm text-muted mb-6">{subtitle}</p>
          {children}
        </div>
      </div>
    </div>
  );
}

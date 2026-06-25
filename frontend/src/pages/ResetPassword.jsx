import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { AuthShell } from "./Login";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [token, setToken] = useState(params.get("token") || "");
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    if (pw !== confirm) {
      setError("Passwords don't match");
      return;
    }
    if (pw.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }
    setBusy(true);
    try {
      await api.post("/auth/reset-password", { token, new_password: pw });
      setDone(true);
      setTimeout(() => navigate("/login"), 1800);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title="Set a new password" subtitle="Choose a strong password you'll remember">
      {done ? (
        <div className="text-center space-y-4">
          <div className="badge border-success/40 text-success w-full justify-center py-2">
            Password updated — redirecting to sign in…
          </div>
          <Link to="/login" className="btn-primary w-full">
            Go to sign in
          </Link>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          {error && (
            <div className="badge border-danger/40 text-danger w-full justify-center py-2">{error}</div>
          )}
          {!params.get("token") && (
            <div>
              <label className="label">Reset token</label>
              <input
                className="input"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Paste your reset token"
                required
              />
            </div>
          )}
          <div>
            <label className="label">New password</label>
            <input
              className="input"
              type="password"
              value={pw}
              onChange={(e) => setPw(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="label">Confirm new password</label>
            <input
              className="input"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
            />
          </div>
          <button className="btn-primary w-full" disabled={busy || !token}>
            {busy ? "Updating…" : "Update password"}
          </button>
          <p className="text-center text-sm text-muted">
            <Link to="/login" className="text-ink underline underline-offset-4">
              Back to sign in
            </Link>
          </p>
        </form>
      )}
    </AuthShell>
  );
}

import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { AuthShell } from "./Login";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [devLink, setDevLink] = useState("");

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const res = await api.post("/auth/forgot-password", { email });
      setSent(true);
      // In dev (no SMTP) the API returns a usable reset link.
      if (res.reset_link) setDevLink(res.reset_link);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title="Reset your password" subtitle="We'll send you a link to set a new one">
      {sent ? (
        <div className="space-y-4">
          <div className="badge border-success/40 text-success w-full justify-center py-2">
            If an account exists for that email, a reset link has been generated.
          </div>
          {devLink && (
            <div className="card p-4 text-sm">
              <div className="text-muted mb-2">
                Email isn't configured in this environment, so here's your reset link:
              </div>
              <Link to={devLink} className="btn-primary w-full">
                Set a new password →
              </Link>
            </div>
          )}
          <Link to="/login" className="btn-ghost w-full">
            Back to sign in
          </Link>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          {error && (
            <div className="badge border-danger/40 text-danger w-full justify-center py-2">{error}</div>
          )}
          <div>
            <label className="label">Email</label>
            <input
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <button className="btn-primary w-full" disabled={busy}>
            {busy ? "Sending…" : "Send reset link"}
          </button>
          <p className="text-center text-sm text-muted">
            Remembered it?{" "}
            <Link to="/login" className="text-white underline underline-offset-4">
              Sign in
            </Link>
          </p>
        </form>
      )}
    </AuthShell>
  );
}

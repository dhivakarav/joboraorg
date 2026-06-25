import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { AuthShell } from "./Login";

export default function Register() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    password: "",
    phone: "",
    years_experience: 0,
    job_title: "",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function set(k, v) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const res = await api.post("/auth/register", {
        ...form,
        years_experience: Number(form.years_experience) || 0,
      });
      // If the verification email couldn't be sent, carry the hint to /pending
      // so the user knows to use "Resend verification" rather than assuming all is well.
      navigate("/pending", res?.notice ? { state: { notice: res.notice } } : undefined);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title="Create your account" subtitle="Sign up — an admin will approve your access">
      <form onSubmit={submit} className="space-y-4">
        {error && <div className="badge border-danger/40 text-danger w-full justify-center py-2">{error}</div>}
        <div>
          <label className="label">Full name</label>
          <input className="input" value={form.full_name} onChange={(e) => set("full_name", e.target.value)} required />
        </div>
        <div>
          <label className="label">Email</label>
          <input className="input" type="email" value={form.email} onChange={(e) => set("email", e.target.value)} required />
        </div>
        <div>
          <label className="label">Password</label>
          <input className="input" type="password" value={form.password} onChange={(e) => set("password", e.target.value)} required />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Phone</label>
            <input className="input" value={form.phone} onChange={(e) => set("phone", e.target.value)} />
          </div>
          <div>
            <label className="label">Years of experience</label>
            <input className="input" type="number" min="0" value={form.years_experience} onChange={(e) => set("years_experience", e.target.value)} />
          </div>
        </div>
        <div>
          <label className="label">Job title / role</label>
          <input className="input" value={form.job_title} onChange={(e) => set("job_title", e.target.value)} placeholder="e.g. Frontend Engineer" />
        </div>
        <button className="btn-primary w-full" disabled={busy}>
          {busy ? "Creating…" : "Create account"}
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-muted">
        Already registered?{" "}
        <Link to="/login" className="text-white underline underline-offset-4">
          Sign in
        </Link>
      </p>
    </AuthShell>
  );
}

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { useAuth } from "../context/AuthContext";
import { api } from "../api/client";
import { useMagnetic } from "../hooks/useMagnetic";
import AINetworkPanel from "../components/auth/AINetworkPanel";
import AuthField from "../components/auth/AuthField";

const spring = { type: "spring", stiffness: 120, damping: 18 };

function LogoMark() {
  return (
    <div className="flex items-center gap-3">
      <svg width="34" height="34" viewBox="0 0 34 34" fill="none" aria-hidden>
        <motion.circle cx="24" cy="8" r="3" fill="#2563EB"
          initial={{ scale: 0, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: 0.9, ...spring }} />
        <motion.path d="M24 8 V21 A9 9 0 0 1 6 21" stroke="#0F172A" strokeWidth="3" strokeLinecap="round" fill="none"
          initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1, ease: "easeInOut", delay: 0.2 }} />
      </svg>
      <motion.span className="text-2xl font-extrabold tracking-tight text-ink"
        initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.6, delay: 0.7 }}>
        Jobora
      </motion.span>
    </div>
  );
}

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const reduce = useReducedMotion();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState(false);
  const [needsVerify, setNeedsVerify] = useState(false);
  const [resendMsg, setResendMsg] = useState("");

  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  const pwValid = password.length >= 6;
  const mag = useMagnetic();

  async function submit(e) {
    e.preventDefault();
    setError(""); setNeedsVerify(false); setResendMsg(""); setBusy(true);
    try {
      const res = await login(email, password);
      setSuccess(true);
      setTimeout(() => navigate(res.is_admin ? "/admin/dashboard" : "/app/dashboard"), reduce ? 200 : 1100);
    } catch (err) {
      setError(err.message);
      if (/verify your email/i.test(err.message || "")) setNeedsVerify(true);
      setBusy(false);
    }
  }

  async function resendVerification() {
    setResendMsg("");
    try {
      const r = await api.post("/auth/resend-verification", { email });
      setResendMsg(r?.message || "If that email is registered and unverified, a new link has been sent.");
    } catch (err) { setResendMsg(err.message); }
  }

  return (
    <motion.div className="grid min-h-screen grid-cols-1 bg-canvas text-ink isolate lg:grid-cols-2"
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.6 }}>

      {/* LEFT — AI network scene (desktop only). Purely decorative → never
          intercepts pointer events. */}
      <div className="pointer-events-none relative hidden select-none lg:block" aria-hidden>
        <AINetworkPanel boosted={success} />
        <div className="absolute inset-y-0 right-0 w-px bg-edge" />
      </div>

      {/* RIGHT — login card */}
      <div className="relative flex items-center justify-center overflow-hidden px-5 py-10">
        <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 lg:hidden" style={{
          background: "radial-gradient(70% 50% at 50% 0%, rgba(37,99,235,0.10), transparent 60%)",
        }} />

        <div className="relative z-10 w-full max-w-sm">
          <motion.div className="mb-8 flex justify-center lg:justify-start"
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <LogoMark />
          </motion.div>

          {/* Soft blue glow behind the card — decorative, non-interactive */}
          <motion.div aria-hidden className="pointer-events-none absolute -inset-5 -z-10 rounded-[32px] bg-brand/15 blur-3xl"
            animate={reduce ? { opacity: 0.3 } : { opacity: [0.18, 0.36, 0.18] }}
            transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }} />

          {/* Card — solid white for maximum legibility */}
          <motion.div className="relative z-10 overflow-hidden rounded-[24px] border border-edge bg-white p-8 shadow-lift-l"
            initial={{ scale: 0.94, opacity: 0, y: 10 }}
            animate={{ scale: success ? 1.02 : 1, opacity: 1, y: 0 }}
            transition={{ ...spring, delay: 0.15 }}>

            <h1 className="text-2xl font-semibold tracking-tight text-ink">Welcome back</h1>
            <p className="mt-1 mb-6 text-sm text-ink-soft">Sign in to your Jobora account</p>

            <form onSubmit={submit} className="relative z-10 space-y-4">
              <AnimatePresence>
                {error && (
                  <motion.div key={error}
                    initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
                    className="animate-shake overflow-hidden rounded-[14px] border border-err/30 bg-err/[0.06] px-3.5 py-2.5 text-sm text-err">
                    {error}
                    {needsVerify && (
                      <div className="mt-2 border-t border-err/20 pt-2 text-center">
                        <button type="button" onClick={resendVerification}
                          className="text-xs font-medium text-brand underline-offset-2 hover:underline">
                          Resend verification email
                        </button>
                        {resendMsg && <div className="mt-1 text-xs text-ink-soft">{resendMsg}</div>}
                      </div>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>

              <AuthField id="login-email" label="Email" type="email" autoComplete="email" required
                value={email} onChange={(e) => setEmail(e.target.value)} valid={emailValid} />

              <div>
                <AuthField id="login-password" label="Password" autoComplete="current-password" required isPassword
                  value={password} onChange={(e) => setPassword(e.target.value)} valid={pwValid} />
                <div className="mt-1.5 text-right">
                  <Link to="/forgot-password" className="text-xs text-ink-soft transition-colors hover:text-brand">
                    Forgot password?
                  </Link>
                </div>
              </div>

              <motion.button type="submit" disabled={busy}
                onMouseMove={mag.onMouseMove} onMouseLeave={mag.onMouseLeave} style={{ x: mag.x, y: mag.y }}
                className="relative w-full overflow-hidden rounded-[14px] bg-brand px-4 py-3 text-sm font-semibold text-white transition-[background-color,box-shadow] duration-200 hover:bg-brand-hover hover:shadow-glow-l disabled:cursor-not-allowed">
                <span className="relative z-10 inline-flex items-center justify-center gap-2">
                  {success ? "Welcome back" : busy ? (
                    <>
                      <span className="h-4 w-4 rounded-full border-2 border-white/35 border-t-white animate-spin" />
                      Preparing your journey…
                    </>
                  ) : "Sign in"}
                </span>
                {busy && !success && !reduce && (
                  <motion.span aria-hidden className="absolute inset-y-0 z-0 w-1/3 bg-gradient-to-r from-transparent via-white/25 to-transparent"
                    initial={{ x: "-130%" }} animate={{ x: "330%" }} transition={{ duration: 1.1, repeat: Infinity, ease: "linear" }} />
                )}
                {busy && (
                  <motion.span aria-hidden className="absolute bottom-0 left-0 z-10 h-[2px] bg-white/80"
                    initial={{ width: 0 }} animate={{ width: success ? "100%" : "88%" }}
                    transition={{ duration: success ? 0.3 : 1.3, ease: "easeOut" }} />
                )}
              </motion.button>
            </form>

            <p className="mt-6 text-center text-sm text-ink-soft">
              No account?{" "}
              <Link to="/register" className="font-medium text-brand hover:underline underline-offset-4">Create one</Link>
            </p>

            <AnimatePresence>
              {success && (
                <motion.div className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-3 rounded-[24px] bg-white/85 backdrop-blur-md"
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} aria-live="polite">
                  <motion.div className="flex h-16 w-16 items-center justify-center rounded-full bg-brand text-2xl font-bold text-white shadow-glow-l"
                    initial={{ scale: 0, rotate: -10 }} animate={{ scale: 1, rotate: 0 }} transition={spring}>
                    {(email.trim()[0] || "J").toUpperCase()}
                  </motion.div>
                  <motion.div className="text-sm text-ink-soft"
                    initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
                    Preparing your dashboard…
                  </motion.div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </div>
      </div>
    </motion.div>
  );
}

// Light auth shell for the secondary auth screens:
// Register / ForgotPassword / ResetPassword / VerifyEmail / PendingApproval.
export function AuthShell({ title, subtitle, children }) {
  return (
    <motion.div
      className="relative flex min-h-screen items-center justify-center bg-canvas px-4 text-ink"
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }}
    >
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10" style={{
        background: "radial-gradient(60% 45% at 50% 0%, rgba(37,99,235,0.08), transparent 60%)",
      }} />
      <motion.div className="w-full max-w-md"
        initial={{ y: 12, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ ...spring, delay: 0.05 }}>
        <div className="mb-8 flex flex-col items-center text-center">
          <div className="flex items-center gap-2.5">
            <svg width="30" height="30" viewBox="0 0 34 34" fill="none" aria-hidden>
              <circle cx="24" cy="8" r="3" fill="#2563EB" />
              <path d="M24 8 V21 A9 9 0 0 1 6 21" stroke="#0F172A" strokeWidth="3" strokeLinecap="round" fill="none" />
            </svg>
            <span className="text-3xl font-extrabold tracking-tight text-ink">Jobora</span>
          </div>
          <div className="mt-1.5 text-sm text-ink-soft">Auto Job Applier</div>
        </div>
        <div className="card-elevated p-8">
          <h1 className="text-xl font-semibold text-ink">{title}</h1>
          <p className="mb-6 mt-1 text-sm text-ink-soft">{subtitle}</p>
          {children}
        </div>
      </motion.div>
    </motion.div>
  );
}

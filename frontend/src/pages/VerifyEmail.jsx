import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { AuthShell } from "./Login";

// Lands here from the verification email link: /verify-email?token=...
// Calls POST /auth/verify-email which marks the account verified.
export default function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [state, setState] = useState(token ? "verifying" : "missing"); // verifying | ok | error | missing
  const [message, setMessage] = useState("");
  const ran = useRef(false);

  useEffect(() => {
    if (!token || ran.current) return;
    ran.current = true; // guard React StrictMode double-invoke (token is single-use)
    api
      .post("/auth/verify-email", { token })
      .then((r) => { setState("ok"); setMessage(r?.message || "Your email has been verified."); })
      .catch((err) => { setState("error"); setMessage(err.message || "Verification link is invalid or expired."); });
  }, [token]);

  return (
    <AuthShell title="Verify your email" subtitle="Confirming your Jobora account">
      {state === "verifying" && (
        <div className="badge border-line text-muted w-full justify-center py-2">Verifying…</div>
      )}
      {state === "missing" && (
        <div className="badge border-danger/40 text-danger w-full justify-center py-2">
          No verification token in the link.
        </div>
      )}
      {state === "ok" && (
        <div className="space-y-4 text-center">
          <div className="badge border-success/40 text-success w-full justify-center py-2">{message}</div>
          <Link to="/login" className="btn-primary w-full">Go to sign in</Link>
        </div>
      )}
      {state === "error" && (
        <div className="space-y-4 text-center">
          <div className="badge border-danger/40 text-danger w-full justify-center py-2">{message}</div>
          <Link to="/login" className="text-ink underline underline-offset-4 text-sm">
            Back to sign in
          </Link>
          <p className="text-xs text-muted">
            The link may have expired. You can request a new one from the sign-in screen.
          </p>
        </div>
      )}
    </AuthShell>
  );
}

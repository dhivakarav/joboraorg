import { Link } from "react-router-dom";
import { AuthShell } from "./Login";

export default function PendingApproval() {
  return (
    <AuthShell title="Account pending approval" subtitle="Almost there">
      <div className="text-center py-4">
        <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-full border border-line bg-elevated text-3xl shadow-glossy">
          ⏳
        </div>
        <p className="text-sm text-muted leading-relaxed">
          Your account is <span className="text-white font-medium">pending admin approval</span>.
          You won't be able to access any features until an administrator approves your account.
          Please check back later.
        </p>
        <Link to="/login" className="btn-primary w-full mt-6">
          Back to sign in
        </Link>
      </div>
    </AuthShell>
  );
}

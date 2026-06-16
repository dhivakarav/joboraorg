// Shared presentational primitives used across the app.
import { createContext, useContext, useState, useCallback, useEffect } from "react";

// ---------- Toast ----------
const ToastCtx = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const push = useCallback((message, type = "info") => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t, { id, message, type }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3500);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="fixed bottom-5 right-5 z-[100] flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`card-elevated px-4 py-3 text-sm max-w-xs ${
              t.type === "error"
                ? "border-danger/50"
                : t.type === "success"
                ? "border-success/50"
                : ""
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export function useToast() {
  return useContext(ToastCtx);
}

// ---------- Modal ----------
export function Modal({ open, onClose, title, children, width = "max-w-md" }) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onMouseDown={onClose}
    >
      <div
        className={`card-elevated w-full ${width} p-6 max-h-[90vh] overflow-y-auto`}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button onClick={onClose} className="text-muted hover:text-white text-xl leading-none">
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

// ---------- Toggle switch ----------
export function Toggle({ checked, onChange }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={`relative h-6 w-11 rounded-full transition-colors ${
        checked ? "bg-white" : "bg-inputline"
      }`}
    >
      <span
        className={`absolute top-0.5 h-5 w-5 rounded-full transition-transform ${
          checked ? "translate-x-[22px] bg-black" : "translate-x-0.5 bg-white"
        }`}
      />
    </button>
  );
}

// ---------- Status badge ----------
// Canonical application statuses. "Applied" is retired: only "Verified Submitted"
// signals a confirmed, evidenced submission. Any stale "Applied" is coerced to
// "Tracked" so it can never reach the screen.
const STATUS_STYLE = {
  // canonical application statuses
  "Verified Submitted": "border-success/60 text-success",
  Submitted: "border-blue-400/50 text-blue-300",
  Tracked: "border-blue-400/40 text-blue-300",
  "Manual Apply": "border-yellow-500/40 text-yellow-400",
  Draft: "border-line text-muted",
  Failed: "border-danger/40 text-danger",
  // other (portal/user/admin) labels still used around the app
  Saved: "border-line text-muted",
  Skipped: "border-muted/40 text-muted",
  Ready: "border-blue-400/40 text-blue-300",
  Queued: "border-blue-400/40 text-blue-300",
  Processing: "border-blue-400/40 text-blue-300",
  "CAPTCHA Required": "border-yellow-500/40 text-yellow-400",
  "Manual Apply Required": "border-yellow-500/40 text-yellow-400",
  approved: "border-success/40 text-success",
  Connected: "border-success/40 text-success",
  Pending: "border-yellow-500/40 text-yellow-400",
  pending: "border-yellow-500/40 text-yellow-400",
  "Setup Needed": "border-yellow-500/40 text-yellow-400",
  suspended: "border-danger/40 text-danger",
};

export function StatusBadge({ status }) {
  // Hard guard: never render the retired "Applied" label.
  const s = status === "Applied" ? "Tracked" : status || "Draft";
  const label = s.charAt(0).toUpperCase() + s.slice(1);
  return <span className={`badge ${STATUS_STYLE[s] || "border-line text-muted"}`}>{label}</span>;
}

// Canonical Evidence cell — keyed on display_status + evidence presence (single
// source of truth, shared by Activity Log and Verification Center):
//   • View  — only Submitted / Verified Submitted that actually have evidence
//             (a stored screenshot or a confirmation URL) → opens the Evidence modal.
//   • Open  — only Tracked / Manual Apply (not yet submitted) → opens the apply page.
//   • "—"   — anything else, or no evidence to show.
export function EvidenceCell({ row, onView }) {
  const ds = row.display_status;
  const hasEvidence = !!row.evidence_available || !!row.confirmation_url;
  const link = "text-white underline underline-offset-2 hover:text-muted";
  if ((ds === "Submitted" || ds === "Verified Submitted") && hasEvidence) {
    return <button onClick={() => onView(row)} className={link}>View</button>;
  }
  if ((ds === "Tracked" || ds === "Manual Apply") && row.apply_url) {
    return <a href={row.apply_url} target="_blank" rel="noopener noreferrer" className={link}>Open ↗</a>;
  }
  return <span className="text-muted">—</span>;
}

// ---------- Tooltip (hover on desktop, tap-to-toggle on mobile) ----------
export function Tooltip({ text, children }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    // close on next tap anywhere
    const id = setTimeout(() => document.addEventListener("click", close, { once: true }), 0);
    return () => { clearTimeout(id); document.removeEventListener("click", close); };
  }, [open]);
  return (
    <span className="relative inline-flex group">
      <span
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
        className="inline-flex"
      >
        {children}
      </span>
      <span
        role="tooltip"
        className={`pointer-events-none absolute left-1/2 bottom-full z-50 mb-2 -translate-x-1/2
                   w-56 rounded-btn border border-line bg-elevated px-3 py-2 text-xs text-white
                   shadow-glossylg group-hover:block ${open ? "block" : "hidden"}`}
      >
        {text}
      </span>
    </span>
  );
}

// ---------- Stat card ----------
export function StatCard({ label, value, accent }) {
  return (
    <div className="card-elevated p-5">
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      <div className={`mt-2 text-3xl font-bold ${accent || "text-white"}`}>{value}</div>
    </div>
  );
}

// ---------- Pills input ----------
export function PillInput({ values, onChange, placeholder }) {
  const [draft, setDraft] = useState("");
  function add() {
    const v = draft.trim();
    if (v && !values.includes(v)) onChange([...values, v]);
    setDraft("");
  }
  return (
    <div>
      <div className="flex gap-2">
        <input
          className="input"
          value={draft}
          placeholder={placeholder}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
        />
        <button type="button" className="btn-primary" onClick={add}>
          Add
        </button>
      </div>
      {values.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {values.map((v) => (
            <span key={v} className="pill">
              {v}
              <button
                onClick={() => onChange(values.filter((x) => x !== v))}
                className="text-muted hover:text-danger"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function Spinner() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-line border-t-white" />
    </div>
  );
}

// Skeleton primitives for loading states.
export function Skeleton({ className = "" }) {
  return <div className={`animate-pulse rounded bg-elevated ${className}`} />;
}

export function JobCardSkeleton() {
  return (
    <div className="card-elevated p-5 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-3 w-1/3" />
        </div>
        <Skeleton className="h-8 w-8 rounded-full" />
      </div>
      <div className="flex gap-2">
        <Skeleton className="h-5 w-24" />
        <Skeleton className="h-5 w-20" />
      </div>
      <Skeleton className="h-16 w-full" />
      <div className="flex items-center gap-2 pt-2">
        <Skeleton className="h-5 w-28" />
        <Skeleton className="h-8 w-24 ml-auto" />
      </div>
    </div>
  );
}

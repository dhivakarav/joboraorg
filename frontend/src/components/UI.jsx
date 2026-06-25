// Shared presentational primitives used across the app.
import { createContext, useContext, useState, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

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
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.div
              key={t.id}
              layout
              initial={{ opacity: 0, x: 40, scale: 0.96 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 40, scale: 0.96 }}
              transition={{ type: "spring", stiffness: 360, damping: 30 }}
              className={`card-elevated max-w-xs px-4 py-3 text-sm text-ink ${
                t.type === "error"
                  ? "border-l-4 border-l-err"
                  : t.type === "success"
                  ? "border-l-4 border-l-ok"
                  : "border-l-4 border-l-brand"
              }`}
            >
              {t.message}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  );
}

export function useToast() {
  return useContext(ToastCtx);
}

// ---------- Modal ----------
export function Modal({ open, onClose, title, children, width = "max-w-md" }) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-sm"
          onMouseDown={onClose}
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        >
          <motion.div
            className={`card-elevated w-full ${width} max-h-[90vh] overflow-y-auto p-6`}
            onMouseDown={(e) => e.stopPropagation()}
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 8 }}
            transition={{ type: "spring", stiffness: 300, damping: 28 }}
          >
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-ink">{title}</h3>
              <button onClick={onClose} className="text-xl leading-none text-ink-soft transition-colors hover:text-ink">
                ×
              </button>
            </div>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// ---------- Toggle switch ----------
export function Toggle({ checked, onChange }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={`relative h-6 w-11 rounded-full transition-colors ${
        checked ? "bg-brand" : "bg-slate-200"
      }`}
    >
      <span
        className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform ${
          checked ? "translate-x-[22px]" : "translate-x-0.5"
        }`}
      />
    </button>
  );
}

// ---------- Status badge ----------
// Application statuses. Automated submission outcomes stay evidence-gated
// (only "Verified Submitted" signals a confirmed, evidenced auto-submission).
// Applied / Interview / Offer / Rejected are SELF-REPORTED pipeline stages a
// user sets by hand — automation never emits them.
const OK = "border-green-200 bg-green-50 text-green-700";
const BLUE = "border-blue-200 bg-blue-50 text-blue-700";
const AMBER = "border-amber-200 bg-amber-50 text-amber-700";
const PURPLE = "border-purple-200 bg-purple-50 text-purple-700";
const EMERALD = "border-emerald-200 bg-emerald-50 text-emerald-700";
const RED = "border-red-200 bg-red-50 text-red-700";
const NEUTRAL = "border-edge bg-canvas text-ink-soft";

const STATUS_STYLE = {
  // canonical application statuses
  "Verified Submitted": OK,
  Submitted: BLUE,
  "Submitted (Unverified)": NEUTRAL,
  Tracked: BLUE,
  "Manual Apply": AMBER,
  "Pending Approval": AMBER,
  Draft: NEUTRAL,
  Failed: RED,
  "Failed — No Confirmation": RED,
  "Failed — Form Not Found": RED,
  "Failed — Submit Not Found": RED,
  // self-reported pipeline stages
  Applied: BLUE,
  Interview: PURPLE,
  Offer: EMERALD,
  Rejected: RED,
  // other (portal/user/admin) labels still used around the app
  Saved: NEUTRAL,
  Skipped: NEUTRAL,
  Ready: BLUE,
  Queued: BLUE,
  Processing: BLUE,
  "CAPTCHA Required": AMBER,
  "Manual Apply Required": AMBER,
  approved: OK,
  Connected: OK,
  Pending: AMBER,
  pending: AMBER,
  "Setup Needed": AMBER,
  suspended: RED,
};

export function StatusBadge({ status }) {
  const s = status || "Draft";
  const label = s.charAt(0).toUpperCase() + s.slice(1);
  return <span className={`badge ${STATUS_STYLE[s] || NEUTRAL}`}>{label}</span>;
}

// Hybrid apply-mode badge: green "Auto-Applied" (ATS public apply path) vs blue
// "Apply Manually" (no public API → user opens the apply link).
export function ApplyModeBadge({ mode }) {
  const auto = mode === "auto_applied";
  return (
    <span className={`badge ${auto ? OK : BLUE}`}>
      {auto ? "Auto-Applied" : "Apply Manually"}
    </span>
  );
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
  const link = "font-medium text-brand underline-offset-2 hover:underline";
  if ((ds === "Submitted" || ds === "Verified Submitted") && hasEvidence) {
    return <button onClick={() => onView(row)} className={link}>View</button>;
  }
  if ((ds === "Tracked" || ds === "Manual Apply") && row.apply_url) {
    return <a href={row.apply_url} target="_blank" rel="noopener noreferrer" className={link}>Open ↗</a>;
  }
  return <span className="text-ink-soft">—</span>;
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
    <span className="group relative inline-flex">
      <span
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
        className="inline-flex"
      >
        {children}
      </span>
      <span
        role="tooltip"
        className={`pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 w-56 -translate-x-1/2
                   rounded-[12px] bg-ink px-3 py-2 text-xs text-white
                   shadow-lift-l group-hover:block ${open ? "block" : "hidden"}`}
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
      <div className="text-xs font-medium uppercase tracking-wide text-ink-soft">{label}</div>
      <div className={`mt-2 text-3xl font-bold tracking-tight ${accent || "text-ink"}`}>{value}</div>
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
                className="text-ink-soft hover:text-err"
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
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-edge border-t-brand" />
    </div>
  );
}

// Skeleton primitives for loading states.
export function Skeleton({ className = "" }) {
  return <div className={`animate-pulse rounded bg-slate-100 ${className}`} />;
}

export function JobCardSkeleton() {
  return (
    <div className="card-elevated space-y-3 p-5">
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
        <Skeleton className="ml-auto h-8 w-24" />
      </div>
    </div>
  );
}

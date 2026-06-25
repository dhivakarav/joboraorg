import { useState } from "react";
import { NavLink, useNavigate, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { useAuth } from "../context/AuthContext";
import OnboardingModal from "./OnboardingModal";
import FeedbackWidget from "./FeedbackWidget";

const USER_NAV = [
  { to: "/app/dashboard", label: "Dashboard", icon: "▦" },
  { to: "/app/jobs", label: "Find Jobs", icon: "◎" },
  { to: "/app/matched", label: "Matched Jobs", icon: "◈" },
  { to: "/app/resume", label: "Resume", icon: "▤" },
  { to: "/app/filters", label: "Filters", icon: "⊜" },
  { to: "/app/activity", label: "Activity Log", icon: "≡" },
  { to: "/app/verification", label: "Verification Center", icon: "✓" },
  { to: "/app/settings", label: "Settings", icon: "⚙" },
];

const ADMIN_NAV = [
  { to: "/admin/dashboard", label: "Dashboard", icon: "▦" },
  { to: "/admin/users", label: "User Management", icon: "◍" },
  { to: "/admin/applications", label: "All Applications", icon: "≡" },
  { to: "/admin/operations", label: "Operations", icon: "◆" },
];

function Wordmark({ admin }) {
  return (
    <div className="flex items-center gap-2.5">
      <svg width="26" height="26" viewBox="0 0 34 34" fill="none" aria-hidden>
        <circle cx="24" cy="8" r="3" fill="#2563EB" />
        <path d="M24 8 V21 A9 9 0 0 1 6 21" stroke="#0F172A" strokeWidth="3" strokeLinecap="round" fill="none" />
      </svg>
      <span className="text-xl font-extrabold tracking-tight text-ink">Jobora</span>
      {admin && <span className="rounded-full bg-brand-soft px-2 py-0.5 text-[10px] font-bold tracking-wide text-brand">ADMIN</span>}
    </div>
  );
}

function NavItems({ nav, onNavigate }) {
  const { pathname } = useLocation();
  return (
    <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
      {nav.map((n) => {
        const active = pathname === n.to;
        return (
          <NavLink
            key={n.to}
            to={n.to}
            onClick={onNavigate}
            className="relative flex items-center gap-3 rounded-[12px] px-3 py-2.5 text-sm font-medium transition-colors"
          >
            {active && (
              <motion.span
                layoutId="nav-active"
                className="absolute inset-0 rounded-[12px] bg-brand-soft"
                transition={{ type: "spring", stiffness: 380, damping: 32 }}
              />
            )}
            <span className={`relative z-10 grid h-7 w-7 place-items-center rounded-[9px] text-sm transition-colors ${
              active ? "bg-brand text-white" : "bg-canvas text-ink-soft"
            }`}>{n.icon}</span>
            <span className={`relative z-10 transition-colors ${active ? "font-semibold text-brand" : "text-ink-soft"}`}>
              {n.label}
            </span>
          </NavLink>
        );
      })}
    </nav>
  );
}

export default function Layout({ admin = false, children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const nav = admin ? ADMIN_NAV : USER_NAV;
  const [open, setOpen] = useState(false); // mobile drawer

  function doLogout() {
    logout();
    navigate("/login");
  }

  const SidebarBody = (
    <>
      <div className="border-b border-edge px-6 py-5">
        <Wordmark admin={admin} />
        <div className="mt-1.5 text-xs text-ink-soft">Auto Job Applier</div>
      </div>
      <NavItems nav={nav} onNavigate={() => setOpen(false)} />
      <div className="border-t border-edge p-4">
        <div className="flex items-center gap-3 rounded-[14px] bg-canvas p-3">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand text-sm font-bold text-white">
            {(user?.full_name?.[0] || user?.email?.[0] || "U").toUpperCase()}
          </div>
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-ink">{user?.full_name}</div>
            <div className="truncate text-xs text-ink-soft">{user?.email}</div>
          </div>
        </div>
        <button className="btn-ghost mt-3 w-full" onClick={doLogout}>Log out</button>
      </div>
    </>
  );

  return (
    <div className="flex min-h-screen bg-canvas">
      {/* Desktop sidebar */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-edge bg-white md:flex">
        {SidebarBody}
      </aside>

      {/* Mobile drawer + overlay */}
      <AnimatePresence>
        {open && (
          <div className="fixed inset-0 z-40 md:hidden">
            <motion.div
              className="absolute inset-0 bg-ink/40 backdrop-blur-sm"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setOpen(false)}
            />
            <motion.aside
              className="absolute left-0 top-0 flex h-full w-72 max-w-[80%] flex-col border-r border-edge bg-white"
              initial={{ x: "-100%" }} animate={{ x: 0 }} exit={{ x: "-100%" }}
              transition={{ type: "spring", stiffness: 320, damping: 34 }}
            >
              {SidebarBody}
            </motion.aside>
          </div>
        )}
      </AnimatePresence>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile top bar */}
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-edge bg-white/80 px-4 py-3 backdrop-blur-xl md:hidden">
          <button aria-label="Open menu" onClick={() => setOpen(true)} className="px-1 text-2xl leading-none text-ink">☰</button>
          <Wordmark admin={admin} />
          <button className="text-xs font-medium text-ink-soft hover:text-ink" onClick={doLogout}>Log out</button>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 md:px-8 md:py-10">{children}</div>
        </main>
      </div>

      {!admin && <OnboardingModal />}
      <FeedbackWidget />
    </div>
  );
}

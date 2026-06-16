import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import OnboardingModal from "./OnboardingModal";
import FeedbackWidget from "./FeedbackWidget";

const USER_NAV = [
  { to: "/app/dashboard", label: "Dashboard", icon: "▦" },
  { to: "/app/jobs", label: "Find Jobs", icon: "◎" },
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
      <div className="px-6 py-6 border-b border-line">
        <div className="text-2xl font-extrabold tracking-tight">
          Jobora
          {admin && <span className="ml-2 text-xs font-medium text-muted align-middle">ADMIN</span>}
        </div>
        <div className="text-xs text-muted mt-1">Student Job Applier</div>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {nav.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            onClick={() => setOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-btn px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-white text-black shadow-glossy"
                  : "text-muted hover:text-white hover:bg-elevated"
              }`
            }
          >
            <span className="w-4 text-center">{n.icon}</span>
            {n.label}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-line p-4">
        <div className="text-sm font-medium truncate">{user?.full_name}</div>
        <div className="text-xs text-muted truncate mb-3">{user?.email}</div>
        <button className="btn-ghost w-full" onClick={doLogout}>Log out</button>
      </div>
    </>
  );

  return (
    <div className="flex min-h-screen bg-bg">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-64 shrink-0 border-r border-line bg-surface flex-col">
        {SidebarBody}
      </aside>

      {/* Mobile drawer + overlay */}
      {open && (
        <div className="md:hidden fixed inset-0 z-40">
          <div className="absolute inset-0 bg-black/60" onClick={() => setOpen(false)} />
          <aside className="absolute left-0 top-0 h-full w-72 max-w-[80%] border-r border-line bg-surface flex flex-col">
            {SidebarBody}
          </aside>
        </div>
      )}

      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile top bar */}
        <header className="md:hidden sticky top-0 z-30 flex items-center justify-between
                           border-b border-line bg-surface px-4 py-3">
          <button aria-label="Open menu" onClick={() => setOpen(true)}
                  className="text-2xl leading-none px-1">☰</button>
          <div className="text-lg font-extrabold tracking-tight">Jobora{admin && " · ADMIN"}</div>
          <button className="text-xs text-muted" onClick={doLogout}>Log out</button>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-6xl px-4 sm:px-6 md:px-8 py-6 md:py-8">{children}</div>
        </main>
      </div>

      {!admin && <OnboardingModal />}
      <FeedbackWidget />
    </div>
  );
}

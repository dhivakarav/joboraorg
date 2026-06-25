import { useState } from "react";

// First-time walkthrough explaining what Jobora does (and doesn't do).
// Dismissible; remembers via localStorage so it shows once.
const KEY = "jobora_howitworks_dismissed";

const STEPS = [
  { icon: "①", title: "Discover real roles",
    body: "We match real internship & new-grad openings to your resume. Senior, PhD-only and experienced roles are filtered out by default." },
  { icon: "②", title: "Apply your way",
    body: "Greenhouse → Track & Apply on the company site. Lever/Ashby → an Assisted Apply wizard prefills the form; you complete the captcha & submit." },
  { icon: "③", title: "Verify your submission",
    body: "Record your confirmation (URL + ID + screenshot). Only then is it “Verified Submitted”. Jobora never claims you applied without proof." },
];

export default function HowItWorks() {
  const [dismissed, setDismissed] = useState(() => localStorage.getItem(KEY) === "1");
  if (dismissed) return null;

  function close() {
    localStorage.setItem(KEY, "1");
    setDismissed(true);
  }

  return (
    <div className="card-elevated p-5 relative">
      <button onClick={close}
              className="absolute top-3 right-3 text-muted hover:text-ink text-lg leading-none"
              aria-label="Dismiss">×</button>
      <h2 className="font-semibold mb-1">Welcome to Jobora 👋</h2>
      <p className="text-sm text-muted mb-4">How it works — honest job tracking for students.</p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {STEPS.map((s) => (
          <div key={s.title} className="rounded-btn bg-input/40 border border-line p-3">
            <div className="text-xl mb-1">{s.icon}</div>
            <div className="font-medium text-sm mb-1">{s.title}</div>
            <div className="text-xs text-muted leading-relaxed">{s.body}</div>
          </div>
        ))}
      </div>
      <button onClick={close} className="btn-ghost mt-4 text-sm">Got it</button>
    </div>
  );
}

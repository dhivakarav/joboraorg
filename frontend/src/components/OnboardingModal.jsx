import { useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { Modal, useToast } from "./UI";

const OPTIONS = [
  { key: "student", emoji: "🎓", title: "Student", desc: "Looking for internships while studying." },
  { key: "fresher", emoji: "🌱", title: "Fresher", desc: "Recent grad seeking my first full-time role." },
  { key: "experienced", emoji: "💼", title: "Experienced", desc: "Working professional exploring new roles." },
];

// One-time onboarding: capture seeker type to personalize recommendations.
export default function OnboardingModal() {
  const { user, refresh } = useAuth();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  const show = user && !user.is_admin && user.status === "approved"
    && !user.seeker_type && !dismissed;

  async function choose(key) {
    setBusy(true);
    try {
      await api.put("/profile/update", { seeker_type: key });
      await refresh();
      toast("Recommendations personalized for you", "success");
      setDismissed(true);
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setBusy(false);
    }
  }

  if (!show) return null;

  return (
    <Modal open={show} onClose={() => setDismissed(true)} title="Welcome to Jobara 👋" width="max-w-lg">
      <div className="space-y-4">
        <p className="text-sm text-muted">
          Tell us where you are in your journey so we can show the right
          opportunities first — internships, fresher roles, or full-time jobs.
        </p>
        <div className="grid grid-cols-1 gap-3">
          {OPTIONS.map((o) => (
            <button
              key={o.key}
              disabled={busy}
              onClick={() => choose(o.key)}
              className="card-elevated p-4 text-left hover:border-brand transition-colors flex items-center gap-4 disabled:opacity-50"
            >
              <span className="text-2xl">{o.emoji}</span>
              <span>
                <span className="font-semibold block">{o.title}</span>
                <span className="text-sm text-muted">{o.desc}</span>
              </span>
            </button>
          ))}
        </div>
        <button className="btn-ghost w-full" disabled={busy} onClick={() => setDismissed(true)}>
          Skip for now
        </button>
      </div>
    </Modal>
  );
}

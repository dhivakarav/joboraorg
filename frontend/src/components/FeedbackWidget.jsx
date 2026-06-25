import { useState } from "react";
import { api } from "../api/client";
import { Modal, useToast } from "./UI";

// Floating beta feedback + bug-report widget, available on every signed-in page.
export default function FeedbackWidget() {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState("feedback");
  const [message, setMessage] = useState("");
  const [rating, setRating] = useState(0);
  const [severity, setSeverity] = useState("medium");
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!message.trim()) return toast("Please add a message", "error");
    setBusy(true);
    try {
      await api.post("/feedback", {
        kind,
        message,
        page: window.location.pathname,
        rating: kind === "feedback" && rating ? rating : null,
        severity: kind === "bug" ? severity : "",
      });
      toast("Thanks for the " + (kind === "bug" ? "bug report" : "feedback") + "!", "success");
      setOpen(false);
      setMessage(""); setRating(0); setKind("feedback");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        title="Send feedback or report a bug"
        className="fixed bottom-5 right-5 z-40 rounded-full bg-brand text-white text-sm font-medium px-4 py-2.5 shadow-lift-l hover:bg-brand-hover transition-colors"
      >
        💬 Feedback
      </button>

      <Modal open={open} onClose={() => setOpen(false)} title="Beta feedback">
        <div className="space-y-4">
          <div className="flex gap-2">
            {["feedback", "bug"].map((k) => (
              <button
                key={k}
                onClick={() => setKind(k)}
                className={`badge px-3 py-1.5 ${kind === k ? "bg-brand text-white border-brand" : "border-line text-muted"}`}
              >
                {k === "bug" ? "🐞 Bug report" : "💡 Feedback"}
              </button>
            ))}
          </div>

          {kind === "feedback" && (
            <div>
              <label className="label">How's your experience? (optional)</label>
              <div className="flex gap-1 text-2xl">
                {[1, 2, 3, 4, 5].map((n) => (
                  <button key={n} onClick={() => setRating(n)}
                          className={n <= rating ? "text-amber-600" : "text-muted"}>★</button>
                ))}
              </div>
            </div>
          )}

          {kind === "bug" && (
            <div>
              <label className="label">Severity</label>
              <select className="input w-auto" value={severity} onChange={(e) => setSeverity(e.target.value)}>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High — blocks me</option>
              </select>
            </div>
          )}

          <div>
            <label className="label">{kind === "bug" ? "What went wrong?" : "Your feedback"}</label>
            <textarea
              className="input min-h-[110px]"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder={kind === "bug"
                ? "What did you do, what happened, what did you expect?"
                : "What would make Jobora more useful for you?"}
            />
          </div>

          <button className="btn-primary w-full" disabled={busy} onClick={submit}>
            {busy ? "Sending…" : "Send"}
          </button>
          <p className="text-xs text-muted text-center">We read every beta report. Thank you 🙏</p>
        </div>
      </Modal>
    </>
  );
}

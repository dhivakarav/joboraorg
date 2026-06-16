import { useEffect, useState } from "react";
import { api } from "../api/client";
import { Modal, Spinner, useToast } from "./UI";

// Real Greenhouse submission — gated by a mandatory per-application confirmation
// and the user's truthful answers to the posting's required screening questions.
// Each confirmed submission files a REAL application (when JOBORA_LIVE=1). The user
// can instead choose "Open on company site & track" (no submission).
export default function GreenhouseSubmitWizard({ job, onClose, onTracked, onSubmitted }) {
  const toast = useToast();
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [answers, setAnswers] = useState({});
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);

  useEffect(() => {
    if (!job) return;
    setForm(null); setError(""); setAnswers({}); setConfirm(false); setDone(null);
    api.post("/jobs/greenhouse/form", payload(job)).then(setForm).catch((e) => setError(e.message));
  }, [job]);

  if (!job) return null;

  const required = form?.required_questions || [];
  const allAnswered = required.every((q) => (answers[q.name] || "").trim());
  const canSubmit = form?.profile_complete && allAnswered && confirm && !busy;

  function setA(name, v) { setAnswers((a) => ({ ...a, [name]: v })); }

  async function trackInstead() {
    window.open(job.apply_url, "_blank", "noopener");
    try {
      await api.post("/jobs/apply", { ...payload(job), status: "Tracked", manual_required: false });
      toast(`Opened ${job.company}'s page — tracked`, "success");
      onTracked?.(); onClose();
    } catch (e) { toast(e.message, "error"); }
  }

  async function submitReal() {
    setBusy(true);
    try {
      const r = await api.post("/jobs/greenhouse/apply", {
        ...payload(job), answers, approved: true,
      });
      setDone(r);
      toast("Application queued — submitting in the background", "success");
      onSubmitted?.();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={!!job} onClose={onClose} title="Submit application — Greenhouse" width="max-w-2xl">
      {error ? (
        <div className="space-y-3">
          <div className="badge border-danger/40 text-danger w-full justify-center py-2">{error}</div>
          <button className="btn-ghost w-full" onClick={trackInstead}>Open on company site &amp; track instead</button>
        </div>
      ) : !form ? (
        <Spinner />
      ) : done ? (
        <div className="space-y-4 text-center">
          <div className="text-4xl">📨</div>
          <div className="font-semibold">Application queued</div>
          <p className="text-sm text-muted">
            It's submitting in the background. The result (Verified Submitted / Submitted /
            Failed) and any evidence will appear in your <b className="text-white">Verification Center</b>.
          </p>
          <button className="btn-primary w-full" onClick={onClose}>Done</button>
        </div>
      ) : (
        <div className="space-y-4">
          <div>
            <div className="font-semibold">{form.title}</div>
            <div className="text-sm text-muted">{form.company} · Greenhouse</div>
          </div>

          {/* Hard, unmissable warning */}
          <div className="card p-3 border-danger/40 text-sm">
            <span className="text-danger font-medium">This files a real application to {form.company}.</span>{" "}
            It is sent under your name and <b className="text-white">cannot be undone</b>. Answer truthfully.
          </div>

          {!form.profile_complete && (
            <div className="badge border-yellow-500/40 text-yellow-400 w-full justify-center py-2">
              Complete your profile/resume first (missing: {form.missing_profile.join(", ")})
            </div>
          )}

          {/* Identity Jobora will submit */}
          <div className="card divide-y divide-line text-sm">
            {[["Name", form.prefill.name], ["Email", form.prefill.email],
              ["Phone", form.prefill.phone], ["Resume", form.prefill.resume_filename || "—"]].map(([k, v]) => (
              <div key={k} className="flex justify-between px-3 py-2">
                <span className="text-muted">{k}</span><span className="text-white">{v || "—"}</span>
              </div>
            ))}
          </div>

          {/* Required screening questions — truthful answers */}
          {required.length > 0 && (
            <div className="space-y-3">
              <div className="label">Required questions (answer truthfully)</div>
              {required.map((q) => (
                <div key={q.name}>
                  <label className="text-sm text-muted block mb-1">{q.label} *</label>
                  {q.values?.length ? (
                    <select className="input" value={answers[q.name] || ""} onChange={(e) => setA(q.name, e.target.value)}>
                      <option value="">— select —</option>
                      {q.values.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                  ) : q.type === "textarea" ? (
                    <textarea className="input min-h-[80px]" value={answers[q.name] || ""} onChange={(e) => setA(q.name, e.target.value)} />
                  ) : (
                    <input className="input" value={answers[q.name] || ""} onChange={(e) => setA(q.name, e.target.value)} />
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Mandatory confirmation */}
          <label className="flex items-start gap-2 text-sm cursor-pointer">
            <input type="checkbox" className="accent-white h-4 w-4 mt-0.5" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} />
            <span>I confirm these answers are truthful and I want to submit a <b className="text-white">real application</b> to {form.company}.</span>
          </label>

          <div className="flex gap-2">
            <button className="btn-ghost flex-1" onClick={trackInstead}>Open &amp; track instead</button>
            <button className="btn-primary flex-1" disabled={!canSubmit} onClick={submitReal}>
              {busy ? "Submitting…" : "Submit real application"}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}

function payload(job) {
  return {
    fingerprint: job.fingerprint, external_id: job.external_id || "", source: job.source,
    title: job.title, company: job.company, location: job.location || "",
    salary: job.salary || "", salary_inr: job.salary_inr || "", apply_url: job.apply_url,
    verified: !!job.verified,
  };
}

import { useEffect, useState } from "react";
import { api } from "../api/client";
import { Modal, Spinner, StatusBadge, useToast } from "./UI";

// Assisted Apply for captcha-gated portals (Lever / Ashby).
// Step 1 Review → Step 2 Apply on portal → Step 3 Record evidence.
// Status becomes "Verified Submitted" only when id + confirmation URL + screenshot
// are all provided; otherwise "Submitted". Never "Applied" without proof.
export default function AssistedApplyWizard({ job, onClose, onDone }) {
  const toast = useToast();
  const [prep, setPrep] = useState(null);
  const [error, setError] = useState("");
  const [step, setStep] = useState(1);
  const [opened, setOpened] = useState(false);
  const [busy, setBusy] = useState(false);

  // evidence
  const [confUrl, setConfUrl] = useState("");
  const [refId, setRefId] = useState("");
  const [shot, setShot] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (!job) return;
    setPrep(null); setError(""); setStep(1); setOpened(false);
    setConfUrl(""); setRefId(""); setShot(null); setResult(null);
    api.post("/jobs/assisted/prepare", {
      job: {
        title: job.title, company: job.company, apply_url: job.apply_url,
        source: job.source, location: job.location, salary: job.salary,
        salary_inr: job.salary_inr, verified: job.verified, fingerprint: job.fingerprint,
      },
    }).then(setPrep).catch((e) => setError(e.message));
  }, [job]);

  if (!job) return null;

  function openPortal() {
    window.open(prep.apply_url, "_blank", "noopener");
    setOpened(true);
    setStep(2);
  }

  async function record() {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("application_id", String(prep.application_id));
      fd.append("confirmation_url", confUrl);
      fd.append("reference_id", refId);
      if (shot) fd.append("screenshot", shot);
      const r = await api.postForm("/jobs/assisted/record", fd);
      setResult(r);
      if (r.verified) toast("Verified Submitted ✓ — evidence saved", "success");
      else toast(`Recorded as ${r.display_status}`, "info");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={!!job} onClose={onClose} title="Assisted Apply" width="max-w-2xl">
      {error ? (
        <div className="space-y-3">
          <div className="badge border-danger/40 text-danger w-full justify-center py-2">{error}</div>
          {error.toLowerCase().includes("resume") && (
            <p className="text-sm text-muted">Upload your resume first, then try again.</p>
          )}
        </div>
      ) : !prep ? (
        <Spinner />
      ) : (
        <div className="space-y-4">
          {/* Header: portal + job */}
          <div className="flex items-center justify-between">
            <div>
              <div className="font-semibold">{job.title}</div>
              <div className="text-sm text-muted">{job.company}</div>
            </div>
            <span className="badge border-blue-400/40 text-blue-600">{prep.platform} · Assisted</span>
          </div>

          <Stepper step={step} />

          {step === 1 && (
            <div className="space-y-4">
              {/* Resume being used */}
              <Row label="Resume">
                {prep.resume_filename
                  ? <span className="text-ink">📄 {prep.resume_filename}</span>
                  : <span className="text-danger">No resume — upload one first</span>}
              </Row>

              {/* Required fields (prefilled) */}
              <div>
                <div className="label">Details we'll fill from your profile</div>
                <div className="card divide-y divide-line">
                  {prep.required_fields.map((f) => (
                    <div key={f.label} className="flex items-center justify-between px-3 py-2 text-sm">
                      <span className="text-muted">{f.label}{f.required && " *"}</span>
                      <span className={f.value ? "text-ink" : "text-muted/60"}>
                        {f.value || (f.required ? "— add on portal" : "—")}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Screening questions note */}
              <div className="card p-3 text-sm border-yellow-500/30">
                <div className="text-amber-600 font-medium mb-1">Screening questions</div>
                {prep.screening_note}
              </div>

              {/* Captcha note */}
              <div className="text-xs text-muted">🔒 {prep.captcha_note}</div>

              <button className="btn-primary w-full" onClick={openPortal} disabled={!prep.resume_filename}>
                Open {prep.platform} application ↗
              </button>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <ol className="text-sm text-muted space-y-1 list-decimal pl-5">
                {prep.instructions.map((s, i) => <li key={i}>{s}</li>)}
              </ol>
              {!opened && (
                <button className="btn-ghost w-full" onClick={openPortal}>Re-open application ↗</button>
              )}
              <div className="card p-4 space-y-3">
                <div className="font-medium text-sm">Record your confirmation</div>
                <div>
                  <label className="label">Confirmation URL (the page after you submitted)</label>
                  <input className="input" value={confUrl} onChange={(e) => setConfUrl(e.target.value)}
                         placeholder="https://jobs.lever.co/.../thanks" />
                </div>
                <div>
                  <label className="label">Reference / application ID (if shown)</label>
                  <input className="input" value={refId} onChange={(e) => setRefId(e.target.value)}
                         placeholder="e.g. LVR-XXXX (optional)" />
                </div>
                <div>
                  <label className="label">Confirmation screenshot</label>
                  <input type="file" accept="image/*" onChange={(e) => setShot(e.target.files?.[0] || null)}
                         className="text-sm text-muted" />
                </div>
                <p className="text-xs text-muted">
                  Verified Submitted needs all three: reference ID + confirmation URL + screenshot.
                  Otherwise it's recorded as <b className="text-ink">Submitted</b>.
                </p>
                <button className="btn-primary w-full" disabled={busy} onClick={record}>
                  {busy ? "Saving…" : "Save & verify"}
                </button>
              </div>

              {result && (
                <div className="card p-4 space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted">Result:</span>
                    <StatusBadge status={result.display_status} />
                  </div>
                  {result.missing?.length > 0 && (
                    <div className="text-xs text-amber-600">
                      Missing for full verification: {result.missing.join(", ")}
                    </div>
                  )}
                  <button className="btn-primary w-full mt-2"
                          onClick={() => { onDone?.(result.display_status); onClose(); }}>
                    Done
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

function Stepper({ step }) {
  const steps = ["Review", "Apply & record"];
  return (
    <div className="flex gap-2 text-xs">
      {steps.map((s, i) => (
        <span key={s}
              className={`badge ${step >= i + 1 ? "bg-brand text-white border-brand" : "border-line text-muted"}`}>
          {i + 1}. {s}
        </span>
      ))}
    </div>
  );
}

function Row({ label, children }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="label !mb-0">{label}</span>
      <span>{children}</span>
    </div>
  );
}

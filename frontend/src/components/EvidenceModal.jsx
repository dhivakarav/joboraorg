import { useEffect, useState } from "react";
import { api } from "../api/client";
import { Modal, Spinner, StatusBadge } from "./UI";

// Submission Evidence viewer: confirmation screenshot, URL, application ID, timestamp.
export default function EvidenceModal({ application, onClose }) {
  const [ev, setEv] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!application) return;
    setEv(null);
    setError("");
    api
      .get(`/applications/${application.id}/evidence`)
      .then(setEv)
      .catch((e) => setError(e.message));
  }, [application]);

  if (!application) return null;

  // Backend returns a short-lived, evidence-scoped URL (or S3 presigned).
  const shotUrl = ev?.has_screenshot ? ev.screenshot_url : null;

  return (
    <Modal open={!!application} onClose={onClose} title="Submission evidence" width="max-w-2xl">
      {error ? (
        <div className="badge border-danger/40 text-danger w-full justify-center py-2">{error}</div>
      ) : !ev ? (
        <Spinner />
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-semibold">{application.job_title}</div>
              <div className="text-sm text-muted">{application.company} · {application.platform || application.portal}</div>
            </div>
            <StatusBadge status={ev.display_status} />
          </div>

          {ev.display_status === "Verified Submitted" ? (
            <div className="badge border-success/50 text-success w-full justify-center py-2">
              ✓ Verified — application ID + confirmation URL + screenshot on file
            </div>
          ) : (
            <div className="badge border-line text-muted w-full justify-center py-2">
              Unverified — missing {[
                !(ev.reference_id) && "application ID",
                !(ev.confirmation_url) && "confirmation URL",
                !(ev.evidence_available) && "screenshot",
              ].filter(Boolean).join(", ") || "evidence"}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3 text-sm">
            <Info label="Submission status (pipeline)" value={ev.submission_status} />
            <Info label="Application ID" value={ev.reference_id || ev.external_application_id || "—"} />
            <Info label="Submitted at" value={ev.submitted_at ? new Date(ev.submitted_at).toLocaleString() : "—"} />
            <Info label="Confirmation URL" value={
              ev.confirmation_url
                ? <a className="text-white underline break-all" href={ev.confirmation_url} target="_blank" rel="noreferrer">{ev.confirmation_url}</a>
                : "—"
            } />
          </div>

          {ev.failure_reason && (
            <div className="card p-3 text-sm border-yellow-500/30">
              <span className="text-yellow-400 font-medium">Reason:</span> {ev.failure_reason}
            </div>
          )}

          <div>
            <div className="label">Confirmation screenshot</div>
            {shotUrl ? (
              <a href={shotUrl} target="_blank" rel="noreferrer">
                <img src={shotUrl} alt="confirmation evidence"
                     className="w-full rounded-card border border-line" />
              </a>
            ) : (
              <div className="card p-6 text-center text-muted text-sm">
                No confirmation screenshot — this application was not verified-submitted.
              </div>
            )}
          </div>

          {ev.platform_response && (
            <div>
              <div className="label">Platform response (captured)</div>
              <pre className="card p-3 text-xs whitespace-pre-wrap max-h-40 overflow-y-auto">{ev.platform_response}</pre>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

function Info({ label, value }) {
  return (
    <div>
      <div className="text-xs text-muted">{label}</div>
      <div className="font-medium break-words">{value}</div>
    </div>
  );
}

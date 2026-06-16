import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { EvidenceCell, Spinner, StatusBadge, useToast } from "../../components/UI";
import EvidenceModal from "../../components/EvidenceModal";

// Verification Center — proof of every submission attempt: application ID,
// confirmation URL, screenshot evidence, timestamp, portal, verification status.
const APPLY_STATES = ["Verified Submitted", "Submitted", "Manual Apply", "Failed"];

export default function VerificationCenter() {
  const toast = useToast();
  const [rows, setRows] = useState(null);
  const [evidenceApp, setEvidenceApp] = useState(null);
  const [onlyVerified, setOnlyVerified] = useState(false);

  async function load() {
    try {
      const d = await api.get("/applications?page=1&page_size=100");
      setRows(d.items || []);
    } catch (e) {
      toast(e.message, "error");
    }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  if (!rows) return <Spinner />;

  // Submission attempts only (exclude pure Tracked/Draft).
  let items = rows.filter((r) => APPLY_STATES.includes(r.display_status));
  if (onlyVerified) items = items.filter((r) => r.display_status === "Verified Submitted");
  const verifiedCount = rows.filter((r) => r.display_status === "Verified Submitted").length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Verification Center</h1>
        <p className="text-sm text-muted">
          Proof of every submission — only <b className="text-white">Verified Submitted</b> means a
          confirmation, application ID, and screenshot are all on file.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="Verified Submitted" value={verifiedCount} accent="text-success" />
        <Stat label="Submission attempts" value={rows.filter((r) => APPLY_STATES.includes(r.display_status)).length} />
        <Stat label="Tracked (not submitted)" value={rows.filter((r) => r.display_status === "Tracked").length} accent="text-blue-300" />
        <Stat label="Total applications" value={rows.length} />
      </div>

      <label className="flex items-center gap-2 text-sm w-fit cursor-pointer">
        <input type="checkbox" className="accent-white h-4 w-4"
               checked={onlyVerified} onChange={(e) => setOnlyVerified(e.target.checked)} />
        Show only Verified Submitted
      </label>

      <div className="card p-5">
        {items.length === 0 ? (
          <p className="text-sm text-muted py-8 text-center">
            No submission attempts yet. Apply to a role from <b className="text-white">Find Jobs</b> —
            assisted applies (Lever/Ashby) let you record your confirmation here.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted border-b border-line">
                  <th className="py-2 pr-3 font-medium">Role</th>
                  <th className="py-2 pr-3 font-medium">Portal</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 pr-3 font-medium">Application ID</th>
                  <th className="py-2 pr-3 font-medium">Confirmation</th>
                  <th className="py-2 pr-3 font-medium">Submitted</th>
                  <th className="py-2 pr-3 font-medium">Evidence</th>
                </tr>
              </thead>
              <tbody>
                {items.map((r) => (
                  <tr key={r.id} className="border-b border-line/50">
                    <td className="py-2.5 pr-3">
                      <div>{r.job_title}</div>
                      <div className="text-xs text-muted">{r.company}</div>
                    </td>
                    <td className="py-2.5 pr-3">{r.platform || r.portal}</td>
                    <td className="py-2.5 pr-3"><StatusBadge status={r.display_status} /></td>
                    <td className="py-2.5 pr-3 font-mono text-xs">
                      {r.application_id || r.external_application_id || "—"}
                    </td>
                    <td className="py-2.5 pr-3">
                      {r.confirmation_url
                        ? <a href={r.confirmation_url} target="_blank" rel="noreferrer"
                             className="text-white underline underline-offset-2 break-all">Open ↗</a>
                        : "—"}
                    </td>
                    <td className="py-2.5 pr-3 text-muted whitespace-nowrap">
                      {r.submitted_at ? new Date(r.submitted_at).toLocaleString() : "—"}
                    </td>
                    <td className="py-2.5 pr-3">
                      <EvidenceCell row={r} onView={setEvidenceApp} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <EvidenceModal application={evidenceApp} onClose={() => setEvidenceApp(null)} />
    </div>
  );
}

function Stat({ label, value, accent }) {
  return (
    <div className="card-elevated p-4">
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      <div className={`mt-1 text-2xl font-bold ${accent || "text-white"}`}>{value}</div>
    </div>
  );
}

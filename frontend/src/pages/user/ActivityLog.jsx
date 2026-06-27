import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { ApplyModeBadge, EvidenceCell, Spinner, StatusBadge, useToast } from "../../components/UI";
import EvidenceModal from "../../components/EvidenceModal";

const SOURCES = ["Remotive", "Arbeitnow", "Greenhouse", "Lever", "Ashby", "SmartRecruiters",
                 "TheMuse", "RemoteOK", "Jobicy", "Workable", "Wellfound", "JSearch",
                 "Adzuna", "Jooble", "Internshala"];
const CANONICAL = ["Draft", "Tracked", "Manual Apply", "Pending Approval", "Queued",
                   "Submitted", "Submitted (Unverified)", "Verified Submitted",
                   "Failed", "Failed — No Confirmation", "Failed — Form Not Found",
                   "Failed — Submit Not Found", "Interview", "Offer", "Rejected"];
const USER_STAGES = ["Tracked", "Interview", "Offer", "Rejected", "Saved", "Skipped"];

// Statuses that represent real in-flight or confirmed submissions — not deletable.
const NON_DELETABLE = new Set(["Queued", "Processing", "Submitted",
                                "Verified Submitted", "Submitted (Unverified)"]);

export default function ActivityLog() {
  const toast = useToast();
  const [evidenceApp, setEvidenceApp] = useState(null);
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [portal, setPortal] = useState("");
  const [status, setStatus] = useState("");
  const [deleting, setDeleting] = useState(null);
  const pageSize = 20;

  async function load() {
    const qs = new URLSearchParams({ page, page_size: pageSize });
    if (portal) qs.set("portal", portal);
    if (status) qs.set("status", status);
    setData(await api.get(`/applications?${qs}`));
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, portal, status]);

  async function setStage(appId, stage) {
    try {
      await api.patch(`/applications/${appId}/status`, { status: stage });
      toast(`Marked as ${stage}`, "success");
      load();
    } catch (e) {
      toast(e.message, "error");
    }
  }

  async function deleteApp(r) {
    if (!window.confirm(`Remove "${r.job_title}" at ${r.company} from your Activity Log?`)) return;
    setDeleting(r.id);
    try {
      await api.del(`/applications/${r.id}`);
      toast("Application removed from Activity Log", "success");
      load();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setDeleting(null);
    }
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1;

  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-ink">Activity Log</h1>
        <p className="text-sm text-muted">Track every application through its lifecycle</p>
      </div>

      <div className="flex flex-wrap gap-3">
        <select className="input w-auto" value={portal} onChange={(e) => { setPortal(e.target.value); setPage(1); }}>
          <option value="">All sources</option>
          {SOURCES.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select className="input w-auto" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="">All statuses</option>
          {CANONICAL.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <div className="card p-5">
        {!data ? (
          <Spinner />
        ) : data.items.length === 0 ? (
          <p className="text-sm text-muted py-8 text-center">No applications match these filters.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted border-b border-line">
                  <th className="py-2 pr-3 font-medium">Date</th>
                  <th className="py-2 pr-3 font-medium">Job title</th>
                  <th className="py-2 pr-3 font-medium">Company</th>
                  <th className="py-2 pr-3 font-medium">Platform</th>
                  <th className="py-2 pr-3 font-medium">Match</th>
                  <th className="py-2 pr-3 font-medium">Salary (INR)</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 pr-3 font-medium">Mode</th>
                  <th className="py-2 pr-3 font-medium">Stage</th>
                  <th className="py-2 pr-3 font-medium">Submission</th>
                  <th className="py-2 pr-3 font-medium">Evidence</th>
                  <th className="py-2 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((r) => (
                  <tr key={r.id} className="border-b border-line/50">
                    <td className="py-2.5 pr-3 text-muted whitespace-nowrap">{new Date(r.applied_at).toLocaleDateString()}</td>
                    <td className="py-2.5 pr-3">{r.job_title}</td>
                    <td className="py-2.5 pr-3 text-muted">{r.company}</td>
                    <td className="py-2.5 pr-3">{r.platform || r.portal}</td>
                    <td className="py-2.5 pr-3">{r.match_score ? `${r.match_score}%` : "—"}</td>
                    <td className="py-2.5 pr-3 text-muted">{r.salary_inr || "—"}</td>
                    <td className="py-2.5 pr-3">
                      <StatusBadge status={r.display_status} />
                    </td>
                    <td className="py-2.5 pr-3">
                      <div className="flex items-center gap-2">
                        <ApplyModeBadge mode={r.application_mode} />
                        {r.application_mode === "manual_link_provided" && r.apply_url && (
                          <a href={r.apply_url} target="_blank" rel="noopener noreferrer"
                             className="text-ink underline underline-offset-2 hover:text-muted text-xs whitespace-nowrap">
                            Open Job ↗
                          </a>
                        )}
                      </div>
                    </td>
                    <td className="py-2.5 pr-3">
                      <select className="input w-auto text-xs py-1"
                              value={r.pipeline_stage || ""}
                              onChange={(e) => e.target.value && setStage(r.id, e.target.value)}
                              title="Set your pipeline stage (self-reported)">
                        <option value="">— set stage</option>
                        {USER_STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </td>
                    <td className="py-2.5 pr-3 text-muted text-xs">
                      {r.submission_status || "Draft"}
                    </td>
                    <td className="py-2.5 pr-3">
                      <EvidenceCell row={r} onView={setEvidenceApp} />
                    </td>
                    <td className="py-2.5">
                      {!NON_DELETABLE.has(r.display_status) && (
                        <button
                          onClick={() => deleteApp(r)}
                          disabled={deleting === r.id}
                          title="Remove from Activity Log"
                          className="text-muted hover:text-red-500 transition-colors p-1 rounded disabled:opacity-40"
                          aria-label="Delete application">
                          {deleting === r.id ? "…" : "✕"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {data && data.total > 0 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted">{data.total} total · page {page} of {totalPages}</span>
          <div className="flex gap-2">
            <button className="btn-ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Prev</button>
            <button className="btn-ghost" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next</button>
          </div>
        </div>
      )}

      <EvidenceModal application={evidenceApp} onClose={() => setEvidenceApp(null)} />
    </div>
  );
}

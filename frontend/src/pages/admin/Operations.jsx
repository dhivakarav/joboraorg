import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { StatCard, Spinner, useToast } from "../../components/UI";

// Admin Operations: beta metrics funnel + feedback/bug triage + invite codes.
// Surfaces the existing /api/admin/{metrics,feedback,invites} endpoints.
export default function Operations() {
  const toast = useToast();
  const [tab, setTab] = useState("metrics");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Operations</h1>
        <p className="text-sm text-muted">Beta metrics, feedback &amp; bug reports, and invite codes</p>
      </div>

      <div className="flex flex-wrap gap-2">
        {[["metrics", "Metrics"], ["feedback", "Feedback & Bugs"], ["invites", "Invites"]].map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)}
                  className={`badge px-3 py-1.5 ${tab === k ? "bg-white text-black border-white" : "border-line text-muted hover:text-white"}`}>
            {label}
          </button>
        ))}
      </div>

      {tab === "metrics" && <Metrics toast={toast} />}
      {tab === "feedback" && <Feedback toast={toast} />}
      {tab === "invites" && <Invites toast={toast} />}
    </div>
  );
}

// ---------------- Metrics ----------------
function Metrics({ toast }) {
  const [m, setM] = useState(null);
  useEffect(() => { api.get("/admin/metrics").then(setM).catch((e) => toast(e.message, "error")); }, []);
  if (!m) return <Spinner />;
  return (
    <div className="space-y-6">
      <Section title="Users">
        <StatCard label="Total" value={m.users.total} />
        <StatCard label="Pending" value={m.users.pending} accent="text-yellow-400" />
        <StatCard label="Approved" value={m.users.approved} accent="text-success" />
        <StatCard label="New this week" value={m.users.new_this_week} accent="text-blue-300" />
      </Section>
      <Section title="Funnel">
        <StatCard label="Signed up" value={m.funnel.signed_up} />
        <StatCard label="Uploaded resume" value={m.funnel.uploaded_resume} accent="text-blue-300" />
        <StatCard label="Tracked a job" value={m.funnel.tracked_a_job} accent="text-blue-300" />
      </Section>
      <Section title="Applications">
        <StatCard label="Verified Submitted" value={m.applications.verified_submitted} accent="text-success" />
        <StatCard label="Submitted" value={m.applications.submitted} accent="text-blue-300" />
        <StatCard label="Manual Apply" value={m.applications.manual_apply} accent="text-yellow-400" />
        <StatCard label="Tracked / Draft" value={m.applications.tracked_or_draft} />
        <StatCard label="Failed" value={m.applications.failed} accent="text-danger" />
        <StatCard label="Total" value={m.applications.total} />
      </Section>
      <Section title="Feedback &amp; Invites">
        <StatCard label="Open feedback" value={m.feedback.open} accent="text-yellow-400" />
        <StatCard label="Open bugs" value={m.feedback.bugs_open} accent="text-danger" />
        <StatCard label="Invites used" value={`${m.invites.used}/${m.invites.total}`} />
      </Section>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div>
      <h2 className="font-semibold mb-3">{title}</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">{children}</div>
    </div>
  );
}

// ---------------- Feedback & Bugs ----------------
function Feedback({ toast }) {
  const [rows, setRows] = useState(null);
  const [kind, setKind] = useState("");
  const load = () => {
    const qs = new URLSearchParams();
    if (kind) qs.set("kind", kind);
    api.get(`/admin/feedback?${qs}`).then((d) => setRows(d.feedback)).catch((e) => toast(e.message, "error"));
  };
  useEffect(() => { load(); }, [kind]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!rows) return <Spinner />;
  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {[["", "All"], ["feedback", "💡 Feedback"], ["bug", "🐞 Bugs"]].map(([k, l]) => (
          <button key={k} onClick={() => setKind(k)}
                  className={`badge px-3 py-1.5 ${kind === k ? "bg-white text-black border-white" : "border-line text-muted"}`}>{l}</button>
        ))}
      </div>
      <div className="card p-5">
        {rows.length === 0 ? (
          <p className="text-sm text-muted py-8 text-center">No {kind || "feedback"} yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted border-b border-line">
                  <th className="py-2 pr-3 font-medium">Type</th>
                  <th className="py-2 pr-3 font-medium">Message</th>
                  <th className="py-2 pr-3 font-medium">Page</th>
                  <th className="py-2 pr-3 font-medium">Rating</th>
                  <th className="py-2 pr-3 font-medium">Severity</th>
                  <th className="py-2 pr-3 font-medium">Contact</th>
                  <th className="py-2 pr-3 font-medium">When</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-b border-line/50 align-top">
                    <td className="py-2.5 pr-3">{r.kind === "bug" ? "🐞 Bug" : "💡"}</td>
                    <td className="py-2.5 pr-3 max-w-xs whitespace-pre-wrap">{r.message}</td>
                    <td className="py-2.5 pr-3 text-muted">{r.page || "—"}</td>
                    <td className="py-2.5 pr-3">{r.rating ? "★".repeat(r.rating) : "—"}</td>
                    <td className="py-2.5 pr-3">{r.severity || "—"}</td>
                    <td className="py-2.5 pr-3 text-muted">{r.contact_email || "—"}</td>
                    <td className="py-2.5 pr-3 text-muted whitespace-nowrap">{new Date(r.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------- Invites ----------------
function Invites({ toast }) {
  const [rows, setRows] = useState(null);
  const [count, setCount] = useState(5);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api.get("/admin/invites").then((d) => setRows(d.invites)).catch((e) => toast(e.message, "error"));
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function generate() {
    setBusy(true);
    try {
      const qs = new URLSearchParams({ count: String(count) });
      if (note) qs.set("note", note);
      const r = await api.post(`/admin/invites?${qs}`);
      toast(`Generated ${r.created} invite code(s)`, "success");
      setNote("");
      load();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setBusy(false);
    }
  }

  function copy(code) {
    navigator.clipboard?.writeText(code);
    toast("Copied", "info");
  }

  if (!rows) return <Spinner />;
  return (
    <div className="space-y-4">
      <div className="card p-4 flex flex-wrap gap-3 items-end">
        <div>
          <label className="label">How many</label>
          <input type="number" min="1" max="200" className="input w-24" value={count}
                 onChange={(e) => setCount(Number(e.target.value))} />
        </div>
        <div className="flex-1 min-w-[180px]">
          <label className="label">Note (optional)</label>
          <input className="input" value={note} onChange={(e) => setNote(e.target.value)}
                 placeholder="e.g. Wave 1 — SRM students" />
        </div>
        <button className="btn-primary" disabled={busy} onClick={generate}>
          {busy ? "Generating…" : "Generate codes"}
        </button>
      </div>

      <div className="card p-5">
        {rows.length === 0 ? (
          <p className="text-sm text-muted py-8 text-center">No invite codes yet. Generate some above.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted border-b border-line">
                  <th className="py-2 pr-3 font-medium">Code</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 pr-3 font-medium">Used by</th>
                  <th className="py-2 pr-3 font-medium">Note</th>
                  <th className="py-2 pr-3 font-medium">Created</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.code} className="border-b border-line/50">
                    <td className="py-2.5 pr-3 font-mono">
                      <button onClick={() => copy(r.code)} className="hover:text-white" title="Copy">{r.code} ⧉</button>
                    </td>
                    <td className="py-2.5 pr-3">
                      <span className={`badge ${r.used ? "border-line text-muted" : "border-success/40 text-success"}`}>
                        {r.used ? "Used" : "Available"}
                      </span>
                    </td>
                    <td className="py-2.5 pr-3 text-muted">{r.used_by_email || "—"}</td>
                    <td className="py-2.5 pr-3 text-muted">{r.note || "—"}</td>
                    <td className="py-2.5 pr-3 text-muted whitespace-nowrap">{new Date(r.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

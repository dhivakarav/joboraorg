import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { Spinner, StatusBadge } from "../../components/UI";

const PORTALS = ["LinkedIn", "Naukri", "Indeed", "Foundit", "Bayt", "JobStreet"];
// Canonical, evidence-gated statuses (filter values). "Applied" is retired.
const STATUSES = ["Draft", "Tracked", "Manual Apply", "Submitted", "Verified Submitted", "Failed"];

export default function AllApplications() {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ portal: "", status: "", date_from: "", date_to: "" });
  const pageSize = 20;

  async function load() {
    const qs = new URLSearchParams({ page, page_size: pageSize });
    Object.entries(filters).forEach(([k, v]) => v && qs.set(k, v));
    setData(await api.get(`/admin/applications?${qs}`));
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, filters]);

  function setF(k, v) {
    setFilters((s) => ({ ...s, [k]: v }));
    setPage(1);
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">All Applications</h1>
        <p className="text-sm text-muted">Every application across all users</p>
      </div>

      <div className="flex flex-wrap gap-3 items-end">
        <select className="input w-auto" value={filters.portal} onChange={(e) => setF("portal", e.target.value)}>
          <option value="">All portals</option>
          {PORTALS.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select className="input w-auto" value={filters.status} onChange={(e) => setF("status", e.target.value)}>
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <div>
          <label className="label">From</label>
          <input type="date" className="input w-auto" value={filters.date_from} onChange={(e) => setF("date_from", e.target.value)} />
        </div>
        <div>
          <label className="label">To</label>
          <input type="date" className="input w-auto" value={filters.date_to} onChange={(e) => setF("date_to", e.target.value)} />
        </div>
      </div>

      <div className="card p-5 overflow-x-auto">
        {!data ? (
          <Spinner />
        ) : data.items.length === 0 ? (
          <p className="text-sm text-muted py-8 text-center">No applications match these filters.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted border-b border-line">
                <th className="py-2 pr-4 font-medium">Timestamp</th>
                <th className="py-2 pr-4 font-medium">Portal</th>
                <th className="py-2 pr-4 font-medium">Job title</th>
                <th className="py-2 pr-4 font-medium">Company</th>
                <th className="py-2 pr-4 font-medium">Location</th>
                <th className="py-2 pr-4 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((r) => (
                <tr key={r.id} className="border-b border-line/50">
                  <td className="py-2.5 pr-4 text-muted">{new Date(r.applied_at).toLocaleString()}</td>
                  <td className="py-2.5 pr-4">{r.portal}</td>
                  <td className="py-2.5 pr-4">{r.job_title}</td>
                  <td className="py-2.5 pr-4 text-muted">{r.company}</td>
                  <td className="py-2.5 pr-4 text-muted">{r.location}</td>
                  <td className="py-2.5 pr-4"><StatusBadge status={r.display_status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
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
    </div>
  );
}

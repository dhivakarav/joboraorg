import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { Spinner, StatusBadge, Modal, useToast } from "../../components/UI";

export default function UserManagement() {
  const toast = useToast();
  const [users, setUsers] = useState(null);
  const [details, setDetails] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);

  async function load() {
    setUsers(await api.get("/admin/users"));
  }
  useEffect(() => {
    load();
  }, []);

  async function approve(id) {
    try {
      await api.post(`/admin/users/${id}/approve`);
      toast("User approved", "success");
      load();
    } catch (e) {
      toast(e.message, "error");
    }
  }
  async function suspend(id) {
    try {
      await api.post(`/admin/users/${id}/suspend`);
      toast("User suspended", "info");
      load();
    } catch (e) {
      toast(e.message, "error");
    }
  }
  async function view(id) {
    setLoadingDetails(true);
    setDetails({});
    try {
      setDetails(await api.get(`/admin/users/${id}/details`));
    } finally {
      setLoadingDetails(false);
    }
  }

  if (!users) return <Spinner />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">User Management</h1>
        <p className="text-sm text-muted">Approve, suspend, and inspect users</p>
      </div>

      <div className="card p-5 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted border-b border-line">
              <th className="py-2 pr-4 font-medium">Name</th>
              <th className="py-2 pr-4 font-medium">Email</th>
              <th className="py-2 pr-4 font-medium">Registered</th>
              <th className="py-2 pr-4 font-medium">Apps</th>
              <th className="py-2 pr-4 font-medium">Status</th>
              <th className="py-2 pr-4 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-line/50">
                <td className="py-3 pr-4 font-medium">{u.full_name}</td>
                <td className="py-3 pr-4 text-muted">{u.email}</td>
                <td className="py-3 pr-4 text-muted">{new Date(u.created_at).toLocaleDateString()}</td>
                <td className="py-3 pr-4">{u.application_count}</td>
                <td className="py-3 pr-4"><StatusBadge status={u.status} /></td>
                <td className="py-3 pr-4">
                  <div className="flex gap-2">
                    {u.status !== "approved" && (
                      <button className="btn-success !px-3 !py-1 text-xs" onClick={() => approve(u.id)}>Approve</button>
                    )}
                    {u.status !== "suspended" && (
                      <button className="btn-danger !px-3 !py-1 text-xs" onClick={() => suspend(u.id)}>Suspend</button>
                    )}
                    <button className="btn-ghost !px-3 !py-1 text-xs" onClick={() => view(u.id)}>View</button>
                  </div>
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr><td colSpan={6} className="py-8 text-center text-muted">No users registered yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <Modal open={!!details} onClose={() => setDetails(null)} title="User details" width="max-w-lg">
        {loadingDetails || !details?.user ? (
          <Spinner />
        ) : (
          <div className="space-y-4 text-sm">
            <div className="grid grid-cols-2 gap-3">
              <Info label="Name" value={details.user.full_name} />
              <Info label="Email" value={details.user.email} />
              <Info label="Phone" value={details.user.phone || "—"} />
              <Info label="Experience" value={`${details.user.years_experience} yrs`} />
              <Info label="Job title" value={details.user.job_title || "—"} />
              <Info label="Status" value={details.user.status} />
              <Info label="Resume" value={details.has_resume ? "Uploaded" : "Not uploaded"} />
              <Info label="Total applications" value={details.total_applications} />
            </div>
            <div>
              <div className="label">Recent activity</div>
              {details.recent_activity.length === 0 ? (
                <span className="text-muted">No activity</span>
              ) : (
                <div className="space-y-1 max-h-40 overflow-y-auto">
                  {details.recent_activity.map((a) => (
                    <div key={a.id} className="flex items-center justify-between border-b border-line/40 py-1">
                      <span>{a.portal} · {a.job_title}</span>
                      <StatusBadge status={a.display_status} />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div>
      <div className="text-xs text-muted">{label}</div>
      <div className="font-medium">{value}</div>
    </div>
  );
}

import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { StatCard, Spinner } from "../../components/UI";

export default function AdminDashboard() {
  const [stats, setStats] = useState(null);
  useEffect(() => {
    api.get("/admin/stats").then(setStats);
  }, []);

  if (!stats) return <Spinner />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Admin Dashboard</h1>
        <p className="text-sm text-muted">Platform-wide overview</p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Users" value={stats.total_users} />
        <StatCard label="Pending Approvals" value={stats.pending_approvals} accent="text-yellow-400" />
        <StatCard label="Approved Users" value={stats.approved_users} accent="text-success" />
        <StatCard label="Total Applications" value={stats.total_applications} />
      </div>
    </div>
  );
}

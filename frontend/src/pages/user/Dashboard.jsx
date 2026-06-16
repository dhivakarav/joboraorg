import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, getToken, BASE } from "../../api/client";
import { StatCard, StatusBadge, Spinner, useToast } from "../../components/UI";
import { useAuth } from "../../context/AuthContext";
import HowItWorks from "../../components/HowItWorks";

export default function Dashboard() {
  const toast = useToast();
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [hasResume, setHasResume] = useState(null);
  const [running, setRunning] = useState(false);
  const [log, setLog] = useState([]);
  const esRef = useRef(null);
  const logEndRef = useRef(null);

  async function loadStats() {
    try {
      setStats(await api.get("/dashboard/stats"));
      const r = await api.get("/resume/parsed");
      setHasResume(!!r.has_resume);
    } catch (e) {
      toast(e.message, "error");
    }
  }

  useEffect(() => {
    loadStats();
    api.get("/apply/status").then((s) => s.running && openStream());
    return () => esRef.current?.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [log]);

  function openStream() {
    if (esRef.current) esRef.current.close();
    const es = new EventSource(`${BASE}/apply/stream?token=${encodeURIComponent(getToken())}`);
    esRef.current = es;
    setRunning(true);
    es.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === "connected") return;
      if (data.type === "done") {
        setRunning(false);
        es.close();
        loadStats();
        toast(data.message || "Finished", "success");
      }
      if (data.type === "error") toast(data.message, "error");
      setLog((l) => [...l.slice(-60), data]);
    };
    es.onerror = () => {
      es.close();
      setRunning(false);
    };
  }

  async function start() {
    setLog([]);
    try {
      await api.post("/apply/start");
      openStream();
      toast("Scanning your profile and tracking matching roles…", "success");
    } catch (e) {
      toast(e.message, "error");
    }
  }

  async function stop() {
    try {
      await api.post("/apply/stop");
      esRef.current?.close();
      setRunning(false);
      loadStats();
      toast("Stopped", "info");
    } catch (e) {
      toast(e.message, "error");
    }
  }

  if (!stats) return <Spinner />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-sm text-muted">Overview of your real job-application activity</p>
        </div>
        {running ? (
          <button className="btn-danger" onClick={stop}>
            ■ Stop
          </button>
        ) : (
          <button className="btn-primary" onClick={start} title="Scan your resume, find matching roles, and track them (no auto-submission)">
            ⚡ Scan &amp; Track Matches
          </button>
        )}
      </div>

      <HowItWorks />

      <GettingStarted
        seekerSet={!!user?.seeker_type}
        hasResume={!!hasResume}
        hasApplied={stats.total > 0}
      />

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <StatCard label="Verified Submitted" value={stats.verified_submitted} accent="text-success" />
        <StatCard label="Submitted" value={stats.submitted} accent="text-blue-300" />
        <StatCard label="Manual Apply" value={stats.manual_apply} accent="text-yellow-400" />
        <StatCard label="Tracked" value={stats.tracked} accent="text-blue-300" />
        <StatCard label="Total" value={stats.total} />
      </div>

      {(running || log.length > 0) && (
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-3">
            {running && <span className="h-2 w-2 rounded-full bg-success animate-pulse" />}
            <h2 className="font-semibold">Live activity {running ? "(running)" : ""}</h2>
          </div>
          <div className="max-h-60 overflow-y-auto rounded-btn bg-input border border-inputline p-3 font-mono text-xs space-y-1">
            {log.map((e, i) => (
              <div key={i} className="text-muted">
                {e.type === "log" ? (
                  <span>
                    <span className="text-white">[{e.portal}]</span> {e.job_title} @ {e.company} —{" "}
                    <span
                      className={
                        e.status === "Verified Submitted"
                          ? "text-success"
                          : e.status === "Tracked" || e.status === "Submitted" || e.status === "Saved"
                          ? "text-blue-300"
                          : e.status === "Failed"
                          ? "text-danger"
                          : e.status === "Manual Apply"
                          ? "text-yellow-400"
                          : ""
                      }
                    >
                      {e.status === "Applied" ? "Tracked" : e.status}
                    </span>
                  </span>
                ) : (
                  <span>» {e.message}</span>
                )}
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        </div>
      )}

      <div className="card p-5">
        <h2 className="font-semibold mb-4">Recent activity</h2>
        {stats.recent_activity.length === 0 ? (
          <p className="text-sm text-muted py-6 text-center">
            No activity yet. Browse <b className="text-white">Find Jobs</b> or hit{" "}
            <b className="text-white">Scan &amp; Track Matches</b>.
          </p>
        ) : (
          <Table rows={stats.recent_activity} />
        )}
      </div>
    </div>
  );
}

function GettingStarted({ seekerSet, hasResume, hasApplied }) {
  const steps = [
    { done: seekerSet, label: "Tell us your job stage", to: "/app/settings", cta: "Set preference" },
    { done: hasResume, label: "Upload your resume", to: "/app/resume", cta: "Upload" },
    { done: hasApplied, label: "Apply to your first job", to: "/app/jobs", cta: "Find jobs" },
  ];
  const done = steps.filter((s) => s.done).length;
  const pct = Math.round((done / steps.length) * 100);
  if (done === steps.length) return null; // hide once onboarding is complete

  return (
    <div className="card-elevated p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold">Getting started</h2>
        <span className="text-sm text-muted">{done}/{steps.length} complete</span>
      </div>
      <div className="h-2 w-full rounded-full bg-input overflow-hidden mb-4">
        <div className="h-full bg-white transition-all" style={{ width: `${pct}%` }} />
      </div>
      <div className="space-y-2">
        {steps.map((s) => (
          <div key={s.label} className="flex items-center justify-between text-sm">
            <span className={s.done ? "text-muted line-through" : "text-white"}>
              {s.done ? "✓" : "○"} {s.label}
            </span>
            {!s.done && (
              <Link to={s.to} className="btn-ghost !px-3 !py-1 text-xs">{s.cta}</Link>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function Table({ rows }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-muted border-b border-line">
            <th className="py-2 pr-4 font-medium">Time</th>
            <th className="py-2 pr-4 font-medium">Portal</th>
            <th className="py-2 pr-4 font-medium">Job</th>
            <th className="py-2 pr-4 font-medium">Company</th>
            <th className="py-2 pr-4 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-b border-line/50">
              <td className="py-2.5 pr-4 text-muted">{new Date(r.applied_at).toLocaleString()}</td>
              <td className="py-2.5 pr-4">{r.portal}</td>
              <td className="py-2.5 pr-4">{r.job_title}</td>
              <td className="py-2.5 pr-4 text-muted">{r.company}</td>
              <td className="py-2.5 pr-4">
                <StatusBadge status={r.display_status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

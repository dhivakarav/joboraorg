import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, getToken, BASE } from "../../api/client";
import { ApplyModeBadge, StatCard, StatusBadge, Spinner, useToast } from "../../components/UI";
import { useAuth } from "../../context/AuthContext";
import HowItWorks from "../../components/HowItWorks";

export default function Dashboard() {
  const toast = useToast();
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [pending, setPending] = useState(null);
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

  function loadPending() {
    api.get("/apply/pending").then(setPending).catch(() => {});
  }

  const [refreshing, setRefreshing] = useState(false);
  async function loadAnalytics(refresh = false) {
    if (refresh) setRefreshing(true);
    try {
      const qs = refresh ? "?location=India&refresh=true" : "?location=India";
      setAnalytics(await api.get(`/jobs/analytics${qs}`));
    } catch (e) {
      /* analytics is best-effort */
    } finally {
      setRefreshing(false);
    }
  }

  async function approve(ids) {
    try {
      const r = await api.post("/apply/approve", ids ? { application_ids: ids } : { all: true });
      toast(r.message, r.live_ready ? "success" : "info");
      loadPending();
      loadStats();
    } catch (e) {
      toast(e.message, "error");
    }
  }

  useEffect(() => {
    loadStats();
    loadPending();
    loadAnalytics();
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
        loadPending();
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
    <div className="space-y-6 animate-fade-up">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink">Dashboard</h1>
          <p className="mt-0.5 text-sm text-ink-soft">Overview of your real job-application activity</p>
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

      {/* Approval gate — auto-apply jobs are NEVER submitted without explicit confirmation. */}
      {pending && pending.items.length > 0 && (
        <div className="card p-5 space-y-3 border-amber-200 bg-amber-50/40">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <h2 className="font-semibold text-amber-700">
                {pending.items.length} application(s) awaiting your approval
              </h2>
              <p className="text-xs text-muted">
                Nothing has been submitted. Review and confirm to apply.
                {" "}Resume: <span className="text-ink">{pending.resume_version}</span>.
                {!pending.live_ready && (
                  <span className="text-amber-600"> · Live mode is OFF — approving will mark these
                    “Manual Apply Required”, not submit them.</span>
                )}
              </p>
            </div>
            {/* Bulk action is DE-EMPHASISED + guarded: it submits every job in the
                list at once, so it must look distinct from the per-job Confirm and
                require an explicit extra confirmation. */}
            <button
              className="btn-ghost whitespace-nowrap border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100"
              onClick={() => {
                const n = pending.items.length;
                if (window.confirm(
                  `Submit ALL ${n} applications at once?\n\nThis applies to every job in the list below — not just one. ` +
                  `To apply to a single job, cancel this and use the “Confirm” button on that specific row instead.`
                )) approve(null);
              }}>
              ⚠ Confirm ALL {pending.items.length} &amp; Submit
            </button>
          </div>
          <div className="divide-y divide-line rounded-btn border border-line">
            {pending.items.map((j) => (
              <div key={j.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                <div className="min-w-0">
                  <div className="truncate">
                    <span className="text-ink">About to apply to:</span> {j.job_title}
                    {" "}<span className="text-muted">at {j.company}</span>
                  </div>
                  <div className="text-xs text-muted">
                    {j.platform} · {j.location || "—"} · {j.match_score}% match · using {pending.resume_version}
                  </div>
                </div>
                {/* Per-job Confirm is now the PRIMARY (prominent) action — it
                    submits only this one row. */}
                <button className="btn-primary whitespace-nowrap" onClick={() => approve([j.id])}>
                  Confirm this job
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <StatCard label="Verified Submitted" value={stats.verified_submitted} accent="text-success" />
        <StatCard label="Submitted" value={stats.submitted} accent="text-blue-600" />
        <StatCard label="Manual Apply" value={stats.manual_apply} accent="text-amber-600" />
        <StatCard label="Tracked" value={stats.tracked} accent="text-blue-600" />
        <StatCard label="Total" value={stats.total} />
      </div>

      {/* Provider / discovery analytics */}
      {analytics && (
        <div className="card p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Job Discovery Analytics</h2>
            <div className="flex items-center gap-3">
              <span className="text-xs text-muted">
                {analytics.live_providers}/{analytics.total_providers} sources live ·
                {" "}last sync {new Date(analytics.last_sync).toLocaleTimeString()}
              </span>
              <button className="btn-ghost text-xs" disabled={refreshing}
                      onClick={() => loadAnalytics(true)}
                      title="Bypass cache, pull the freshest live listings">
                {refreshing ? "Refreshing…" : "↻ Refresh"}
              </button>
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <StatCard label="Jobs discovered" value={analytics.jobs_discovered} />
            <StatCard label="Internships" value={analytics.internships} accent="text-blue-600" />
            <StatCard label="Freshers" value={analytics.freshers} accent="text-blue-600" />
            <StatCard label="AI/ML jobs" value={analytics.ai_ml} accent="text-purple-600" />
            <StatCard label="Coverage" value={`${analytics.coverage_percentage}%`} accent="text-success" />
          </div>
          {analytics.by_source && (
            <div className="flex flex-wrap gap-2 text-xs pt-1">
              {Object.entries(analytics.by_source).sort((a, b) => b[1] - a[1]).map(([s, n]) => (
                <span key={s} className="badge border-line text-muted">{s}: {n}</span>
              ))}
            </div>
          )}
        </div>
      )}

      {(running || log.length > 0) && (
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-3">
            {running && <span className="h-2 w-2 rounded-full bg-success animate-pulse" />}
            <h2 className="font-semibold">Live activity {running ? "(running)" : ""}</h2>
          </div>
          <div className="max-h-60 overflow-y-auto rounded-[12px] bg-slate-50 border border-edge p-3 font-mono text-xs space-y-1">
            {log.map((e, i) => (
              <div key={i} className="text-muted">
                {e.type === "log" ? (
                  <span>
                    <span className="text-ink">[{e.portal}]</span> {e.job_title} @ {e.company} —{" "}
                    <span
                      className={
                        e.status === "Verified Submitted"
                          ? "text-success"
                          : e.status === "Tracked" || e.status === "Submitted" || e.status === "Saved"
                          ? "text-blue-600"
                          : e.status === "Failed"
                          ? "text-danger"
                          : e.status === "Manual Apply"
                          ? "text-amber-600"
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
            No activity yet. Browse <b className="text-ink">Find Jobs</b> or hit{" "}
            <b className="text-ink">Scan &amp; Track Matches</b>.
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
      <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden mb-4">
        <div className="h-full rounded-full bg-brand transition-all duration-700" style={{ width: `${pct}%` }} />
      </div>
      <div className="space-y-2">
        {steps.map((s) => (
          <div key={s.label} className="flex items-center justify-between text-sm">
            <span className={s.done ? "text-muted line-through" : "text-ink"}>
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
                <div className="flex items-center gap-2">
                  <StatusBadge status={r.display_status} />
                  <ApplyModeBadge mode={r.application_mode} />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { JobCardSkeleton, Tooltip, useToast } from "../../components/UI";
import { useAuth } from "../../context/AuthContext";
import AssistedApplyWizard from "../../components/AssistedApplyWizard";
import GreenhouseSubmitWizard from "../../components/GreenhouseSubmitWizard";

// Captcha-gated portals use the Assisted Apply wizard; others use the review modal.
const ASSISTED_PLATFORMS = ["Lever", "Ashby"];

// India-first location list — major hiring hubs for students/freshers.
const LOCATIONS = [
  "", "India", "Remote India", "Chennai", "Bangalore", "Hyderabad", "Pune",
  "Mumbai", "Delhi NCR", "Remote",
];

// Minimum salary buckets (annual INR). Value is what we send as ?min_salary.
const SALARY_BUCKETS = [
  { label: "Any salary", value: 0 },
  { label: "₹3 LPA+", value: 300000 },
  { label: "₹6 LPA+", value: 600000 },
  { label: "₹10 LPA+", value: 1000000 },
  { label: "₹15 LPA+", value: 1500000 },
];

// Internship duration buckets (months). Value is sent as ?duration substring.
const DURATIONS = [
  { label: "Any duration", value: "" },
  { label: "2 months", value: "2" },
  { label: "3 months", value: "3" },
  { label: "6 months", value: "6" },
];

// Tabs map to backend filters. The Remote tab sets a `remote` flag — it must NOT
// overwrite the Location dropdown, so "India + Remote" stays India-first
// (location=India & remote=true) instead of falling back to global remote jobs.
const TABS = [
  { key: "all", label: "All", filter: {} },
  { key: "internship", label: "Internship", filter: { employment_type: "internship" } },
  { key: "fresher", label: "Fresher", filter: { employment_type: "fresher" } },
  { key: "job", label: "Full-time", filter: { employment_type: "job" } },
  { key: "remote", label: "Remote", filter: { remote: true } },
];

// Personalize the default tab from the onboarding seeker type.
const SEEKER_DEFAULT_TAB = { student: "internship", fresher: "fresher", experienced: "job" };

// Sources whose discovery awaits an authorized data source (shown as "Source Pending").
const PENDING_SOURCES = {
  Internshala: "Internshala integration is awaiting an authorized data source.",
  Workable: "Workable discovery needs an authorized account token.",
  Wellfound: "Wellfound discovery is awaiting an authorized data source (no public API).",
  JSearch: "JSearch (Google for Jobs) needs a free RapidAPI key to enable broad India + remote + internship coverage.",
};

export default function FindJobs() {
  const toast = useToast();
  const { user } = useAuth();
  const [q, setQ] = useState("");
  const [location, setLocation] = useState("");
  const [tab, setTab] = useState(SEEKER_DEFAULT_TAB[user?.seeker_type] || "all");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [assistJob, setAssistJob] = useState(null);
  const [ghJob, setGhJob] = useState(null);
  const [showIneligible, setShowIneligible] = useState(false);
  const [company, setCompany] = useState("");
  const [minSalary, setMinSalary] = useState(0);
  const [duration, setDuration] = useState("");

  async function openApply(j) {
    // Assisted (captcha-gated) portals use the wizard.
    if (ASSISTED_PLATFORMS.includes(j.platform)) { setAssistJob(j); return; }
    // Greenhouse → submit wizard (real submission behind a per-application
    // confirmation + truthful required answers; also offers Open & Track).
    if (j.platform === "Greenhouse") { setGhJob(j); return; }
    // Everything else = Track & Apply on Company Site: open the official
    // application page and record a TRACKED event. Nothing is submitted by Jobora.
    window.open(j.apply_url, "_blank", "noopener");
    try {
      await api.post("/jobs/apply", {
        fingerprint: j.fingerprint, source: j.source, title: j.title, company: j.company,
        location: j.location || "", salary: j.salary || "", salary_inr: j.salary_inr || "",
        deadline: j.deadline || "", apply_url: j.apply_url, verified: !!j.verified,
        match_score: j.match_score || 0, platform: j.platform || "",
        manual_required: !!j.manual_required, status: "Tracked",
      });
      markApplied(j.fingerprint);
      toast(`Opened ${j.company}'s application page — tracked in your Activity Log`, "success");
    } catch (e) {
      toast(e.message, "error");
    }
  }
  // null = let the server default it from the profile; then we sync the checkbox.
  const [internshipsOnly, setInternshipsOnly] = useState(null);

  async function load(activeTab = tab, refresh = false, ineligible = showIneligible, io = internshipsOnly) {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: 40 });
      if (q) params.set("q", q);
      const tabFilter = TABS.find((t) => t.key === activeTab)?.filter || {};
      // Location dropdown takes precedence over any tab-provided location, so the
      // user's explicit choice (e.g. India) is never overwritten by a tab.
      const loc = location || tabFilter.location || "";
      if (loc) params.set("location", loc);
      if (tabFilter.employment_type) params.set("employment_type", tabFilter.employment_type);
      // Remote tab adds remote=true alongside (not instead of) the location.
      if (tabFilter.remote) params.set("remote", "true");
      if (ineligible) params.set("include_ineligible", "true");
      if (io !== null && io !== undefined) params.set("internships_only", String(io));
      if (company.trim()) params.set("company", company.trim());
      if (minSalary) params.set("min_salary", String(minSalary));
      if (duration) params.set("duration", duration);
      if (refresh) params.set("refresh", "true");
      const resp = await api.get(`/jobs?${params}`);
      setData(resp);
      setInternshipsOnly((prev) => (prev === null ? !!resp.internships_only : prev));
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(tab);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function selectTab(key) {
    setTab(key);
    load(key);
  }

  function markApplied(fp) {
    setData((d) => ({
      ...d,
      items: d.items.map((x) => (x.fingerprint === fp ? { ...x, applied: true } : x)),
    }));
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Find Jobs</h1>
        <p className="text-sm text-muted">
          Real openings matched to your resume · salary/stipend in INR · track &amp; apply on the company site
        </p>
      </div>

      {/* Tabs / filter chips */}
      <div className="flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => selectTab(t.key)}
            className={`badge px-3 py-1.5 transition-colors ${
              tab === t.key ? "bg-white text-black border-white" : "border-line text-muted hover:text-white"
            }`}
          >
            {t.label}
          </button>
        ))}
        {user?.seeker_type && tab === SEEKER_DEFAULT_TAB[user.seeker_type] && (
          <span className="badge border-blue-400/40 text-blue-300">★ Recommended for you</span>
        )}
      </div>

      <div className="card p-4 flex flex-wrap gap-3 items-end">
        <div className="flex-1 min-w-[200px]">
          <label className="label">Role / keywords</label>
          <input
            className="input"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load()}
            placeholder="e.g. backend engineer, data scientist"
          />
        </div>
        <div>
          <label className="label">Location</label>
          <select className="input w-auto" value={location}
                  onChange={(e) => setLocation(e.target.value)}>
            {LOCATIONS.map((l) => (
              <option key={l} value={l}>{l || "Anywhere"}</option>
            ))}
          </select>
        </div>
        <div className="min-w-[150px]">
          <label className="label">Company</label>
          <input
            className="input"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load()}
            placeholder="e.g. Razorpay, Zoho"
          />
        </div>
        <div>
          <label className="label">Min salary</label>
          <select className="input w-auto" value={minSalary}
                  onChange={(e) => setMinSalary(Number(e.target.value))}>
            {SALARY_BUCKETS.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Internship duration</label>
          <select className="input w-auto" value={duration}
                  onChange={(e) => setDuration(e.target.value)}>
            {DURATIONS.map((d) => (
              <option key={d.value} value={d.value}>{d.label}</option>
            ))}
          </select>
        </div>
        <button className="btn-primary" onClick={() => load()}>Search</button>
        <button className="btn-ghost" onClick={() => load(tab, true)} title="Bypass cache, fetch fresh">↻ Refresh</button>
      </div>

      {/* Internships & New Grad only — hard filter (default ON for students/freshers) */}
      <label className="flex items-center gap-2 text-sm cursor-pointer select-none w-fit">
        <input
          type="checkbox"
          className="accent-white h-4 w-4"
          checked={!!(internshipsOnly ?? data?.internships_only)}
          onChange={() => {
            const v = !(internshipsOnly ?? data?.internships_only);
            setInternshipsOnly(v);
            load(tab, false, showIneligible, v);
          }}
        />
        <span className="text-white">Internships &amp; New Grad only</span>
        <Tooltip text="On by default for students/freshers: shows only roles with an explicit intern / new-grad / fresher / entry-level signal, and hides senior, staff, PhD-only and experienced roles. Turn off to see all eligible roles.">
          <span className="text-muted text-xs cursor-help underline decoration-dotted">what's this?</span>
        </Tooltip>
      </label>

      {/* Sources — Source Pending badge + tooltip for unavailable providers */}
      {data?.sources && (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-muted">Sources:</span>
          {data.sources.map((s) => {
            if (PENDING_SOURCES[s.name] && !s.available) {
              return (
                <Tooltip key={s.name} text={PENDING_SOURCES[s.name]}>
                  <span className="badge border-yellow-500/40 text-yellow-400 cursor-help">
                    ⏳ {s.name} · Source Pending
                  </span>
                </Tooltip>
              );
            }
            return (
              <span key={s.name}
                    className={`badge ${s.available ? "border-success/40 text-success" : "border-line text-muted"}`}>
                {s.available ? "●" : "○"} {s.name}
              </span>
            );
          })}
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <JobCardSkeleton key={i} />)}
        </div>
      ) : !data || data.items.length === 0 ? (
        <EmptyState tab={tab} q={q} data={data}
                    internshipsOnly={!!(internshipsOnly ?? data?.internships_only)}
                    onShowAllInternshipsOff={() => { setInternshipsOnly(false); load(tab, false, showIneligible, false); }}
                    onShowIneligible={() => { setShowIneligible(true); load(tab, false, true); }}
                    onSwitch={selectTab}
                    onBroaden={() => { setQ(""); setTab("all"); load("all"); }} />
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="text-sm text-muted">
              {data.total} {data.internships_only ? "internship & new-grad roles" : "eligible positions"}, best fit first
              {data.internships_only && data.filtered_generic > 0 && (
                <span className="text-muted/70"> · {data.filtered_generic} generic/senior roles filtered</span>
              )}
            </div>
            {data.hidden_ineligible > 0 && (
              <button
                className="text-xs text-muted hover:text-white underline underline-offset-2"
                onClick={() => { const v = !showIneligible; setShowIneligible(v); load(tab, false, v); }}
              >
                {showIneligible
                  ? "Hide roles above your level"
                  : `${data.hidden_ineligible} senior/PhD/visa-restricted roles hidden — show anyway`}
              </button>
            )}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {data.items.map((j) => (
              <JobCard key={j.fingerprint} job={j} onApply={() => openApply(j)} />
            ))}
          </div>
        </>
      )}

      <AssistedApplyWizard
        job={assistJob}
        onClose={() => setAssistJob(null)}
        onDone={() => {
          if (assistJob) markApplied(assistJob.fingerprint);
          setAssistJob(null);
        }}
      />

      <GreenhouseSubmitWizard
        job={ghJob}
        onClose={() => setGhJob(null)}
        onTracked={() => ghJob && markApplied(ghJob.fingerprint)}
        onSubmitted={() => ghJob && markApplied(ghJob.fingerprint)}
      />
    </div>
  );
}

function EmptyState({ tab, q, data, internshipsOnly, onShowAllInternshipsOff, onShowIneligible, onSwitch, onBroaden }) {
  const filteredGeneric = data?.filtered_generic || 0;
  const hiddenIneligible = data?.hidden_ineligible || 0;
  const hiddenByInternship = internshipsOnly && filteredGeneric > 0;
  const hiddenBySenior = hiddenIneligible > 0;

  return (
    <div className="card p-10 text-center space-y-4">
      <div className="text-5xl">🔍</div>
      <div className="space-y-1">
        <div className="font-semibold text-lg">No roles to show{q ? ` for "${q}"` : ""}</div>

        {/* Explain WHY, using the real filter counts */}
        {hiddenByInternship ? (
          <p className="text-sm text-muted max-w-md mx-auto">
            The <b className="text-white">Internships &amp; New Grad only</b> filter is on, and{" "}
            <b className="text-white">{filteredGeneric}</b> eligible role{filteredGeneric === 1 ? "" : "s"}{" "}
            didn't carry an explicit intern/new-grad signal
            {hiddenBySenior && <> (plus {hiddenIneligible} senior/PhD roles hidden)</>}.
            Internship postings on these sources are bursty — try turning the filter off.
          </p>
        ) : hiddenBySenior ? (
          <p className="text-sm text-muted max-w-md mx-auto">
            We hid <b className="text-white">{hiddenIneligible}</b> role{hiddenIneligible === 1 ? "" : "s"}{" "}
            that are above an early-career level (senior / staff / PhD / 3+ yrs). Show them, broaden the
            role, or try a different keyword.
          </p>
        ) : (
          <p className="text-sm text-muted max-w-md mx-auto">
            Try a broader role or keyword, a different location, or refresh for the latest listings.
          </p>
        )}
      </div>

      {/* Targeted actions */}
      <div className="flex flex-wrap gap-2 justify-center pt-2">
        {hiddenByInternship && (
          <button className="btn-primary" onClick={onShowAllInternshipsOff}>Show all eligible roles</button>
        )}
        {!hiddenByInternship && hiddenBySenior && (
          <button className="btn-primary" onClick={onShowIneligible}>Show hidden roles</button>
        )}
        <button className={hiddenByInternship || hiddenBySenior ? "btn-ghost" : "btn-primary"} onClick={onBroaden}>
          Browse all roles
        </button>
        {tab !== "remote" && <button className="btn-ghost" onClick={() => onSwitch("remote")}>Remote roles</button>}
      </div>

      <p className="text-xs text-muted pt-1">
        Tip: the <b className="text-white">Internships &amp; New Grad only</b> toggle above the results
        controls how strict the filter is.
      </p>
    </div>
  );
}

function ScoreRing({ score }) {
  const color = score >= 70 ? "text-success" : score >= 45 ? "text-yellow-400" : "text-muted";
  return (
    <div className={`shrink-0 text-center ${color}`}>
      <div className="text-2xl font-bold leading-none">{score}</div>
      <div className="text-[10px] uppercase tracking-wide text-muted">match</div>
    </div>
  );
}

const TYPE_LABEL = { internship: "Internship", fresher: "Fresher", job: "Full-time" };
const ELIG_STYLE = {
  "Excellent Match": "border-success/60 text-success",
  "Good Match": "border-success/40 text-success",
  "Possible Match": "border-yellow-500/40 text-yellow-400",
  "Not Recommended": "border-danger/40 text-danger",
};

const SIGNAL_STYLE = {
  Internship: "border-blue-400/50 text-blue-300",
  "New Grad": "border-purple-400/50 text-purple-300",
  "Fresher Friendly": "border-teal-400/50 text-teal-300",
};

function EligibilityBadge({ job }) {
  if (!job.eligibility_tier) return null;
  return (
    <span className={`badge ${ELIG_STYLE[job.eligibility_tier] || "border-line text-muted"}`}>
      {job.eligibility_tier === "Excellent Match" ? "★ " : ""}{job.eligibility_tier}
      {job.eligibility_score ? ` · ${job.eligibility_score}` : ""}
    </span>
  );
}

function SignalBadge({ job }) {
  if (!job.early_signal) return null;
  return (
    <span className={`badge ${SIGNAL_STYLE[job.early_signal] || "border-line text-muted"}`}>
      {job.early_signal}
    </span>
  );
}

function JobCard({ job, onApply }) {
  return (
    <div className="card-elevated p-5 flex flex-col">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold leading-snug">{job.title}</h3>
          <div className="text-sm text-muted mt-0.5">{job.company}</div>
        </div>
        <ScoreRing score={job.match_score} />
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        <EligibilityBadge job={job} />
        <SignalBadge job={job} />
        {job.employment_type && TYPE_LABEL[job.employment_type] && (
          <span className="badge border-blue-400/40 text-blue-300">{TYPE_LABEL[job.employment_type]}</span>
        )}
        {job.location && <Meta icon="📍" text={job.location} />}
        {job.salary_inr && <Meta icon="💰" text={job.salary_inr} />}
        {job.duration && <Meta icon="🕑" text={job.duration} />}
        {job.deadline && <Meta icon="⏳" text={`Closes ${job.deadline}`} />}
        {job.posted_at && <Meta icon="📅" text={job.posted_at} />}
        <Meta icon="🔗" text={job.source} />
      </div>

      {/* Why matched? — eligibility reasons first, then skill/role match reasons */}
      <div className="mt-3 rounded-btn bg-input/40 border border-line p-2.5">
        <div className="text-[11px] uppercase tracking-wide text-muted mb-1">Why matched?</div>
        <ul className="space-y-0.5 text-xs">
          {(job.eligibility_reasons?.length ? job.eligibility_reasons : [job.eligibility_reason])
            .filter(Boolean)
            .map((r, i) => (
              <li key={`e${i}`} className="text-muted">• {r}</li>
            ))}
          {job.match_reasons?.slice(0, 2).map((r, i) => (
            <li key={`m${i}`} className="text-muted">• {r}</li>
          ))}
        </ul>
      </div>

      <div className="mt-auto pt-4 flex items-center gap-2 border-t border-line mt-4">
        {job.verified && <span className="badge border-line text-muted">✓ Verified listing</span>}
        {ASSISTED_PLATFORMS.includes(job.platform) ? (
          <span className="badge border-blue-400/40 text-blue-300">Assisted Apply</span>
        ) : (
          <span className="badge border-line text-muted">Apply on company site</span>
        )}
        <div className="ml-auto">
          {job.applied ? (
            <span className="badge border-success/40 text-success">✓ Tracked</span>
          ) : (
            <button className="btn-primary" onClick={onApply}>
              {ASSISTED_PLATFORMS.includes(job.platform) ? "Assisted Apply" : "Track & Apply"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function Meta({ icon, text }) {
  return (
    <span className="pill !py-0.5 !text-xs">
      <span>{icon}</span>
      {text}
    </span>
  );
}

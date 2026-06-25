import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { Spinner, StatusBadge, useToast } from "../../components/UI";

// Matched Jobs — the Find & Link pipeline. Shows the manual-link results produced
// by a "Start Applying" run (no-API portals like Naukri/Unstop/Internshala +
// aggregator listings that link out), sorted by match score. Each opens the
// original apply URL / portal search in a new tab. We never auto-submit or scrape.
export default function MatchedJobs() {
  const toast = useToast();
  const [items, setItems] = useState(null);
  const [opened, setOpened] = useState({});
  const [ishLink, setIshLink] = useState(null);

  async function load() {
    setItems(null);
    try {
      const resp = await api.get(
        "/applications?mode=manual_link_provided&sort=match_score&page_size=100");
      setItems(resp.items || []);
    } catch (e) {
      toast(e.message, "error");
      setItems([]);
    }
  }

  // "Search on Internshala" deep-link built from the user's primary role filter —
  // a constructed search URL (never a fetched/scraped listing), always available.
  async function loadIshLink() {
    try {
      const f = await api.get("/filters");
      const role = (f.roles && f.roles[0]) || "";
      const qs = new URLSearchParams({ q: role, location: "India", employment_type: "internship" });
      setIshLink(await api.get(`/jobs/internshala-link?${qs}`));
    } catch (e) { /* best-effort */ }
  }

  useEffect(() => { load(); loadIshLink(); /* eslint-disable-next-line */ }, []);

  function openJob(j) {
    window.open(j.apply_url, "_blank", "noopener");      // already a tracked application
    setOpened((o) => ({ ...o, [j.id]: true }));
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink">Matched Jobs</h1>
          <p className="text-sm text-muted">
            Find &amp; Link results from your last Start-Applying run — open the listing/portal to apply.
          </p>
        </div>
        <button className="btn-ghost" onClick={load}>↻ Refresh</button>
      </div>

      {/* Always-available Internshala search deep-link (constructed URL, not a
          scraped listing) — browse and apply on Internshala yourself. */}
      {ishLink?.search_url && (
        <div className="card p-3 flex items-center justify-between gap-3 border-blue-400/30">
          <div className="text-sm">
            <span className="font-medium text-blue-600">Search on Internshala</span>
            <span className="text-muted">{" — "}{ishLink.note}</span>
          </div>
          <a href={ishLink.search_url} target="_blank" rel="noopener noreferrer"
             className="btn-ghost whitespace-nowrap text-blue-600 border-blue-400/40">
            Search on Internshala ↗
          </a>
        </div>
      )}

      {items === null ? (
        <Spinner />
      ) : items.length === 0 ? (
        <div className="card p-8 text-center text-sm text-muted">
          No matched manual-apply jobs yet. Click <b className="text-ink">Start Applying</b> on the
          Dashboard — one run auto-applies where possible and adds manual sources
          (Naukri, Unstop, Internshala, Indeed, LinkedIn, Foundit, Shine, Apna…) here with apply links.
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {items.map((j) => (
            <div key={j.id} className="card p-5 flex flex-col gap-2">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-semibold">{j.job_title}</div>
                  <div className="text-sm text-muted">{j.company}{j.location ? ` · ${j.location}` : ""}</div>
                </div>
                <div className="text-right">
                  <div className="text-lg font-bold text-success">{j.match_score || 0}%</div>
                  <div className="text-xs text-muted">match</div>
                </div>
              </div>
              <div className="flex items-center gap-2 flex-wrap text-xs">
                <span className="badge border-blue-400/50 text-blue-600">Apply Manually</span>
                <span className="badge border-indigo-400/40 text-indigo-600">{applyHost(j)}</span>
                <StatusBadge status={j.display_status} />
              </div>
              <div className="mt-auto pt-2">
                {opened[j.id] ? (
                  <span className="badge border-success/40 text-success">✓ Opened</span>
                ) : (
                  <button className="btn-primary w-full" onClick={() => openJob(j)}>Open Job ↗</button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function applyHost(j) {
  const u = (j.apply_url || "").toLowerCase();
  if (u.includes("naukri")) return "Apply on Naukri";
  if (u.includes("unstop")) return "Apply on Unstop";
  if (u.includes("internshala")) return "Apply on Internshala";
  if (u.includes("indeed")) return "Apply on Indeed";
  if (u.includes("linkedin")) return "Apply on LinkedIn";
  if (u.includes("foundit") || u.includes("monster")) return "Apply on Foundit";
  if (u.includes("shine")) return "Apply on Shine";
  if (u.includes("apna")) return "Apply on Apna";
  return "Apply on Company Site";
}

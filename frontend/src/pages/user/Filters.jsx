import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { Spinner, PillInput, useToast } from "../../components/UI";

const LOCATIONS = ["India", "Dubai", "Singapore"];
const JOB_TYPES = ["Full-time", "Internships", "Part-time", "Remote", "Contract"];

export default function Filters() {
  const toast = useToast();
  const [f, setF] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/filters").then(setF);
  }, []);

  function set(k, v) {
    setF((s) => ({ ...s, [k]: v }));
  }
  function toggleIn(key, value) {
    setF((s) => {
      const arr = s[key] || [];
      return { ...s, [key]: arr.includes(value) ? arr.filter((x) => x !== value) : [...arr, value] };
    });
  }

  async function save() {
    setSaving(true);
    try {
      await api.post("/filters", {
        roles: f.roles,
        locations: f.locations,
        job_types: f.job_types,
        keywords: f.keywords,
        daily_limit: Number(f.daily_limit),
        min_match_score: Number(f.min_match_score ?? 50),
      });
      toast("Filters saved", "success");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setSaving(false);
    }
  }

  if (!f) return <Spinner />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Filters</h1>
        <p className="text-sm text-muted">Tell Jobora exactly which jobs to target</p>
      </div>

      <div className="card p-6 space-y-5">
        <div>
          <label className="label">Job titles / roles</label>
          <PillInput values={f.roles} onChange={(v) => set("roles", v)} placeholder="e.g. Software Engineer" />
        </div>

        <div>
          <label className="label">Target keywords</label>
          <PillInput values={f.keywords} onChange={(v) => set("keywords", v)} placeholder="e.g. python, react" />
        </div>

        <div>
          <label className="label">Locations</label>
          <div className="flex flex-wrap gap-2">
            {LOCATIONS.map((loc) => (
              <button
                key={loc}
                type="button"
                onClick={() => toggleIn("locations", loc)}
                className={`badge px-3 py-1.5 ${
                  f.locations.includes(loc) ? "bg-white text-black border-white" : "border-line text-muted"
                }`}
              >
                {loc}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="label">Job type</label>
          <div className="flex flex-wrap gap-2">
            {JOB_TYPES.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => toggleIn("job_types", t)}
                className={`badge px-3 py-1.5 ${
                  f.job_types.includes(t) ? "bg-white text-black border-white" : "border-line text-muted"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="label">
            Daily application limit — <span className="text-white">{f.daily_limit}/day</span>
          </label>
          <input
            type="range"
            min="5"
            max="100"
            step="1"
            value={f.daily_limit}
            onChange={(e) => set("daily_limit", e.target.value)}
            className="w-full accent-white"
          />
          <div className="flex justify-between text-xs text-muted mt-1">
            <span>5</span>
            <span>100</span>
          </div>
        </div>

        <div>
          <label className="label">
            Minimum resume match score — <span className="text-white">{f.min_match_score ?? 50}%</span>
          </label>
          <input
            type="range"
            min="0"
            max="100"
            step="5"
            value={f.min_match_score ?? 50}
            onChange={(e) => set("min_match_score", e.target.value)}
            className="w-full accent-white"
          />
          <div className="flex justify-between text-xs text-muted mt-1">
            <span>0% (show all)</span>
            <span>100% (exact)</span>
          </div>
          <p className="text-xs text-muted mt-1">
            Jobs scoring below this against your resume are hidden in Find Jobs &amp; Matched Jobs.
          </p>
        </div>

        <div className="pt-2">
          <button className="btn-primary" disabled={saving} onClick={save}>
            {saving ? "Saving…" : "Save filters"}
          </button>
        </div>
      </div>
    </div>
  );
}

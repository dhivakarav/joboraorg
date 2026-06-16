import { useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import { Spinner, PillInput, useToast } from "../../components/UI";

export default function Resume() {
  const toast = useToast();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const fileRef = useRef(null);

  async function load() {
    try {
      setData(await api.get("/resume/parsed"));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function onFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      toast("Resume exceeds 5MB limit", "error");
      return;
    }
    setUploading(true);
    try {
      const parsed = await api.upload("/resume/upload", file);
      setData(parsed);
      toast("Resume uploaded & parsed", "success");
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  function set(k, v) {
    setData((d) => ({ ...d, [k]: v }));
  }

  async function save() {
    setSaving(true);
    try {
      await api.put("/resume/parsed", {
        parsed_name: data.parsed_name,
        parsed_email: data.parsed_email,
        parsed_phone: data.parsed_phone,
        parsed_location: data.parsed_location,
        parsed_skills: data.parsed_skills,
        parsed_experience: Number(data.parsed_experience) || 0,
        linkedin_url: data.linkedin_url,
        portfolio_url: data.portfolio_url,
      });
      toast("Saved", "success");
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <Spinner />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Resume</h1>
        <p className="text-sm text-muted">Upload your PDF resume — we extract your details automatically</p>
      </div>

      <div className="card-elevated p-6">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <div className="font-medium">{data.has_resume ? "Resume uploaded" : "No resume yet"}</div>
            <div className="text-sm text-muted">PDF only · max 5MB</div>
          </div>
          <button className="btn-primary" disabled={uploading} onClick={() => fileRef.current?.click()}>
            {uploading ? "Parsing…" : data.has_resume ? "Replace resume" : "Upload resume"}
          </button>
          <input ref={fileRef} type="file" accept="application/pdf" hidden onChange={onFile} />
        </div>
      </div>

      {data.has_resume && (
        <div className="card p-6 space-y-4">
          <h2 className="font-semibold">Parsed details (quick-edit)</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Name</label>
              <input className="input" value={data.parsed_name || ""} onChange={(e) => set("parsed_name", e.target.value)} />
            </div>
            <div>
              <label className="label">Email</label>
              <input className="input" value={data.parsed_email || ""} onChange={(e) => set("parsed_email", e.target.value)} />
            </div>
            <div>
              <label className="label">Phone</label>
              <input className="input" value={data.parsed_phone || ""} onChange={(e) => set("parsed_phone", e.target.value)} />
            </div>
            <div>
              <label className="label">Location</label>
              <input className="input" value={data.parsed_location || ""} onChange={(e) => set("parsed_location", e.target.value)} />
            </div>
            <div>
              <label className="label">Years of experience</label>
              <input className="input" type="number" min="0" value={data.parsed_experience || 0} onChange={(e) => set("parsed_experience", e.target.value)} />
            </div>
            <div>
              <label className="label">LinkedIn URL</label>
              <input className="input" value={data.linkedin_url || ""} onChange={(e) => set("linkedin_url", e.target.value)} placeholder="https://linkedin.com/in/…" />
            </div>
            <div>
              <label className="label">Portfolio URL</label>
              <input className="input" value={data.portfolio_url || ""} onChange={(e) => set("portfolio_url", e.target.value)} placeholder="https://…" />
            </div>
          </div>
          <div>
            <label className="label">Skills</label>
            <PillInput
              values={data.parsed_skills || []}
              onChange={(v) => set("parsed_skills", v)}
              placeholder="Add a skill and press Enter"
            />
          </div>
          {data.parsed_education?.length > 0 && (
            <div>
              <label className="label">Education (parsed)</label>
              <div className="space-y-1">
                {data.parsed_education.map((ed, i) => (
                  <div key={i} className="pill !rounded-btn w-full justify-start">
                    {ed.detail}{ed.year ? ` · ${ed.year}` : ""}
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="pt-2">
            <button className="btn-primary" disabled={saving} onClick={save}>
              {saving ? "Saving…" : "Save changes"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

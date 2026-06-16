import { useState } from "react";
import { api } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../components/UI";

export default function Settings() {
  const { user, refresh } = useAuth();
  const toast = useToast();
  const [profile, setProfile] = useState({
    full_name: user.full_name,
    phone: user.phone,
    years_experience: user.years_experience,
    job_title: user.job_title,
  });
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const [savingP, setSavingP] = useState(false);
  const [savingPw, setSavingPw] = useState(false);
  const [savingSeeker, setSavingSeeker] = useState(false);

  async function saveSeeker(type) {
    setSavingSeeker(true);
    try {
      await api.put("/profile/update", { seeker_type: type });
      await refresh();
      toast("Job preferences updated", "success");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setSavingSeeker(false);
    }
  }

  async function saveProfile() {
    setSavingP(true);
    try {
      await api.put("/profile/update", {
        ...profile,
        years_experience: Number(profile.years_experience) || 0,
      });
      await refresh();
      toast("Profile updated", "success");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setSavingP(false);
    }
  }

  async function changePassword() {
    setSavingPw(true);
    try {
      await api.put("/profile/password", pw);
      setPw({ current_password: "", new_password: "" });
      toast("Password changed", "success");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setSavingPw(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-sm text-muted">Manage your profile and password</p>
      </div>

      <div className="card p-6 space-y-4">
        <h2 className="font-semibold">Job preferences</h2>
        <p className="text-sm text-muted">
          Sets which jobs we show first. {user.seeker_type
            ? <>Current: <span className="text-white capitalize">{user.seeker_type}</span>.</>
            : "Not set yet."}
        </p>
        <div className="flex flex-wrap gap-2">
          {[
            { key: "student", emoji: "🎓", label: "Student", hint: "Internships first" },
            { key: "fresher", emoji: "🌱", label: "Fresher", hint: "Entry-level jobs first" },
            { key: "experienced", emoji: "💼", label: "Experienced", hint: "Full-time jobs first" },
          ].map((o) => (
            <button
              key={o.key}
              disabled={savingSeeker}
              onClick={() => saveSeeker(o.key)}
              className={`card-elevated px-4 py-3 text-left transition-colors disabled:opacity-50 ${
                user.seeker_type === o.key ? "border-white" : "hover:border-white/40"
              }`}
            >
              <div className="font-medium">{o.emoji} {o.label}</div>
              <div className="text-xs text-muted">{o.hint}</div>
            </button>
          ))}
        </div>
      </div>

      <div className="card p-6 space-y-4">
        <h2 className="font-semibold">Profile</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="label">Full name</label>
            <input className="input" value={profile.full_name} onChange={(e) => setProfile({ ...profile, full_name: e.target.value })} />
          </div>
          <div>
            <label className="label">Email (read-only)</label>
            <input className="input opacity-60" value={user.email} disabled />
          </div>
          <div>
            <label className="label">Phone</label>
            <input className="input" value={profile.phone} onChange={(e) => setProfile({ ...profile, phone: e.target.value })} />
          </div>
          <div>
            <label className="label">Years of experience</label>
            <input className="input" type="number" min="0" value={profile.years_experience} onChange={(e) => setProfile({ ...profile, years_experience: e.target.value })} />
          </div>
          <div className="md:col-span-2">
            <label className="label">Job title</label>
            <input className="input" value={profile.job_title} onChange={(e) => setProfile({ ...profile, job_title: e.target.value })} />
          </div>
        </div>
        <button className="btn-primary" disabled={savingP} onClick={saveProfile}>
          {savingP ? "Saving…" : "Save profile"}
        </button>
      </div>

      <div className="card p-6 space-y-4">
        <h2 className="font-semibold">Change password</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="label">Current password</label>
            <input className="input" type="password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} />
          </div>
          <div>
            <label className="label">New password</label>
            <input className="input" type="password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} />
          </div>
        </div>
        <button className="btn-primary" disabled={savingPw} onClick={changePassword}>
          {savingPw ? "Updating…" : "Update password"}
        </button>
      </div>
    </div>
  );
}

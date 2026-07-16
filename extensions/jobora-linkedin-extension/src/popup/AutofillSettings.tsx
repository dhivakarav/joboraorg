/**
 * Popup section to edit the autofill profile — the answers ATS forms ask for
 * that can't be derived from the Jobora account (city, notice period, work
 * authorization, …). Contact info + skills are auto-seeded from the account.
 */
import { useEffect, useState } from 'react';
import { getProfile, setProfile, EMPTY_PROFILE, type AutofillProfile } from '../autofill/profile';

export default function AutofillSettings() {
  const [p, setP] = useState<AutofillProfile>(EMPTY_PROFILE);
  const [saved, setSaved] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => { getProfile().then(v => { setP(v); setLoaded(true); }); }, []);

  function set<K extends keyof AutofillProfile>(k: K, v: AutofillProfile[K]) {
    setP(prev => ({ ...prev, [k]: v }));
  }
  async function save() {
    await setProfile(p);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  if (!loaded) return null;

  const text = (label: string, k: keyof AutofillProfile, placeholder = '') => (
    <div>
      <label className="jbr-label">{label}</label>
      <input
        className="jbr-input text-xs"
        value={String(p[k] ?? '')}
        placeholder={placeholder}
        onChange={e => set(k, e.target.value as AutofillProfile[typeof k])}
      />
    </div>
  );

  const toggle = (label: string, k: keyof AutofillProfile) => (
    <label className="flex items-center justify-between text-xs text-ink-soft py-0.5">
      <span>{label}</span>
      <input
        type="checkbox"
        checked={Boolean(p[k])}
        onChange={e => set(k, e.target.checked as AutofillProfile[typeof k])}
      />
    </label>
  );

  return (
    <details className="text-xs">
      <summary className="cursor-pointer text-ink-soft hover:text-ink select-none">
        ⚡ Autofill profile
      </summary>
      <div className="mt-2 space-y-2">
        <p className="text-[10px] text-ink-soft leading-snug">
          Name, email, phone & skills are auto-filled from your Jobora account.
          Set the rest below — used to answer application forms automatically.
        </p>
        <div className="grid grid-cols-2 gap-2">
          {text('City', 'city', 'Chennai')}
          {text('Country', 'country', 'India')}
          {text('Postal code', 'postalCode', '600001')}
          {text('Years exp.', 'yearsExperience', '1')}
          {text('Expected CTC (LPA)', 'expectedCtc', '6')}
          {text('Notice (days)', 'noticePeriodDays', '0')}
        </div>
        {text('LinkedIn URL', 'linkedinUrl', 'https://linkedin.com/in/…')}

        <div className="border-t border-edge pt-1.5 mt-1.5">
          {toggle('Available immediately', 'availableImmediately')}
          {toggle("Completed Bachelor's", 'hasBachelors')}
          {toggle('Willing to relocate', 'willingToRelocate')}
          {toggle('Authorized to work', 'workAuthorized')}
          {toggle('Requires visa sponsorship', 'requiresSponsorship')}
        </div>

        <div>
          <label className="jbr-label">Default answer to unknown Yes/No</label>
          <select
            className="jbr-input text-xs"
            value={p.defaultYesNo}
            onChange={e => set('defaultYesNo', e.target.value as 'Yes' | 'No')}
          >
            <option value="Yes">Yes</option>
            <option value="No">No</option>
          </select>
        </div>

        <button onClick={save} className="jbr-btn-ghost text-xs w-full">
          {saved ? '✓ Saved' : 'Save autofill profile'}
        </button>
      </div>
    </details>
  );
}

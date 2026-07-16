/**
 * Prominent Auto-apply switch at the top of the popup. When ON, the ⚡ button
 * on job pages turns red and auto-submits high-match jobs. Deliberately big and
 * obvious (the old toggle was buried in the autofill settings).
 */
import { useEffect, useState } from 'react';
import { getProfile, patchProfile, BYPASS_PASSWORD } from '../autofill/profile';

export default function AutoApplyToggle() {
  const [on, setOn] = useState(false);
  const [minMatch, setMinMatch] = useState(55);
  const [query, setQuery] = useState('');
  const [loc, setLoc] = useState('');
  const [loaded, setLoaded] = useState(false);

  // Password-gated low-match bypass.
  const [bypass, setBypass] = useState(false);
  const [pwOpen, setPwOpen] = useState(false);
  const [pw, setPw] = useState('');
  const [pwErr, setPwErr] = useState(false);

  useEffect(() => {
    getProfile().then(p => {
      setOn(p.autoSubmit); setMinMatch(p.autoSubmitMinMatch);
      setQuery(p.searchQuery || ''); setLoc(p.searchLocation || '');
      setBypass(p.matchBypass);
      setLoaded(true);
    });
  }, []);

  async function toggle() {
    const next = !on;
    setOn(next);
    await patchProfile({ autoSubmit: next });
  }
  async function saveMin(v: number) {
    setMinMatch(v);
    await patchProfile({ autoSubmitMinMatch: v });
  }
  async function tryUnlock() {
    if (pw === BYPASS_PASSWORD) {
      setBypass(true); setPwOpen(false); setPw(''); setPwErr(false);
      await patchProfile({ matchBypass: true });
    } else {
      setPwErr(true);
    }
  }
  async function relock() {
    setBypass(false);
    await patchProfile({ matchBypass: false });
  }

  if (!loaded) return null;

  return (
    <div className={`jbr-card px-3 py-2.5 ${on ? 'border-err/40 bg-err/5' : 'border-edge'}`}>
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="text-xs font-semibold text-ink">⚡ Auto-apply</div>
          <div className="text-[10px] text-ink-soft leading-snug">
            {on ? 'ON — the ⚡ button submits high-match jobs' : 'OFF — the ⚡ button only fills'}
          </div>
        </div>
        {/* Switch */}
        <button
          onClick={toggle}
          role="switch"
          aria-checked={on}
          className={`relative shrink-0 h-6 w-11 rounded-full transition-colors
            ${on ? 'bg-err' : 'bg-edge'}`}
        >
          <span
            className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all
              ${on ? 'left-[22px]' : 'left-0.5'}`}
          />
        </button>
      </div>

      {on && (
        <div className="mt-2 space-y-1.5">
          <div className="flex items-center gap-2">
            <label className="text-[11px] text-ink-soft flex-1">Only auto-submit if match ≥</label>
            <input
              type="number"
              className="jbr-input text-xs w-16 py-1"
              value={String(minMatch)}
              onChange={e => saveMin(Number(e.target.value))}
            />
            <span className="text-[11px] text-ink-soft">%</span>
          </div>
          <div className="border-t border-edge pt-1.5 space-y-1.5">
            <label className="jbr-label">Saved search — for “Start auto-apply”</label>
            <input
              className="jbr-input text-xs"
              placeholder="Role, e.g. Machine Learning Engineer"
              value={query}
              onChange={e => { setQuery(e.target.value); void patchProfile({ searchQuery: e.target.value }); }}
            />
            <input
              className="jbr-input text-xs"
              placeholder="Location, e.g. India (optional)"
              value={loc}
              onChange={e => { setLoc(e.target.value); void patchProfile({ searchLocation: e.target.value }); }}
            />
          </div>
          {/* ── Low-match bypass (password-gated) ─────────────────────── */}
          <div className="border-t border-edge pt-1.5">
            {bypass ? (
              <div className="flex items-center justify-between gap-2 rounded bg-err/10 px-2 py-1.5">
                <span className="text-[11px] font-semibold text-err">🔓 Match filter bypassed — applies to ALL scores</span>
                <button onClick={relock} className="text-[10px] underline text-ink-soft shrink-0">Lock</button>
              </div>
            ) : !pwOpen ? (
              <button
                onClick={() => { setPwOpen(true); setPwErr(false); }}
                className="w-full text-[11px] text-ink-soft underline text-left"
              >
                🔒 Bypass match filter (password)…
              </button>
            ) : (
              <div className="space-y-1">
                <label className="jbr-label">Enter bypass password</label>
                <div className="flex gap-1">
                  <input
                    type="password"
                    autoFocus
                    className={`jbr-input text-xs flex-1 ${pwErr ? 'border-err' : ''}`}
                    value={pw}
                    onChange={e => { setPw(e.target.value); setPwErr(false); }}
                    onKeyDown={e => { if (e.key === 'Enter') void tryUnlock(); }}
                    placeholder="••••••••"
                  />
                  <button onClick={() => void tryUnlock()} className="jbr-btn-primary text-xs px-2">Unlock</button>
                </div>
                {pwErr && <div className="text-[10px] text-err">Wrong password.</div>}
                <div className="text-[10px] text-warn leading-snug">
                  Bypass applies to LOW-match jobs too — more applications, more
                  ban risk, lower relevance. It never fabricates answers; it still
                  pauses on questions it can't answer truthfully.
                </div>
              </div>
            )}
          </div>

          <div className="text-[10px] text-err leading-snug">
            ⚠ Auto-submitting sends real applications and can get your account
            restricted. Throttled by the daily ban meter. Use carefully.
          </div>
        </div>
      )}
    </div>
  );
}

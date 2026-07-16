import { useEffect, useState } from 'react';
import { startBulk, stopBulk, getBulkState, type BulkState } from '../../autofill/bulk';
import { getProfile, patchProfile, BYPASS_PASSWORD } from '../../autofill/profile';

/**
 * Self-contained sidebar control for the bulk auto-apply engine.
 * Everything needed to run lives here — enable, the password-gated low-match
 * bypass, and Start/Stop — so the user never has to dig through the popup.
 * Start runs on whatever results list is open (or the saved search if set).
 */
export default function BulkApplyPanel() {
  const [state, setState] = useState<BulkState | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [query, setQuery] = useState('');
  const [bypass, setBypass] = useState(false);

  // Bypass unlock UI
  const [pwOpen, setPwOpen] = useState(false);
  const [pw, setPw] = useState('');
  const [pwErr, setPwErr] = useState(false);

  useEffect(() => {
    const load = () => getBulkState().then(setState);
    load();
    const loadProfile = () => getProfile().then(p => {
      setEnabled(p.autoSubmit); setQuery(p.searchQuery || ''); setBypass(p.matchBypass);
    });
    loadProfile();
    const onChange = (c: Record<string, chrome.storage.StorageChange>) => {
      if (c.jobora_bulk_run) load();
      if (c.jobora_autofill_profile) loadProfile();
    };
    chrome.storage.onChanged.addListener(onChange);
    return () => chrome.storage.onChanged.removeListener(onChange);
  }, []);

  async function toggleEnabled() {
    const next = !enabled;
    setEnabled(next);
    await patchProfile({ autoSubmit: next });
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

  if (!state) return null;

  return (
    <div className="jbr-card p-3 space-y-2.5">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-ink-soft uppercase tracking-wide">
          Bulk auto-apply
        </span>
        {bypass && <span className="text-[10px] font-semibold text-err">🔓 bypass</span>}
        {state.active && <span className="text-[10px] text-brand animate-pulse">running…</span>}
      </div>

      {/* 1 — Enable auto-apply */}
      <label className="flex items-center gap-2 cursor-pointer">
        <input type="checkbox" checked={enabled} onChange={() => void toggleEnabled()} className="accent-err h-4 w-4" />
        <span className="text-[11px] text-ink font-medium">Auto-apply — submit real applications</span>
      </label>

      {/* 2 — Low-match bypass (password-gated) */}
      {bypass ? (
        <div className="flex items-center justify-between gap-2 rounded bg-err/10 px-2 py-1.5">
          <span className="text-[10px] font-semibold text-err">🔓 Match filter OFF — applies to ALL scores</span>
          <button onClick={() => void relock()} className="text-[10px] underline text-ink-soft shrink-0">Lock</button>
        </div>
      ) : !pwOpen ? (
        <button
          onClick={() => { setPwOpen(true); setPwErr(false); }}
          className="w-full text-[11px] text-ink-soft underline text-left"
        >
          🔒 Bypass match filter — apply to low-match jobs (password)
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
            Bypass applies to LOW-match jobs too — more applications, more ban
            risk. It never fabricates answers; it still pauses on questions it
            can't answer truthfully.
          </div>
        </div>
      )}

      {/* 3 — Start / Stop */}
      {state.active ? (
        <>
          <div className="text-xs text-ink">
            ✓ {state.applied} applied · {state.skipped} skipped · limit {state.target}/day
          </div>
          {state.current && <div className="text-[11px] text-ink-soft truncate">{state.current}</div>}
          <button onClick={() => void stopBulk()} className="w-full jbr-btn border border-err/40 bg-err/5 text-err text-sm font-semibold">
            ⏹ Stop
          </button>
        </>
      ) : (
        <>
          {state.current && <div className="text-[11px] text-ink-soft">{state.current}</div>}
          <button
            onClick={() => void startBulk()}
            disabled={!enabled}
            className="w-full jbr-btn-primary text-sm font-semibold disabled:opacity-40"
          >
            🚀 Start auto-apply
          </button>
          <p className="text-[10px] text-ink-soft leading-snug">
            Runs on {query ? `your saved search “${query}”` : 'the current results list'}.{' '}
            {bypass ? 'Applies to ALL match levels.' : 'High-match only.'} Stops at {state.target}/day;
            pauses + notifies on questions it can't answer truthfully.
          </p>
        </>
      )}
    </div>
  );
}

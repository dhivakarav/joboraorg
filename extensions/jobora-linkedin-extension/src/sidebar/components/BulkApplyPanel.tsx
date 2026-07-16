import { useEffect, useState } from 'react';
import { startBulk, stopBulk, getBulkState, type BulkState } from '../../autofill/bulk';
import { getProfile } from '../../autofill/profile';

/**
 * Sidebar control for the bulk auto-apply engine. Start → walks the saved
 * search, applies to high-match jobs, stops at the daily safe limit.
 */
export default function BulkApplyPanel() {
  const [state, setState] = useState<BulkState | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [query, setQuery] = useState('');

  useEffect(() => {
    const load = () => getBulkState().then(setState);
    load();
    getProfile().then(p => { setEnabled(p.autoSubmit); setQuery(p.searchQuery || ''); });
    const onChange = (c: Record<string, chrome.storage.StorageChange>) => {
      if (c.jobora_bulk_run) load();
      if (c.jobora_autofill_profile) getProfile().then(p => { setEnabled(p.autoSubmit); setQuery(p.searchQuery || ''); });
    };
    chrome.storage.onChanged.addListener(onChange);
    return () => chrome.storage.onChanged.removeListener(onChange);
  }, []);

  if (!state) return null;

  return (
    <div className="jbr-card p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-ink-soft uppercase tracking-wide">
          Bulk auto-apply
        </span>
        {state.active && <span className="text-[10px] text-brand animate-pulse">running…</span>}
      </div>

      {!enabled && (
        <p className="text-[11px] text-warn leading-snug">
          Turn on “Auto-apply” in the popup first, and set a saved search.
        </p>
      )}

      {enabled && !query && (
        <p className="text-[11px] text-warn leading-snug">
          Set a saved search (role + location) in the popup to run bulk apply.
        </p>
      )}

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
            disabled={!enabled || !query}
            className="w-full jbr-btn-primary text-sm font-semibold disabled:opacity-40"
          >
            🚀 Start auto-apply{query ? ` · “${query}”` : ''}
          </button>
          <p className="text-[10px] text-ink-soft leading-snug">
            Applies to high-match jobs only, stops at {state.target}/day, and pauses +
            notifies you on questions it can’t answer truthfully.
          </p>
        </>
      )}
    </div>
  );
}

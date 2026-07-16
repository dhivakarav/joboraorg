/**
 * Application tracker — recent applications with status + a follow-up nudge for
 * ones sitting >7 days with no movement.
 */
import { useEffect, useState } from 'react';
import { sendMsg } from '../api/messages';
import type { ApplicationsPage, TrackedApplication } from '../types/job';
import Spinner from '../sidebar/components/Spinner';

const STATUS_COLOR: Record<string, string> = {
  'Applied': 'text-brand', 'Submitted': 'text-ok', 'Verified Submitted': 'text-ok',
  'Manual Apply': 'text-warn', 'Tracked': 'text-ink-soft', 'Interview': 'text-ok',
  'Offer': 'text-ok', 'Rejected': 'text-err',
};

function daysSince(iso?: string): number | null {
  if (!iso) return null;
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
}

export default function ApplicationsTracker() {
  const [apps, setApps] = useState<TrackedApplication[] | null>(null);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    sendMsg<ApplicationsPage>({ type: 'GET_APPLICATIONS' }).then(res => {
      if (res.ok) { setApps(res.data.items ?? []); setTotal(res.data.total ?? 0); }
      else setApps([]);
    });
  }, []);

  return (
    <details className="text-xs">
      <summary className="cursor-pointer text-ink-soft hover:text-ink select-none">
        📋 My applications{apps ? ` (${total})` : ''}
      </summary>
      <div className="mt-2 space-y-1.5 max-h-64 overflow-y-auto jbr-scroll">
        {apps === null && <div className="py-2 flex justify-center"><Spinner size="sm" /></div>}
        {apps?.length === 0 && (
          <p className="text-[11px] text-ink-soft py-1">No applications yet — apply to a job to see it here.</p>
        )}
        {apps?.map(a => {
          const d = daysSince(a.applied_at);
          const stale = d !== null && d >= 7 && !['Rejected', 'Offer'].includes(a.display_status);
          return (
            <a
              key={a.id}
              href={a.apply_url || '#'}
              target="_blank"
              rel="noopener noreferrer"
              className="jbr-card block px-2.5 py-2 hover:border-brand/40"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-medium text-ink truncate">{a.job_title}</span>
                <span className="text-[10px] font-semibold text-ink-soft shrink-0">{a.match_score}%</span>
              </div>
              <div className="flex items-center justify-between gap-2 mt-0.5">
                <span className="text-[11px] text-ink-soft truncate">{a.company}</span>
                <span className={`text-[10px] font-medium shrink-0 ${STATUS_COLOR[a.display_status] ?? 'text-ink-soft'}`}>
                  {a.display_status}
                </span>
              </div>
              {stale && (
                <div className="mt-1 text-[10px] text-warn">⏰ {d}d ago — time to follow up</div>
              )}
            </a>
          );
        })}
      </div>
    </details>
  );
}

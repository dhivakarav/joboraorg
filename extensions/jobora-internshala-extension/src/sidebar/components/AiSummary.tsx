import { useEffect, useState } from 'react';
import { sendMsg } from '../../api/messages';
import type { ExtractedJob } from '../../types/job';
import Spinner from './Spinner';

interface AiSummaryProps {
  job: ExtractedJob;
}

type State =
  | { status: 'loading' }
  | { status: 'done'; summary: string; ai: boolean }
  | { status: 'error'; msg: string };

export default function AiSummary({ job }: AiSummaryProps) {
  const [state, setState] = useState<State>({ status: 'loading' });

  useEffect(() => {
    let cancelled = false;
    setState({ status: 'loading' });

    sendMsg<{ summary: string; ai: boolean }>({
      type: 'AI_SUMMARY',
      job,
    }).then(res => {
      if (cancelled) return;
      if (res.ok) setState({ status: 'done', summary: res.data.summary, ai: res.data.ai });
      else setState({ status: 'error', msg: res.error });
    });

    return () => { cancelled = true; };
  // Re-run whenever the job fingerprint changes (new job page)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job.fingerprint]);

  return (
    <div className="jbr-card p-3 space-y-2">
      <div className="flex items-center gap-1.5">
        <span className="text-xs font-semibold text-ink-soft uppercase tracking-wide">
          AI Analysis
        </span>
        {state.status === 'done' && state.ai && (
          <span className="jbr-badge border-brand/30 bg-brand-soft text-brand">Claude</span>
        )}
      </div>

      {state.status === 'loading' && (
        <div className="flex items-center gap-2">
          <Spinner size="sm" />
          <span className="text-xs text-ink-soft">Analysing match…</span>
        </div>
      )}

      {state.status === 'done' && (
        <p className="text-xs text-ink leading-relaxed">{state.summary}</p>
      )}

      {state.status === 'error' && (
        <p className="text-xs text-ink-soft italic">Summary unavailable.</p>
      )}
    </div>
  );
}

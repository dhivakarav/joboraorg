import { useState } from 'react';
import type { ExtResponse } from '../../api/messages';
import Spinner from './Spinner';

interface ActionButtonsProps {
  alreadySaved: boolean;
  /** Track the job in Jobora (POST /api/jobs/apply with status=Tracked). */
  onTrackJob: () => Promise<void>;
  /** Generate AI resume tips — returns the response so we can show it inline. */
  onGenerateTips: () => Promise<ExtResponse<{ tips: string; ai: boolean }> | undefined>;
  /** Generate a cover letter — returns the response for inline display. */
  onGenerateCoverLetter: () => Promise<ExtResponse<{ cover_letter: string; ai: boolean }> | undefined>;
}

type Panel = 'none' | 'tips' | 'letter';

export default function ActionButtons({
  alreadySaved,
  onTrackJob,
  onGenerateTips,
  onGenerateCoverLetter,
}: ActionButtonsProps) {
  const [tracking, setTracking]   = useState(false);
  const [tracked, setTracked]     = useState(alreadySaved);
  const [trackError, setTrackError] = useState('');

  const [tipsLoading, setTipsLoading]     = useState(false);
  const [letterLoading, setLetterLoading] = useState(false);
  const [tips, setTips]         = useState('');
  const [tipsAi, setTipsAi]     = useState(false);
  const [letter, setLetter]     = useState('');
  const [letterAi, setLetterAi] = useState(false);

  const [panel, setPanel]  = useState<Panel>('none');
  const [copied, setCopied] = useState(false);

  async function handleTrack() {
    if (tracked) return;
    setTracking(true);
    setTrackError('');
    try {
      await onTrackJob();
      setTracked(true);
    } catch (e) {
      setTrackError(e instanceof Error ? e.message : 'Failed to track job');
    } finally {
      setTracking(false);
    }
  }

  async function handleTips() {
    if (tips) { setPanel(p => p === 'tips' ? 'none' : 'tips'); return; }
    setTipsLoading(true);
    try {
      const res = await onGenerateTips();
      if (res?.ok) {
        setTips(res.data.tips);
        setTipsAi(res.data.ai);
        setPanel('tips');
      }
    } finally {
      setTipsLoading(false);
    }
  }

  async function handleLetter() {
    if (letter) { setPanel(p => p === 'letter' ? 'none' : 'letter'); return; }
    setLetterLoading(true);
    try {
      const res = await onGenerateCoverLetter();
      if (res?.ok) {
        setLetter(res.data.cover_letter);
        setLetterAi(res.data.ai);
        setPanel('letter');
      }
    } finally {
      setLetterLoading(false);
    }
  }

  function copyText(text: string) {
    navigator.clipboard?.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  const activeText = panel === 'tips' ? tips : panel === 'letter' ? letter : '';

  return (
    <div className="space-y-2.5">
      {/* ── Primary: Track Job ── */}
      <button
        onClick={handleTrack}
        disabled={tracking || tracked}
        className={`w-full jbr-btn text-sm font-semibold transition-all
          ${tracked
            ? 'border border-ok/40 bg-ok/5 text-ok cursor-default'
            : 'jbr-btn-primary'}`}
      >
        {tracking
          ? <><Spinner size="sm" /><span>Tracking…</span></>
          : tracked
            ? '✓ Tracked in Jobora'
            : '📌 Track Job'}
      </button>

      {trackError && (
        <p className="text-xs text-err px-1">{trackError}</p>
      )}

      {/* ── Secondary: AI tools ── */}
      <div className="flex gap-2">
        <button
          onClick={handleTips}
          disabled={tipsLoading}
          className={`jbr-btn-ghost flex-1 text-xs transition-colors
            ${panel === 'tips' ? 'border-brand text-brand bg-brand-soft' : ''}`}
        >
          {tipsLoading ? <Spinner size="sm" /> : '✨ Resume Tips'}
        </button>
        <button
          onClick={handleLetter}
          disabled={letterLoading}
          className={`jbr-btn-ghost flex-1 text-xs transition-colors
            ${panel === 'letter' ? 'border-brand text-brand bg-brand-soft' : ''}`}
        >
          {letterLoading ? <Spinner size="sm" /> : '📝 Cover Letter'}
        </button>
      </div>

      {/* ── Expanded AI panel ── */}
      {panel !== 'none' && activeText && (
        <div className="jbr-card p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-ink-soft uppercase tracking-wide flex items-center gap-1.5">
              {panel === 'tips' ? 'Resume Tips' : 'Cover Letter'}
              {((panel === 'tips' && tipsAi) || (panel === 'letter' && letterAi)) && (
                <span className="jbr-badge border-brand/30 bg-brand-soft text-brand normal-case">Claude AI</span>
              )}
            </span>
            <button onClick={() => copyText(activeText)} className="jbr-btn-ghost px-2 py-0.5 text-xs">
              {copied ? '✓ Copied' : 'Copy'}
            </button>
          </div>
          <div className="text-xs text-ink leading-relaxed whitespace-pre-wrap jbr-scroll max-h-52 overflow-y-auto">
            {activeText}
          </div>
        </div>
      )}
    </div>
  );
}

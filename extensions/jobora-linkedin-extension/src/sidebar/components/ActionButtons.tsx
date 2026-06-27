import { useState } from 'react';
import Spinner from './Spinner';

interface ActionButtonsProps {
  alreadySaved: boolean;
  onSaveJob: () => Promise<void>;
  onGenerateTips: () => Promise<void>;
  onGenerateCoverLetter: () => Promise<void>;
  tips: string;
  coverLetter: string;
  tipsAi: boolean;
  coverLetterAi: boolean;
}

type Panel = 'none' | 'tips' | 'letter';

export default function ActionButtons({
  alreadySaved,
  onSaveJob,
  onGenerateTips,
  onGenerateCoverLetter,
  tips,
  coverLetter,
  tipsAi,
  coverLetterAi,
}: ActionButtonsProps) {
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(alreadySaved);
  const [tipsLoading, setTipsLoading] = useState(false);
  const [letterLoading, setLetterLoading] = useState(false);
  const [panel, setPanel] = useState<Panel>('none');
  const [copied, setCopied] = useState(false);

  async function handleSave() {
    if (saved) return;
    setSaving(true);
    try {
      await onSaveJob();
      setSaved(true);
    } finally {
      setSaving(false);
    }
  }

  async function handleTips() {
    if (tips) { setPanel(p => p === 'tips' ? 'none' : 'tips'); return; }
    setTipsLoading(true);
    try {
      await onGenerateTips();
      setPanel('tips');
    } finally {
      setTipsLoading(false);
    }
  }

  async function handleLetter() {
    if (coverLetter) { setPanel(p => p === 'letter' ? 'none' : 'letter'); return; }
    setLetterLoading(true);
    try {
      await onGenerateCoverLetter();
      setPanel('letter');
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

  const activeText = panel === 'tips' ? tips : panel === 'letter' ? coverLetter : '';

  return (
    <div className="space-y-3">
      {/* Primary actions */}
      <div className="flex gap-2">
        <button
          onClick={handleSave}
          disabled={saving || saved}
          className={`jbr-btn flex-1 ${saved
            ? 'border border-ok/40 bg-ok/5 text-ok cursor-default'
            : 'jbr-btn-primary'}`}
        >
          {saving ? <Spinner size="sm" /> : saved ? '✓ Saved to Jobora' : '🔖 Save Job'}
        </button>
      </div>

      {/* Secondary actions */}
      <div className="flex gap-2">
        <button
          onClick={handleTips}
          disabled={tipsLoading}
          className={`jbr-btn-ghost flex-1 text-xs ${panel === 'tips' ? 'border-brand text-brand bg-brand-soft' : ''}`}
        >
          {tipsLoading ? <Spinner size="sm" /> : '✨ Resume Tips'}
        </button>
        <button
          onClick={handleLetter}
          disabled={letterLoading}
          className={`jbr-btn-ghost flex-1 text-xs ${panel === 'letter' ? 'border-brand text-brand bg-brand-soft' : ''}`}
        >
          {letterLoading ? <Spinner size="sm" /> : '📝 Cover Letter'}
        </button>
      </div>

      {/* Expanded panel */}
      {panel !== 'none' && activeText && (
        <div className="jbr-card p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-ink-soft uppercase tracking-wide">
              {panel === 'tips' ? 'Resume Tips' : 'Cover Letter'}
              {((panel === 'tips' && tipsAi) || (panel === 'letter' && coverLetterAi)) && (
                <span className="ml-1.5 jbr-badge border-brand/30 bg-brand-soft text-brand">AI</span>
              )}
            </span>
            <button
              onClick={() => copyText(activeText)}
              className="jbr-btn-ghost px-2 py-1 text-xs"
            >
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

import { useState } from 'react';
import type { ExtractedJob } from '../../types/job';

interface DebugViewProps {
  job: ExtractedJob;
}

export default function DebugView({ job }: DebugViewProps) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const json = JSON.stringify(job, null, 2);

  function copy() {
    navigator.clipboard?.writeText(json).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="jbr-card overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-3 py-2.5
                   text-xs font-medium text-ink-soft hover:text-ink hover:bg-canvas
                   transition-colors"
      >
        <span className="flex items-center gap-1.5">
          <span className="text-[10px] font-mono bg-elevated rounded px-1 py-0.5">
            JSON
          </span>
          Extraction debug
        </span>
        <span className="text-xs">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="border-t border-edge">
          <div className="flex justify-end px-2 py-1 bg-elevated/50">
            <button onClick={copy} className="jbr-btn-ghost px-2 py-0.5 text-[10px]">
              {copied ? '✓ Copied' : 'Copy JSON'}
            </button>
          </div>
          <pre
            className="px-3 pb-3 text-[10px] leading-relaxed font-mono text-ink-soft
                       overflow-x-auto jbr-scroll max-h-72 whitespace-pre"
          >
            {json}
          </pre>
        </div>
      )}
    </div>
  );
}

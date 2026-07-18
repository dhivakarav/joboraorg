import Spinner from './Spinner';

export type ExtractionPhase =
  | 'idle'            // no job page open
  | 'waiting'         // on a job page but DOM not ready yet
  | 'extracting'      // running extraction
  | 'scoring'         // extraction done, waiting for score API
  | 'ready'           // scored successfully
  | 'extract_failed'  // extractor gave up
  | 'score_failed';   // backend score call failed

interface ExtractionStatusProps {
  phase: ExtractionPhase;
  error?: string;
  attempt?: number;
  onRetry?: () => void;
}

const PHASE_LABEL: Record<ExtractionPhase, string> = {
  idle:           'Open an Internshala internship to see your match score.',
  waiting:        'Waiting for job to load…',
  extracting:     'Reading job details…',
  scoring:        'Scoring against your resume…',
  ready:          '',
  extract_failed: 'Could not read job details.',
  score_failed:   'Could not score this job.',
};

export default function ExtractionStatus({ phase, error, attempt = 0, onRetry }: ExtractionStatusProps) {
  if (phase === 'ready') return null;

  const label = PHASE_LABEL[phase];
  const isSpinner = phase === 'waiting' || phase === 'extracting' || phase === 'scoring';
  const isFailed  = phase === 'extract_failed' || phase === 'score_failed';

  return (
    <div className="flex flex-col items-center gap-3 py-6 px-4 text-center">
      {isSpinner && <Spinner size="md" />}

      {phase === 'idle' && (
        <div className="text-4xl mb-1">💼</div>
      )}

      <p className="text-sm text-ink-soft max-w-[240px] leading-relaxed">
        {label}
      </p>

      {error && (
        <p className="text-xs text-err/80 max-w-[240px]">{error}</p>
      )}

      {attempt > 2 && phase === 'waiting' && (
        <p className="text-xs text-ink-soft/60">
          LinkedIn is taking longer than usual…
        </p>
      )}

      {isFailed && onRetry && (
        <button onClick={onRetry} className="jbr-btn-ghost text-xs mt-1">
          ↻ Retry
        </button>
      )}
    </div>
  );
}

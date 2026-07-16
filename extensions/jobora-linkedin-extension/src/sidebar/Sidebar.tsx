/**
 * Main sidebar — Phase 3 rewrite.
 *
 * Uses a single extraction state machine instead of multiple flags:
 *
 *   idle → waiting → extracting → scoring → ready
 *                ↘              ↘          ↘
 *             extract_failed  score_failed  (retry back to waiting)
 *
 * The toggle tab is always visible (outside the shadow host's width).
 * Opening/closing only resizes the host element — React state is preserved.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { LinkedInAdapter, waitForJobReady } from '../adapters/linkedin';
import { sendMsg } from '../api/messages';
import { watchNavigation, isLinkedInJobPage } from '../content/detector';
import type { ExtractedJob, JobScore, JoBoraUser, ResumeProfile } from '../types/job';
import type { ExtractionPhase } from './components/ExtractionStatus';
import LoginPrompt from './components/LoginPrompt';
import MatchPanel from './components/MatchPanel';
import SkillsPanel from './components/SkillsPanel';
import ActionButtons from './components/ActionButtons';
import AiSummary from './components/AiSummary';
import DebugView from './components/DebugView';
import ExtractionStatus from './components/ExtractionStatus';
import Spinner from './components/Spinner';
import BanMeter from './components/BanMeter';
import BulkApplyPanel from './components/BulkApplyPanel';

// ── Types ─────────────────────────────────────────────────────────────────────

interface SidebarProps {
  hostEl: HTMLDivElement;
}

type AuthState = 'loading' | 'unauthenticated' | 'authenticated';

interface JobState {
  phase: ExtractionPhase;
  job: ExtractedJob | null;
  score: JobScore | null;
  error: string;
  attempt: number;
}

const INITIAL_JOB_STATE: JobState = {
  phase: 'idle',
  job: null,
  score: null,
  error: '',
  attempt: 0,
};

const OPEN_WIDTH  = '400px';
const CLOSED_WIDTH = '0px';

const adapter = new LinkedInAdapter();

// ── Component ─────────────────────────────────────────────────────────────────

export default function Sidebar({ hostEl }: SidebarProps) {
  const [open, setOpen]             = useState(false);
  const [authState, setAuthState]   = useState<AuthState>('loading');
  const [user, setUser]             = useState<JoBoraUser | null>(null);
  const [resume, setResume]         = useState<ResumeProfile | null>(null);
  const [loginError, setLoginError] = useState('');
  const [showDebug, setShowDebug]   = useState(false);

  const [jobState, setJobState]     = useState<JobState>(INITIAL_JOB_STATE);

  // Ref to cancel in-flight extraction when user navigates away mid-run
  const extractionAbort = useRef<AbortController | null>(null);

  // ── Host width ───────────────────────────────────────────────────────────────
  useEffect(() => {
    hostEl.style.width          = open ? OPEN_WIDTH : CLOSED_WIDTH;
    hostEl.style.pointerEvents  = open ? 'all' : 'none';
  }, [open, hostEl]);

  // ── Auth bootstrap ───────────────────────────────────────────────────────────
  useEffect(() => {
    sendMsg<JoBoraUser>({ type: 'GET_ME' }).then(res => {
      if (res.ok) {
        setUser(res.data);
        setAuthState('authenticated');
        loadResume();
      } else {
        setAuthState('unauthenticated');
      }
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function loadResume() {
    sendMsg<ResumeProfile>({ type: 'GET_RESUME' }).then(res => {
      if (res.ok) setResume(res.data);
    });
  }

  async function handleLogin(email: string, password: string) {
    setLoginError('');
    const res = await sendMsg<{ user: JoBoraUser }>({ type: 'LOGIN', email, password });
    if (!res.ok) { setLoginError(res.error); return; }
    setUser(res.data.user);
    setAuthState('authenticated');
    loadResume();
    startExtraction();
  }

  async function handleLogout() {
    await sendMsg({ type: 'LOGOUT' });
    setUser(null);
    setAuthState('unauthenticated');
    setJobState(INITIAL_JOB_STATE);
  }

  // ── Extraction state machine ─────────────────────────────────────────────────

  const startExtraction = useCallback(() => {
    // Cancel any previous in-flight extraction
    extractionAbort.current?.abort();
    const abort = new AbortController();
    extractionAbort.current = abort;

    const url = window.location.href;

    if (!isLinkedInJobPage(url)) {
      setJobState({ ...INITIAL_JOB_STATE, phase: 'idle' });
      return;
    }

    setJobState(s => ({ ...INITIAL_JOB_STATE, phase: 'waiting', attempt: s.attempt + 1 }));

    // Wait for the job title to appear in the DOM
    waitForJobReady(12_000)
      .then(() => {
        if (abort.signal.aborted) return;
        setJobState(s => ({ ...s, phase: 'extracting' }));

        // Small delay to let LinkedIn finish painting the full card
        return new Promise<void>(r => setTimeout(r, 300));
      })
      .then(() => {
        if (abort.signal.aborted) return;

        const extracted = adapter.extract();
        if (!extracted) {
          setJobState(s => ({
            ...s,
            phase: 'extract_failed',
            error: 'Job details not found on this page.',
          }));
          return;
        }

        setJobState(s => ({ ...s, phase: 'scoring', job: extracted }));

        return sendMsg<JobScore>({ type: 'SCORE_JOB', job: extracted }).then(res => {
          if (abort.signal.aborted) return;
          if (res.ok) {
            // Adopt the backend's canonical fingerprint (SHA-256 of
            // source|company|title|url). The adapter's synchronous fingerprint
            // is a non-cryptographic approximation that never matches the hash
            // the backend uses for its `already_saved` lookup — so without this
            // Track Job would never reflect as saved. Overwrite it here.
            setJobState(s => ({
              ...s,
              phase: 'ready',
              score: res.data,
              job: s.job ? { ...s.job, fingerprint: res.data.fingerprint } : s.job,
            }));
          } else {
            setJobState(s => ({
              ...s,
              phase: 'score_failed',
              error: res.error,
            }));
          }
        });
      })
      .catch(err => {
        if (abort.signal.aborted) return;
        const msg = err instanceof Error ? err.message : 'Unknown extraction error';
        setJobState(s => ({ ...s, phase: 'extract_failed', error: msg }));
      });
  }, []);

  // ── Navigation watcher ───────────────────────────────────────────────────────
  useEffect(() => {
    if (authState !== 'authenticated') return;

    startExtraction();

    const stopWatch = watchNavigation(() => {
      // Small debounce — LinkedIn may fire multiple mutations for one navigation
      setTimeout(startExtraction, 600);
    });

    return () => {
      stopWatch();
      extractionAbort.current?.abort();
    };
  }, [authState, startExtraction]);

  // ── User actions ─────────────────────────────────────────────────────────────
  async function handleTrackJob() {
    if (!jobState.job) return;
    const saveRes = await sendMsg({ type: 'SAVE_JOB', job: jobState.job });
    // Surface a failed save to ActionButtons (which catches + shows the error)
    // instead of silently marking the job as tracked.
    if (!saveRes.ok) throw new Error(saveRes.error);
    // Refresh score so already_saved updates
    const res = await sendMsg<JobScore>({ type: 'SCORE_JOB', job: jobState.job });
    if (res.ok) setJobState(s => ({ ...s, score: res.data }));
  }

  async function handleGenerateTips() {
    if (!jobState.job) return;
    return sendMsg<{ tips: string; ai: boolean }>({ type: 'AI_TIPS', job: jobState.job });
  }

  async function handleGenerateCoverLetter() {
    if (!jobState.job) return;
    return sendMsg<{ cover_letter: string; ai: boolean }>({ type: 'COVER_LETTER', job: jobState.job });
  }

  // ── Render ───────────────────────────────────────────────────────────────────
  const { phase, job, score, error, attempt } = jobState;

  return (
    <div id="jobora-sidebar-root-inner" style={{ height: '100%' }}>
      {/* ── Toggle tab — always visible ── */}
      <button
        onClick={() => setOpen(o => !o)}
        title={open ? 'Close Jobora' : 'Open Jobora'}
        style={{
          position: 'fixed',
          right: open ? OPEN_WIDTH : '0',
          top: '50%',
          transform: 'translateY(-50%)',
          transition: 'right 0.28s cubic-bezier(0.4,0,0.2,1)',
          zIndex: 2147483646,
          pointerEvents: 'all',
        }}
        className="flex flex-col items-center justify-center w-9 h-20 rounded-l-btn
                   bg-brand text-white shadow-lift-l hover:bg-brand-hover focus:outline-none"
        aria-label={open ? 'Close Jobora sidebar' : 'Open Jobora sidebar'}
      >
        {/* Match score badge when ready + closed */}
        {!open && phase === 'ready' && score && (
          <span className="text-[10px] font-bold leading-none mb-0.5">
            {score.match_score}%
          </span>
        )}
        <span
          className="text-[8px] font-bold tracking-widest leading-none"
          style={{ writingMode: 'vertical-rl', textOrientation: 'mixed' }}
        >
          JOBORA
        </span>
        <span className="mt-1 text-[10px]">{open ? '›' : '‹'}</span>
      </button>

      {/* ── Sidebar panel ── */}
      {open && (
        <div
          className="flex flex-col bg-canvas h-screen border-l border-edge
                     shadow-[-4px_0_32px_rgba(15,23,42,0.12)] fixed right-0 top-0"
          style={{ width: OPEN_WIDTH, pointerEvents: 'all' }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-edge shrink-0">
            <div className="flex items-center gap-2">
              <div className="h-6 w-6 rounded-btn bg-brand flex items-center justify-center shrink-0">
                <span className="text-white text-[10px] font-bold">J</span>
              </div>
              <span className="text-sm font-semibold text-ink">Jobora</span>
              {phase === 'waiting' || phase === 'extracting' || phase === 'scoring'
                ? <Spinner size="sm" />
                : null}
            </div>

            <div className="flex items-center gap-1.5">
              {/* Debug toggle lives in the footer — see the "debug" button there. */}
              {user && (
                <>
                  <span className="text-xs text-ink-soft truncate max-w-[110px]">
                    {user.full_name || user.email}
                  </span>
                  <button onClick={handleLogout} className="jbr-btn-ghost px-2 py-1 text-xs">
                    Out
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto jbr-scroll">

            {/* ─ Loading auth ─ */}
            {authState === 'loading' && (
              <div className="flex items-center justify-center h-32">
                <Spinner label="Connecting…" />
              </div>
            )}

            {/* ─ Not signed in ─ */}
            {authState === 'unauthenticated' && (
              <LoginPrompt onLogin={handleLogin} error={loginError} />
            )}

            {/* ─ Authenticated ─ */}
            {authState === 'authenticated' && (
              <div className="p-4 space-y-4">

                {/* Job metadata (shown as soon as we have the job) */}
                {job && (
                  <div className="space-y-1">
                    <div className="flex items-start gap-2">
                      {job.companyLogoUrl && (
                        <img
                          src={job.companyLogoUrl}
                          alt={job.company}
                          className="h-9 w-9 rounded object-contain border border-edge shrink-0"
                          onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
                        />
                      )}
                      <div className="min-w-0">
                        <h2 className="text-sm font-semibold text-ink leading-snug line-clamp-2">
                          {job.title}
                        </h2>
                        <p className="text-xs text-ink-soft mt-0.5">
                          {job.company}
                          {job.location ? ` · ${job.location}` : ''}
                        </p>
                      </div>
                    </div>

                    {/* Badges row */}
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      {job.employmentType && (
                        <span className="jbr-badge border-edge text-ink-soft">{job.employmentType}</span>
                      )}
                      {job.experienceLevel && (
                        <span className="jbr-badge border-edge text-ink-soft">{job.experienceLevel}</span>
                      )}
                      {job.workplaceType && (
                        <span className="jbr-badge border-edge text-ink-soft">{job.workplaceType}</span>
                      )}
                      {job.easyApply && (
                        <span className="jbr-badge border-brand/40 bg-brand-soft text-brand">
                          ⚡ Easy Apply
                        </span>
                      )}
                      {job.salary && (
                        <span className="jbr-badge border-ok/40 bg-ok/5 text-ok">
                          {job.salary}
                        </span>
                      )}
                    </div>

                    {/* Recruiter */}
                    {job.recruiterName && (
                      <p className="text-[11px] text-ink-soft">
                        Posted by {job.recruiterName}
                        {job.recruiterTitle ? ` · ${job.recruiterTitle}` : ''}
                      </p>
                    )}

                    {/* Posted date */}
                    {job.postedAt && (
                      <p className="text-[11px] text-ink-soft">{job.postedAt}</p>
                    )}
                  </div>
                )}

                {/* Extraction / scoring status (idle, waiting, failed, etc.) */}
                {phase !== 'ready' && (
                  <ExtractionStatus
                    phase={phase}
                    error={error}
                    attempt={attempt}
                    onRetry={startExtraction}
                  />
                )}

                {/* Score ring + tier + reasons */}
                {phase === 'ready' && score && (
                  <MatchPanel score={score} />
                )}

                {/* AI match summary (auto-triggered) */}
                {phase === 'ready' && job && (
                  <AiSummary job={job} />
                )}

                {/* Skills breakdown */}
                {phase === 'ready' && score && job && (
                  <SkillsPanel
                    missingSkills={score.missing_skills}
                    resumeSkills={resume?.parsed_skills ?? []}
                    jobSkills={job.skills}
                  />
                )}

                {/* Track Job + AI buttons.
                    Keyed by the stable job URL so the component remounts on
                    every job change — otherwise its internal `tracked`/tips/
                    letter state would leak from the previous job (e.g. a new,
                    unsaved job would still show "✓ Tracked"). */}
                {job && phase !== 'idle' && phase !== 'extract_failed' && (
                  <ActionButtons
                    key={job.url}
                    alreadySaved={score?.already_saved ?? false}
                    onTrackJob={handleTrackJob}
                    onGenerateTips={handleGenerateTips}
                    onGenerateCoverLetter={handleGenerateCoverLetter}
                  />
                )}

                {/* Score failed — show track anyway */}
                {phase === 'score_failed' && job && (
                  <div className="rounded-btn bg-warn/10 border border-warn/20 px-3 py-2 text-xs text-warn/80">
                    Scoring failed — you can still track this job manually.
                  </div>
                )}

                {/* Bulk auto-apply engine */}
                <BulkApplyPanel />

                {/* Ban-risk meter — applications submitted today */}
                <BanMeter />

                {/* Resume status pill */}
                {resume !== null && (
                  <div className="jbr-card px-3 py-2 flex items-center justify-between">
                    <span className="text-xs text-ink-soft">Resume</span>
                    <span className={`text-xs font-medium ${resume.has_resume ? 'text-ok' : 'text-warn'}`}>
                      {resume.has_resume
                        ? `✓ ${resume.parsed_skills.length} skills`
                        : '⚠ No resume — upload at jobora.app'}
                    </span>
                  </div>
                )}

                {/* Debug JSON view */}
                {showDebug && job && <DebugView job={job} />}

              </div>
            )}
          </div>

          {/* Footer */}
          <div className="shrink-0 px-4 py-2 border-t border-edge flex items-center justify-between">
            <a
              href="https://jobora.app"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[10px] text-ink-soft hover:text-ink"
            >
              jobora.app ↗
            </a>
            {job && (
              <button
                onClick={() => setShowDebug(d => !d)}
                className={`text-[10px] font-mono px-1.5 py-0.5 rounded
                           border transition-colors
                           ${showDebug
                            ? 'border-brand/40 text-brand bg-brand-soft'
                            : 'border-edge text-ink-soft hover:text-ink'}`}
              >
                {showDebug ? 'hide JSON' : 'debug'}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

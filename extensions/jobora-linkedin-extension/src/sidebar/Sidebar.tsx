/**
 * Main sidebar component.
 *
 * Mounted inside a Shadow DOM by the content script. Manages:
 *   • open/closed state (toggle button always visible)
 *   • auth state (show LoginPrompt or job analysis)
 *   • job extraction on page load + SPA navigation
 *   • communication with the background SW via chrome.runtime.sendMessage
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { adapterFor } from '../adapters/registry';
import { sendMsg } from '../api/messages';
import type { ExtractedJob, JobScore, JoBoraUser, ResumeProfile } from '../types/job';
import LoginPrompt from './components/LoginPrompt';
import MatchPanel from './components/MatchPanel';
import SkillsPanel from './components/SkillsPanel';
import ActionButtons from './components/ActionButtons';
import Spinner from './components/Spinner';

interface SidebarProps {
  /** The host element in the real DOM — we resize it as the sidebar opens/closes. */
  hostEl: HTMLDivElement;
}

const OPEN_WIDTH = '380px';
const CLOSED_WIDTH = '0px';

// ── Types ──────────────────────────────────────────────────────────────────────
type AuthState = 'loading' | 'unauthenticated' | 'authenticated';

// ── Component ──────────────────────────────────────────────────────────────────
export default function Sidebar({ hostEl }: SidebarProps) {
  const [open, setOpen]         = useState(false);
  const [authState, setAuthState] = useState<AuthState>('loading');
  const [user, setUser]         = useState<JoBoraUser | null>(null);
  const [resume, setResume]     = useState<ResumeProfile | null>(null);
  const [loginError, setLoginError] = useState('');

  const [job, setJob]           = useState<ExtractedJob | null>(null);
  const [score, setScore]       = useState<JobScore | null>(null);
  const [scoreLoading, setScoreLoading] = useState(false);
  const [scoreError, setScoreError]     = useState('');

  const [tips, setTips]         = useState('');
  const [tipsAi, setTipsAi]     = useState(false);
  const [letter, setLetter]     = useState('');
  const [letterAi, setLetterAi] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);

  // ── Host width ───────────────────────────────────────────────────────────────
  useEffect(() => {
    hostEl.style.width = open ? OPEN_WIDTH : CLOSED_WIDTH;
    hostEl.style.pointerEvents = open ? 'all' : 'none';
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
    extractAndScore();
  }

  async function handleLogout() {
    await sendMsg({ type: 'LOGOUT' });
    setUser(null);
    setAuthState('unauthenticated');
    setScore(null);
    setJob(null);
  }

  // ── Job extraction + scoring ─────────────────────────────────────────────────
  const extractAndScore = useCallback(() => {
    const adapter = adapterFor(location.href);
    if (!adapter) return;

    // LinkedIn renders asynchronously — retry briefly until the DOM is ready
    let attempts = 0;
    const tryExtract = () => {
      const extracted = adapter.extract();
      if (!extracted && attempts < 15) {
        attempts++;
        setTimeout(tryExtract, 400);
        return;
      }
      if (!extracted) return;

      setJob(extracted);
      setScore(null);
      setTips('');
      setLetter('');
      setScoreError('');
      setScoreLoading(true);

      sendMsg<JobScore>({ type: 'SCORE_JOB', job: extracted }).then(res => {
        setScoreLoading(false);
        if (res.ok) setScore(res.data);
        else setScoreError(res.error);
      });
    };

    tryExtract();
  }, []);

  // On mount and on SPA navigation events
  useEffect(() => {
    if (authState !== 'authenticated') return;
    extractAndScore();

    const container = containerRef.current;
    if (!container) return;

    const onNavigate = () => {
      setJob(null);
      setScore(null);
      setTimeout(extractAndScore, 800); // wait for LinkedIn to render new job
    };
    container.addEventListener('jobora:navigate', onNavigate);
    return () => container.removeEventListener('jobora:navigate', onNavigate);
  }, [authState, extractAndScore]);

  // ── Actions ──────────────────────────────────────────────────────────────────
  async function handleSaveJob() {
    if (!job) return;
    await sendMsg({ type: 'SAVE_JOB', job });
  }

  async function handleGenerateTips() {
    if (!job) return;
    const res = await sendMsg<{ tips: string; ai: boolean }>({ type: 'AI_TIPS', job });
    if (res.ok) { setTips(res.data.tips); setTipsAi(res.data.ai); }
  }

  async function handleGenerateCoverLetter() {
    if (!job) return;
    const res = await sendMsg<{ cover_letter: string; ai: boolean }>({ type: 'COVER_LETTER', job });
    if (res.ok) { setLetter(res.data.cover_letter); setLetterAi(res.data.ai); }
  }

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    <div ref={containerRef} id="jobora-sidebar-root-inner" style={{ height: '100%' }}>
      {/* ── Toggle tab (always visible, even when closed) ── */}
      <button
        onClick={() => setOpen(o => !o)}
        title={open ? 'Close Jobora' : 'Open Jobora'}
        style={{
          position: 'fixed',
          right: open ? '380px' : '0',
          top: '50%',
          transform: 'translateY(-50%)',
          transition: 'right 0.28s cubic-bezier(0.4,0,0.2,1)',
          zIndex: 2147483646,
          pointerEvents: 'all',
        }}
        className="flex flex-col items-center justify-center w-9 h-20 rounded-l-btn
                   bg-brand text-white shadow-lift-l hover:bg-brand-hover
                   focus:outline-none"
        aria-label={open ? 'Close Jobora sidebar' : 'Open Jobora sidebar'}
      >
        {/* Vertical "Jobora" label */}
        <span className="text-[9px] font-bold tracking-widest"
              style={{ writingMode: 'vertical-rl', textOrientation: 'mixed' }}>
          JOBORA
        </span>
        <span className="mt-1 text-xs">{open ? '›' : '‹'}</span>
      </button>

      {/* ── Sidebar panel ── */}
      {open && (
        <div
          className="jbr-sidebar-panel flex flex-col bg-canvas h-screen w-[380px]
                     border-l border-edge shadow-[-4px_0_24px_rgba(15,23,42,0.10)]
                     fixed right-0 top-0"
          style={{ pointerEvents: 'all' }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-edge shrink-0">
            <div className="flex items-center gap-2">
              <div className="h-6 w-6 rounded-btn bg-brand flex items-center justify-center">
                <span className="text-white text-[10px] font-bold">J</span>
              </div>
              <span className="text-sm font-semibold text-ink">Jobora</span>
            </div>
            {user && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-ink-soft truncate max-w-[140px]">
                  {user.full_name || user.email}
                </span>
                <button
                  onClick={handleLogout}
                  className="jbr-btn-ghost px-2 py-1 text-xs"
                >
                  Sign out
                </button>
              </div>
            )}
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto jbr-scroll">
            {authState === 'loading' && (
              <div className="flex items-center justify-center h-32">
                <Spinner label="Connecting…" />
              </div>
            )}

            {authState === 'unauthenticated' && (
              <LoginPrompt onLogin={handleLogin} error={loginError} />
            )}

            {authState === 'authenticated' && (
              <div className="p-4 space-y-4">
                {/* Job meta */}
                {job ? (
                  <div>
                    <h2 className="text-sm font-semibold text-ink leading-snug">
                      {job.title}
                    </h2>
                    <p className="text-xs text-ink-soft mt-0.5">
                      {job.company}{job.location ? ` · ${job.location}` : ''}
                    </p>
                    {job.employmentType && (
                      <div className="flex gap-1.5 mt-1.5 flex-wrap">
                        <span className="jbr-badge border-edge text-ink-soft">
                          {job.employmentType}
                        </span>
                        {job.experienceLevel && (
                          <span className="jbr-badge border-edge text-ink-soft">
                            {job.experienceLevel}
                          </span>
                        )}
                        {job.easyApply && (
                          <span className="jbr-badge border-brand/30 bg-brand-soft text-brand">
                            Easy Apply
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-ink-soft">
                    Open a LinkedIn job listing to see your match score.
                  </p>
                )}

                {/* Match score */}
                {scoreLoading && (
                  <div className="flex items-center gap-2 text-xs text-ink-soft">
                    <Spinner size="sm" />
                    Scoring against your resume…
                  </div>
                )}
                {scoreError && (
                  <div className="rounded-btn bg-err/10 border border-err/20 px-3 py-2 text-xs text-err">
                    {scoreError}
                  </div>
                )}
                {score && !scoreLoading && <MatchPanel score={score} />}

                {/* Skills breakdown */}
                {score && job && (
                  <SkillsPanel
                    missingSkills={score.missing_skills}
                    resumeSkills={resume?.parsed_skills ?? []}
                    jobSkills={job.skills}
                  />
                )}

                {/* Actions */}
                {job && (
                  <ActionButtons
                    alreadySaved={score?.already_saved ?? false}
                    onSaveJob={handleSaveJob}
                    onGenerateTips={handleGenerateTips}
                    onGenerateCoverLetter={handleGenerateCoverLetter}
                    tips={tips}
                    coverLetter={letter}
                    tipsAi={tipsAi}
                    coverLetterAi={letterAi}
                  />
                )}

                {/* Resume status */}
                {resume !== null && (
                  <div className="jbr-card px-3 py-2 flex items-center justify-between">
                    <span className="text-xs text-ink-soft">Resume</span>
                    <span className={`text-xs font-medium ${resume.has_resume ? 'text-ok' : 'text-warn'}`}>
                      {resume.has_resume
                        ? `✓ Uploaded (${resume.parsed_skills.length} skills)`
                        : '⚠ No resume — upload at jobora.app'}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="shrink-0 px-4 py-2 border-t border-edge text-center">
            <a
              href="https://jobora.app"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[10px] text-ink-soft hover:text-ink"
            >
              Open Jobora Dashboard ↗
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

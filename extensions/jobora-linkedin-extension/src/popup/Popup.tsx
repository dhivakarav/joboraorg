/**
 * Browser-action popup.
 *
 * Shows auth status, server URL setting, and quick links to the Jobora dashboard.
 * The popup runs in the extension context so it can call the Jobora API directly
 * (no CORS restriction) — but for simplicity it also goes via the background SW.
 */
import { useEffect, useState } from 'react';
import { sendMsg } from '../api/messages';
import type { JoBoraUser, ResumeProfile } from '../types/job';
import Spinner from '../sidebar/components/Spinner';
import AutofillSettings from './AutofillSettings';

// Default API base shown in "Server settings". Baked in at build time
// (build.mjs vite `define`) — production by default, or the JOBORA_API_BASE
// override for local dev builds. Keeps a fresh install off localhost for
// real users while letting local builds point at http://localhost:8000/api.
const DEFAULT_BASE =
  typeof __JOBORA_API_BASE__ !== 'undefined'
    ? __JOBORA_API_BASE__
    : 'https://jobara-api.onrender.com/api';

type AuthState = 'loading' | 'unauthenticated' | 'authenticated';

export default function Popup() {
  const [authState, setAuthState]   = useState<AuthState>('loading');
  const [user, setUser]             = useState<JoBoraUser | null>(null);
  const [resume, setResume]         = useState<ResumeProfile | null>(null);
  const [email, setEmail]           = useState('');
  const [password, setPassword]     = useState('');
  const [loginError, setLoginError] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);

  // API base URL setting
  const [apiBase, setApiBase]       = useState('');
  const [apiBaseSaved, setApiBaseSaved] = useState(false);

  useEffect(() => {
    chrome.storage.local.get(['jobora_api_base'], ({ jobora_api_base }) => {
      setApiBase((jobora_api_base as string | undefined) ?? DEFAULT_BASE);
    });

    sendMsg<JoBoraUser>({ type: 'GET_ME' }).then(res => {
      if (res.ok) {
        setUser(res.data);
        setAuthState('authenticated');
        sendMsg<ResumeProfile>({ type: 'GET_RESUME' }).then(r => {
          if (r.ok) setResume(r.data);
        });
      } else {
        setAuthState('unauthenticated');
      }
    });
  }, []);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoginError('');
    setLoginLoading(true);
    try {
      const res = await sendMsg<{ user: JoBoraUser }>({ type: 'LOGIN', email, password });
      if (!res.ok) { setLoginError(res.error); return; }
      setUser(res.data.user);
      setAuthState('authenticated');
      const r = await sendMsg<ResumeProfile>({ type: 'GET_RESUME' });
      if (r.ok) setResume(r.data);
    } finally {
      setLoginLoading(false);
    }
  }

  async function handleLogout() {
    await sendMsg({ type: 'LOGOUT' });
    setUser(null);
    setAuthState('unauthenticated');
    setResume(null);
  }

  function saveApiBase() {
    chrome.storage.local.set({ jobora_api_base: apiBase.trim() }, () => {
      setApiBaseSaved(true);
      setTimeout(() => setApiBaseSaved(false), 2000);
    });
  }

  return (
    <div className="w-72 bg-canvas font-sans text-ink antialiased">
      {/* Header */}
      <div className="flex items-center gap-2.5 px-4 py-3 border-b border-edge">
        <div className="h-7 w-7 rounded-btn bg-brand flex items-center justify-center shrink-0">
          <span className="text-white text-xs font-bold">J</span>
        </div>
        <div>
          <div className="text-sm font-semibold text-ink">Jobora</div>
          <div className="text-[10px] text-ink-soft">LinkedIn Integration</div>
        </div>
      </div>

      <div className="p-4 space-y-4">
        {authState === 'loading' && (
          <div className="flex justify-center py-4">
            <Spinner label="Loading…" />
          </div>
        )}

        {/* ── Authenticated ── */}
        {authState === 'authenticated' && user && (
          <>
            <div className="jbr-card px-3 py-2.5 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-ink">
                  {user.full_name || user.email}
                </span>
                <span className="jbr-badge border-ok/30 bg-ok/5 text-ok">Connected</span>
              </div>
              <div className="text-[11px] text-ink-soft">{user.email}</div>
            </div>

            <div className="jbr-card px-3 py-2.5">
              <div className="text-xs text-ink-soft mb-1">Resume</div>
              {resume ? (
                <div className={`text-xs font-medium ${resume.has_resume ? 'text-ok' : 'text-warn'}`}>
                  {resume.has_resume
                    ? `✓ ${resume.parsed_skills.length} skills parsed`
                    : '⚠ No resume uploaded'}
                </div>
              ) : (
                <Spinner size="sm" />
              )}
            </div>

            <div className="flex gap-2">
              <a
                href="https://jobora.app/app/dashboard"
                target="_blank"
                rel="noopener noreferrer"
                className="jbr-btn-primary flex-1 text-xs"
              >
                Open Dashboard ↗
              </a>
              <button onClick={handleLogout} className="jbr-btn-ghost text-xs px-3">
                Sign out
              </button>
            </div>
          </>
        )}

        {/* ── Login form ── */}
        {authState === 'unauthenticated' && (
          <>
            <p className="text-xs text-ink-soft leading-relaxed">
              Sign in to score LinkedIn jobs against your Jobora resume.
            </p>

            {loginError && (
              <div className="rounded-btn bg-err/10 border border-err/20 px-3 py-2 text-xs text-err">
                {loginError}
              </div>
            )}

            <form onSubmit={handleLogin} className="space-y-2.5">
              <div>
                <label className="jbr-label">Email</label>
                <input
                  type="email"
                  className="jbr-input"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  autoComplete="email"
                />
              </div>
              <div>
                <label className="jbr-label">Password</label>
                <input
                  type="password"
                  className="jbr-input"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  autoComplete="current-password"
                />
              </div>
              <button type="submit" className="jbr-btn-primary w-full" disabled={loginLoading}>
                {loginLoading ? <Spinner size="sm" /> : 'Sign in'}
              </button>
            </form>
          </>
        )}

        {/* ── Autofill profile ── */}
        {authState === 'authenticated' && <AutofillSettings />}

        {/* ── API base URL (dev setting) ── */}
        <details className="text-xs">
          <summary className="cursor-pointer text-ink-soft hover:text-ink select-none">
            ⚙ Server settings
          </summary>
          <div className="mt-2 space-y-1.5">
            <label className="jbr-label">API base URL</label>
            <input
              type="url"
              className="jbr-input text-xs"
              value={apiBase}
              onChange={e => setApiBase(e.target.value)}
              placeholder={DEFAULT_BASE}
            />
            <button onClick={saveApiBase} className="jbr-btn-ghost text-xs w-full">
              {apiBaseSaved ? '✓ Saved' : 'Save'}
            </button>
          </div>
        </details>
      </div>
    </div>
  );
}

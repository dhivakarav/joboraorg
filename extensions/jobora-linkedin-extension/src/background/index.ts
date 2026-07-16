/**
 * Background service worker — the only place that calls the Jobora backend.
 *
 * Extension service workers bypass CORS for hosts in host_permissions,
 * so all API calls are proxied here from content scripts + the popup.
 *
 * Message handling is the only public surface: content script and popup
 * send chrome.runtime.sendMessage() and receive a typed response.
 */
import { api, login, logout, getAuth, clearAuth } from '../api/client';
import type { ExtRequest, ExtResponse } from '../api/messages';
import type { ExtractedJob, JoBoraUser } from '../types/job';

// ── Proactive token refresh via alarm ─────────────────────────────────────────

const ALARM_NAME = 'jobora_token_refresh';
const REFRESH_INTERVAL_MIN = 50; // refresh every 50 min (access token TTL = 60 min)

chrome.alarms.create(ALARM_NAME, { periodInMinutes: REFRESH_INTERVAL_MIN });

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== ALARM_NAME) return;
  const auth = await getAuth();
  if (!auth) return;
  // getValidToken() inside api.get handles the refresh transparently
  try {
    await api.get<JoBoraUser>('/auth/me');
  } catch {
    // Token is dead — clear storage so the UI shows the login prompt
    await clearAuth();
  }
});

// ── Helpers ────────────────────────────────────────────────────────────────────

function ok<T>(data: T): ExtResponse<T> {
  return { ok: true, data };
}

function err(msg: string): ExtResponse<never> {
  return { ok: false, error: msg };
}

function jobPayload(job: ExtractedJob) {
  return {
    title: job.title,
    company: job.company,
    location: job.location,
    description_snippet: job.description.slice(0, 1500),
    employment_type: job.employmentType,
    experience_level: job.experienceLevel,
    salary: job.salary,
    source: job.source,
    url: job.url,
    skills: job.skills,
  };
}

// ── Message router ─────────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener(
  (msg: ExtRequest, _sender, sendResponse: (r: ExtResponse<unknown>) => void) => {

    (async () => {
      try {
        switch (msg.type) {

          case 'LOGIN': {
            await login(msg.email, msg.password);
            const user = await api.get<JoBoraUser>('/auth/me');
            sendResponse(ok({ user }));
            break;
          }

          case 'LOGOUT': {
            await logout();
            sendResponse(ok({ message: 'Logged out' }));
            break;
          }

          case 'GET_ME': {
            const auth = await getAuth();
            if (!auth) { sendResponse(err('Not authenticated')); break; }
            const user = await api.get<JoBoraUser>('/auth/me');
            sendResponse(ok(user));
            break;
          }

          case 'GET_RESUME': {
            const resume = await api.get('/resume/parsed');
            sendResponse(ok(resume));
            break;
          }

          case 'SCORE_JOB': {
            const score = await api.post('/jobs/score', jobPayload(msg.job));
            sendResponse(ok(score));
            break;
          }

          case 'GET_APPLICATIONS': {
            const apps = await api.get('/applications?page_size=25');
            sendResponse(ok(apps));
            break;
          }

          case 'SHOW_NOTIFICATION': {
            // Inline 1×1 icon so notifications work without shipping an icon asset.
            const ICON = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
            chrome.notifications.create({
              type: 'basic',
              iconUrl: ICON,
              title: msg.title,
              message: msg.message,
            }, () => void chrome.runtime.lastError);
            sendResponse(ok({}));
            break;
          }

          case 'SAVE_JOB': {
            // Re-use the existing POST /api/jobs/apply endpoint — no new API needed.
            const payload = {
              fingerprint: msg.job.fingerprint,
              source: msg.job.source,
              title: msg.job.title,
              company: msg.job.company,
              location: msg.job.location,
              salary: msg.job.salary,
              salary_inr: '',
              apply_url: msg.job.url,
              verified: false,
              match_score: 0,
              platform: msg.job.source,
              manual_required: true,
              status: 'Tracked',
            };
            const saved = await api.post('/jobs/apply', payload);
            sendResponse(ok(saved));
            break;
          }

          case 'AI_TIPS': {
            const tips = await api.post('/jobs/ai-tips', jobPayload(msg.job));
            sendResponse(ok(tips));
            break;
          }

          case 'AI_SUMMARY': {
            const summary = await api.post('/jobs/ai-summary', jobPayload(msg.job));
            sendResponse(ok(summary));
            break;
          }

          case 'COVER_LETTER': {
            const letter = await api.post('/jobs/cover-letter', jobPayload(msg.job));
            sendResponse(ok(letter));
            break;
          }

          default:
            sendResponse(err('Unknown message type'));
        }
      } catch (e: unknown) {
        sendResponse(err(e instanceof Error ? e.message : 'Unknown error'));
      }
    })();

    // Return true to keep the message channel open for the async response
    return true;
  },
);

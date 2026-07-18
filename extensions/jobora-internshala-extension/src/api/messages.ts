/**
 * Typed message protocol between the content script and the background
 * service worker.
 *
 * WHY route through the background?
 *   Content scripts run in the web-page context and are subject to CORS.
 *   Extension service workers are exempt from CORS for hosts listed in
 *   `host_permissions` — so ALL Jobora API calls go through the background.
 */
import type { ExtractedJob, JobScore, JoBoraUser, ResumeProfile, SavedApplication } from '../types/job';

// ── Request types ──────────────────────────────────────────────────────────────

export type ExtRequest =
  | { type: 'LOGIN'; email: string; password: string }
  | { type: 'LOGOUT' }
  | { type: 'GET_ME' }
  | { type: 'GET_RESUME' }
  | { type: 'SCORE_JOB'; job: ExtractedJob }
  | { type: 'SAVE_JOB'; job: ExtractedJob }
  | { type: 'AI_TIPS'; job: ExtractedJob }
  | { type: 'AI_SUMMARY'; job: ExtractedJob }
  | { type: 'COVER_LETTER'; job: ExtractedJob }
  | { type: 'GET_APPLICATIONS' }
  | { type: 'ANSWER_FIELD'; label: string; fieldType: 'text' | 'choice' | 'number'; options: string[]; jobTitle: string; jobCompany: string }
  | { type: 'SHOW_NOTIFICATION'; title: string; message: string };

// ── Response types ─────────────────────────────────────────────────────────────

export type ExtResponse<T = unknown> =
  | { ok: true; data: T }
  | { ok: false; error: string };

export type LoginResponse     = ExtResponse<{ user: JoBoraUser }>;
export type LogoutResponse    = ExtResponse<{ message: string }>;
export type MeResponse        = ExtResponse<JoBoraUser>;
export type ResumeResponse    = ExtResponse<ResumeProfile>;
export type ScoreResponse     = ExtResponse<JobScore>;
export type SaveResponse      = ExtResponse<SavedApplication>;
export type AiTipsResponse    = ExtResponse<{ tips: string; ai: boolean }>;
export type CoverLetterResponse = ExtResponse<{ cover_letter: string; ai: boolean }>;

// ── Helper to send a message and get a typed response ─────────────────────────

export function sendMsg<T>(req: ExtRequest): Promise<ExtResponse<T>> {
  return chrome.runtime.sendMessage(req) as Promise<ExtResponse<T>>;
}

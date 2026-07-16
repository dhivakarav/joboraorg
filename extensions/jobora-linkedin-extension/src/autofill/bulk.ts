/**
 * Bulk auto-apply engine.
 *
 * When the user clicks "Start auto-apply" in the sidebar, this walks the current
 * LinkedIn search results, scores each job against the resume, and auto-applies
 * ONLY to high-match ones — pausing + notifying the user when a job asks a
 * question it can't answer truthfully. Throttled by the daily ban meter.
 *
 * Design choices (confirmed with the user):
 *   - Source: a saved search the user configured (navigates there first).
 *   - Selectivity: high-match only (>= profile.autoSubmitMinMatch).
 *   - Hard questions: pause the run + send a browser notification.
 *   - Stop: at the daily SAFE limit (15) — well under LinkedIn's ~30 throttle.
 *
 * Runs in the content-script main context, so it can drive the real page.
 */
import { sendMsg } from '../api/messages';
import { getProfile } from './profile';
import { getBanRisk, DAILY_SAFE } from './banmeter';
import { LinkedInAdapter } from '../adapters/linkedin';
import { runApplyLoop, findApplyContainer, sleep, toast } from './index';

const STATE_KEY = 'jobora_bulk_run';

export interface BulkState {
  active: boolean;
  applied: number;
  skipped: number;
  current: string;   // status line for the sidebar
  target: number;
}

const IDLE: BulkState = { active: false, applied: 0, skipped: 0, current: '', target: DAILY_SAFE };

export async function getBulkState(): Promise<BulkState> {
  const { [STATE_KEY]: s } = await chrome.storage.local.get(STATE_KEY);
  return { ...IDLE, ...(s as Partial<BulkState> | undefined) };
}
async function setState(patch: Partial<BulkState>): Promise<BulkState> {
  const next = { ...(await getBulkState()), ...patch };
  await chrome.storage.local.set({ [STATE_KEY]: next });
  return next;
}
function notify(title: string, message: string) {
  void sendMsg({ type: 'SHOW_NOTIFICATION', title, message });
}

/** Human-ish random delay (2–4.5s) so we don't look like a bot. */
const humanDelay = () => sleep(2000 + Math.random() * 2500);

/** Build the LinkedIn Easy-Apply search URL from the saved search. */
function searchUrl(query: string, location: string): string {
  const p = new URLSearchParams({ keywords: query, f_AL: 'true', sortBy: 'R' });
  if (location) p.set('location', location);
  return `https://www.linkedin.com/jobs/search/?${p.toString()}`;
}

/** The clickable job cards currently in the results list. */
function jobCards(): HTMLElement[] {
  return Array.from(
    document.querySelectorAll<HTMLElement>('li[data-occludable-job-id], .scaffold-layout__list-item'),
  ).filter(el => el.querySelector('a[href*="/jobs/view/"], a.job-card-container__link, a.job-card-list__title'));
}

function alreadyApplied(card: HTMLElement): boolean {
  return /applied/i.test(card.textContent || '');
}

/** Start a bulk run. Navigates to the saved search first if needed. */
export async function startBulk(): Promise<void> {
  const profile = await getProfile();
  if (!profile.autoSubmit) { toast('Turn on Auto-apply in the popup first.'); return; }

  const query = profile.searchQuery?.trim();
  await setState({ active: true, applied: 0, skipped: 0, target: DAILY_SAFE, current: 'Starting…' });

  // Navigate to the saved search if one is set and we're not already there.
  if (query && !location.href.includes(encodeURIComponent(query).slice(0, 8))) {
    location.href = searchUrl(query, profile.searchLocation || '');
    return;   // content script re-inits after load → resumeIfActive() continues
  }
  void runBulkLoop();
}

export async function stopBulk(): Promise<void> {
  await setState({ active: false, current: 'Stopped.' });
  toast('⏹ Auto-apply stopped.');
}

/** Called on content-script init: if a run was active, keep going after nav. */
export async function resumeBulkIfActive(): Promise<void> {
  const s = await getBulkState();
  if (s.active) { await sleep(2500); void runBulkLoop(); }
}

async function runBulkLoop(): Promise<void> {
  const profile = await getProfile();
  const adapter = new LinkedInAdapter();

  for (const card of jobCards()) {
    if (!(await getBulkState()).active) return;          // user hit Stop

    const risk = await getBanRisk();
    if (risk.count >= DAILY_SAFE) {
      await setState({ active: false, current: `Reached ${DAILY_SAFE}/day — stopping for safety.` });
      notify('Jobora — daily limit reached', `Applied to ${risk.count} today. Stopping to protect your account.`);
      return;
    }
    if (alreadyApplied(card)) continue;

    // Open the job.
    (card.querySelector('a[href*="/jobs/view/"], a.job-card-container__link, a.job-card-list__title') as HTMLElement)?.click();
    await humanDelay();

    // Score it.
    const job = adapter.extract();
    if (!job) { await bump('skipped', 'Job details not loaded'); continue; }
    const scoreRes = await sendMsg<{ match_score: number }>({ type: 'SCORE_JOB', job });
    const score = scoreRes.ok ? scoreRes.data.match_score : 0;
    if (score < profile.autoSubmitMinMatch) {
      await bump('skipped', `Skipped ${job.title} (${score}%)`);
      continue;
    }

    // Open Easy Apply.
    const easyBtn = Array.from(document.querySelectorAll<HTMLButtonElement>('button'))
      .find(b => /easy apply/i.test(b.textContent || '') && !b.disabled);
    if (!easyBtn) { await bump('skipped', `No Easy Apply for ${job.title}`); continue; }
    easyBtn.click();
    await sleep(1500);

    const container = findApplyContainer();
    if (!container) { await bump('skipped', `Couldn't open form for ${job.title}`); continue; }

    const status = await runApplyLoop(container);
    if (status === 'submitted') {
      await bump('applied', `✓ Applied: ${job.title} (${score}%)`);
      await sleep(2000);   // let the confirmation + ban meter register
    } else if (status === 'paused') {
      await setState({ active: false, current: `Paused — "${job.title}" needs your input.` });
      notify('Jobora — needs your answer', `"${job.title}" has a question I can't answer truthfully. Open LinkedIn to finish it, then restart.`);
      return;
    } else {
      await bump('skipped', `Couldn't finish ${job.title}`);
      // close the half-open modal
      (findApplyContainer()?.querySelector('button[aria-label*="Dismiss" i]') as HTMLElement)?.click();
      await sleep(800);
    }
    await humanDelay();
  }

  await setState({ active: false, current: 'Done — no more matching jobs in this list.' });
  notify('Jobora — run finished', `Applied to ${(await getBulkState()).applied} matching jobs.`);
}

async function bump(kind: 'applied' | 'skipped', line: string): Promise<void> {
  const s = await getBulkState();
  await setState({ [kind]: s[kind] + 1, current: line } as Partial<BulkState>);
  toast(`🚀 ${line}`);
}

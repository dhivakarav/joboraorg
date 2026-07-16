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
 *
 * IMPORTANT — stays in the split-view /jobs/search/ layout:
 *   Card links are Ember views. Clicking one BEFORE Ember hydrates falls through
 *   to a raw anchor navigation → the single-job /jobs/view/ page, whose DOM the
 *   adapter can't read. So we (a) wait for hydration before clicking, (b) verify
 *   each click switched the detail pane in-page (currentJobId matched), and
 *   (c) recover back to the list if a stray full navigation slips through.
 */
import { sendMsg } from '../api/messages';
import { getProfile, effectiveMinMatch } from './profile';
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

// ── DOM helpers ────────────────────────────────────────────────────────────────

const CARD_SEL = 'li[data-occludable-job-id], .scaffold-layout__list-item';
const CARD_LINK_SEL = 'a[href*="/jobs/view/"], a.job-card-container__link, a.job-card-list__title';
const DETAIL_TITLE_SEL = [
  '.job-details-jobs-unified-top-card__job-title h1',
  '.jobs-unified-top-card__job-title h1',
  '.scaffold-layout__detail h1',
];

/** The clickable job cards currently in the results list. */
function jobCards(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>(CARD_SEL))
    .filter(el => el.querySelector(CARD_LINK_SEL));
}

/** The LinkedIn job id for a card (used to verify in-page selection + re-find it). */
function cardJobId(card: HTMLElement): string {
  return (
    card.getAttribute('data-occludable-job-id') ||
    card.querySelector('[data-job-id]')?.getAttribute('data-job-id') ||
    ''
  );
}

/** The job id currently shown in the detail pane (?currentJobId=…). */
function currentJobId(): string {
  try {
    return new URLSearchParams(location.search).get('currentJobId') || '';
  } catch {
    return '';
  }
}

function onSearchPage(): boolean {
  return location.pathname.includes('/jobs/search/') || location.pathname.includes('/jobs/collections/');
}

function detailTitlePresent(): boolean {
  return DETAIL_TITLE_SEL.some(s => (document.querySelector(s)?.textContent || '').trim().length > 0);
}

function alreadyApplied(card: HTMLElement): boolean {
  return /\bapplied\b/i.test(card.textContent || '');
}

/** Poll until `pred` is true or `ms` elapses. Returns the final truthiness. */
async function waitFor(pred: () => boolean, ms = 8000, step = 250): Promise<boolean> {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    if (pred()) return true;
    await sleep(step);
  }
  return pred();
}

/** Scroll the results list to lazy-load more cards (LinkedIn virtualizes them). */
async function loadMoreCards(target = 25): Promise<void> {
  let prev = 0;
  for (let i = 0; i < 8; i++) {
    const cards = jobCards();
    if (cards.length >= target) break;
    if (cards.length === prev && i > 1) break;   // no new cards loading — stop
    prev = cards.length;
    cards[cards.length - 1]?.scrollIntoView({ block: 'end' });
    await sleep(700);
  }
  jobCards()[0]?.scrollIntoView({ block: 'center' });
  await sleep(400);
}

/** Bail out of the loop and re-load the saved search list (used after a stray nav). */
async function recoverToList(profile: { searchQuery?: string; searchLocation?: string }): Promise<void> {
  const q = profile.searchQuery?.trim();
  if (q) {
    await setState({ current: 'Recovering to results list…' });
    location.href = searchUrl(q, profile.searchLocation || '');   // resume() restarts after load
  } else {
    await setState({ active: false, current: 'Lost the results list — restart from a search.' });
  }
}

// ── Lifecycle ──────────────────────────────────────────────────────────────────

/** Start a bulk run. Navigates to the saved search first if needed. */
export async function startBulk(): Promise<void> {
  const profile = await getProfile();
  if (!profile.autoSubmit) { toast('Turn on Auto-apply in the popup first.'); return; }

  const query = profile.searchQuery?.trim();
  await setState({ active: true, applied: 0, skipped: 0, target: DAILY_SAFE, current: 'Starting…' });

  // Navigate to the saved search unless we're already on a results list page.
  if (query && !onSearchPage()) {
    location.href = searchUrl(query, profile.searchLocation || '');
    return;   // content script re-inits after load → resumeBulkIfActive() continues
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
  if (!s.active) return;
  // Wait for the results list to hydrate before touching anything.
  await waitFor(() => jobCards().length > 0, 12000);
  await sleep(1500);
  void runBulkLoop();
}

// ── Main loop ────────────────────────────────────────────────────────────────

async function runBulkLoop(): Promise<void> {
  const profile = await getProfile();
  const adapter = new LinkedInAdapter();

  // If a stray navigation left us on a single-job page, go back to the list.
  if (!onSearchPage()) { await recoverToList(profile); return; }

  // Wait for Ember to hydrate the list + detail pane. Clicking before this
  // causes raw anchor navigation to /jobs/view/ (unparseable single-job page).
  const ready = await waitFor(() => jobCards().length > 0 && detailTitlePresent(), 12000);
  if (!ready) {
    await setState({ active: false, current: 'Results list did not load — try again.' });
    return;
  }

  await loadMoreCards();

  // Snapshot the job ids up front; re-find each card by id each iteration
  // (LinkedIn recycles the <li> elements as you scroll).
  const jobIds = jobCards().map(cardJobId).filter(Boolean);
  if (!jobIds.length) {
    await setState({ active: false, current: 'No jobs found in this list.' });
    return;
  }

  for (const jobId of jobIds) {
    if (!(await getBulkState()).active) return;                    // user hit Stop

    const risk = await getBanRisk();
    if (risk.count >= DAILY_SAFE) {
      await setState({ active: false, current: `Reached ${DAILY_SAFE}/day — stopping for safety.` });
      notify('Jobora — daily limit reached', `Applied to ${risk.count} today. Stopping to protect your account.`);
      return;
    }

    // Re-find the card (it may have been recycled). Scroll it into view so its
    // Ember link is live before we click.
    let card = document.querySelector<HTMLElement>(`li[data-occludable-job-id="${jobId}"]`);
    if (!card) continue;
    card.scrollIntoView({ block: 'center' });
    await sleep(500);
    card = document.querySelector<HTMLElement>(`li[data-occludable-job-id="${jobId}"]`) || card;

    if (alreadyApplied(card)) { await bump('skipped', 'Already applied — skipping'); continue; }

    const link = card.querySelector(CARD_LINK_SEL) as HTMLElement | null;
    if (!link) continue;
    link.click();

    // Verify the detail pane switched to THIS job in-page. If a full navigation
    // to /jobs/view/ slipped through, recover to the list and let resume restart.
    await waitFor(() => currentJobId() === jobId, 6000);
    if (!onSearchPage()) { await recoverToList(profile); return; }
    await waitFor(detailTitlePresent, 6000);
    await humanDelay();

    // Score it.
    const job = adapter.extract();
    if (!job) { await bump('skipped', 'Job details not loaded'); continue; }
    const scoreRes = await sendMsg<{ match_score: number }>({ type: 'SCORE_JOB', job });
    const score = scoreRes.ok ? scoreRes.data.match_score : 0;
    if (score < effectiveMinMatch(profile)) {
      await bump('skipped', `Skipped ${job.title} (${score}%)`);
      continue;
    }

    // Open Easy Apply (scoped to the detail pane's apply button).
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
      await sleep(1500);
      dismissAnyModal();                 // close the post-apply confirmation
      await sleep(1000);
    } else if (status === 'paused') {
      await setState({ active: false, current: `Paused — "${job.title}" needs your input.` });
      notify('Jobora — needs your answer', `"${job.title}" has a question I can't answer truthfully. Open LinkedIn to finish it, then restart.`);
      return;
    } else {
      await bump('skipped', `Couldn't finish ${job.title}`);
      dismissAnyModal();                 // close the half-open modal
      await sleep(800);
    }
    await humanDelay();
  }

  const final = await getBulkState();
  await setState({ active: false, current: `Done — applied to ${final.applied}, skipped ${final.skipped}.` });
  notify('Jobora — run finished', `Applied to ${final.applied} matching jobs, skipped ${final.skipped}.`);
}

/** Close any open Easy-Apply or confirmation modal. */
function dismissAnyModal(): void {
  const btn = document.querySelector(
    '.artdeco-modal button[aria-label*="Dismiss" i], button[aria-label*="Dismiss" i]',
  ) as HTMLElement | null;
  btn?.click();
}

async function bump(kind: 'applied' | 'skipped', line: string): Promise<void> {
  const s = await getBulkState();
  await setState({ [kind]: s[kind] + 1, current: line } as Partial<BulkState>);
  toast(`🚀 ${line}`);
}

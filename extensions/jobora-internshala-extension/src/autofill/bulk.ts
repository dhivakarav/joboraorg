/**
 * Internshala bulk auto-apply walker.
 *
 * Internshala's apply flow is multi-page (full navigations), so this is a
 * page-reactive state machine: on every content-script load, resumeBulkIfActive()
 * looks at the current URL and does the next step:
 *
 *   /internships/…  (listing)     → collect detail links → go to the first
 *   /internship/detail/…          → score; if it passes, click "Apply now"
 *   /student/resume               → click "Proceed to application"
 *   /application/form/…           → fill (profile + resume-grounded AI) → Submit
 *   (post-submit confirmation)    → record applied → go to the next internship
 *
 * Honest guards: high-match only (unless bypass), stops at the daily safe limit,
 * and if a form has a question it can't answer truthfully the AI pass leaves it
 * blank → we DON'T submit; we blink + notify the user and stop.
 */
import { getProfile, effectiveMinMatch } from './profile';
import { getBanRisk, DAILY_SAFE } from './banmeter';
import { InternshalaAdapter } from '../adapters/internshala';
import { runAutofill } from './engine';
import { setNativeValue, isVisible, labelTextFor, selectOption, clickChoice } from './fill';
import { sendMsg } from '../api/messages';
import { sleep, toast, alertUser } from './index';

const STATE_KEY = 'jobora_ishala_run';

export interface BulkState {
  active: boolean;
  applied: number;
  skipped: number;
  current: string;
  target: number;
  queue: string[];   // internship detail URLs still to process
}

const IDLE: BulkState = { active: false, applied: 0, skipped: 0, current: '', target: DAILY_SAFE, queue: [] };

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
const humanDelay = () => sleep(1500 + Math.random() * 2000);

async function waitFor(pred: () => boolean, ms = 10000, step = 300): Promise<boolean> {
  const end = Date.now() + ms;
  while (Date.now() < end) { if (pred()) return true; await sleep(step); }
  return pred();
}

// ── Page-type helpers ──────────────────────────────────────────────────────────

const path = () => location.pathname;
const isListing = () => /\/internships(\/|$)/.test(path()) || /\/jobs(\/|$)/.test(path());
const isDetail  = () => /\/(internship|job)\/detail\//.test(path());
const isResumeGate = () => /\/student\/resume/.test(path());
const isForm    = () => /\/application\/form\//.test(path());

/** Detail links currently on a listing page. */
function listingLinks(): string[] {
  const cards = Array.from(document.querySelectorAll<HTMLElement>('.individual_internship[internshipid]'));
  const urls = cards
    .map(c => c.querySelector<HTMLAnchorElement>('a[href*="/internship/detail"], a[href*="/job/detail"]')?.href)
    .filter((u): u is string => !!u)
    .map(u => u.split('?')[0]);
  return [...new Set(urls)];
}

// ── Lifecycle ──────────────────────────────────────────────────────────────────

export async function startBulk(): Promise<void> {
  const profile = await getProfile();
  if (!profile.autoSubmit) { toast('Turn on Auto-apply first.'); return; }
  if (!isListing()) { toast('Open an Internshala internships list, then Start.'); return; }
  const queue = listingLinks();
  if (!queue.length) { toast('No internships found on this page.'); return; }
  await setState({ active: true, applied: 0, skipped: 0, target: DAILY_SAFE, queue, current: `Found ${queue.length} internships…` });
  await gotoNext();
}

export async function stopBulk(): Promise<void> {
  await setState({ active: false, current: 'Stopped.' });
  toast('⏹ Auto-apply stopped.');
}

/** Advance to the next queued internship detail page. */
async function gotoNext(): Promise<void> {
  const s = await getBulkState();
  if (!s.active) return;
  if (!s.queue.length) {
    await setState({ active: false, current: `Done — applied ${s.applied}, skipped ${s.skipped}.` });
    notify('Jobora — Internshala run finished', `Applied to ${s.applied}, skipped ${s.skipped}.`);
    return;
  }
  const [nextUrl, ...rest] = s.queue;
  await setState({ queue: rest, current: 'Opening next internship…' });
  location.href = nextUrl;   // resumeBulkIfActive() continues on load
}

/** Called on every content-script load — drives the next step for the page we're on. */
export async function resumeBulkIfActive(): Promise<void> {
  const s = await getBulkState();
  if (!s.active) return;
  await sleep(1200);

  const risk = await getBanRisk();
  if (risk.count >= DAILY_SAFE) {
    await setState({ active: false, current: `Reached ${DAILY_SAFE}/day — stopping.` });
    notify('Jobora — daily limit reached', `Applied to ${risk.count} today. Stopping to protect your account.`);
    return;
  }

  try {
    if (isDetail()) return void await onDetail();
    if (isResumeGate()) return void await onResumeGate();
    if (isForm()) return void await onForm();
    if (isListing()) {
      if (!s.queue.length) { const q = listingLinks(); if (q.length) await setState({ queue: q }); }
      return void await gotoNext();
    }
    // Post-submit confirmation / anything else → move on to the next internship.
    await gotoNext();
  } catch {
    await setState({ current: 'Hiccup — continuing…' });
    await gotoNext();
  }
}

// ── Per-page handlers ────────────────────────────────────────────────────────

async function onDetail(): Promise<void> {
  const profile = await getProfile();
  const adapter = new InternshalaAdapter();
  await waitFor(() => !!document.querySelector('.apply_now_button, .profile_on_detail_page'), 10000);

  // Already applied?
  if (document.querySelector('.applied_message, .application_success') ||
      /you have already applied/i.test(document.body.textContent || '')) {
    await bump('skipped', 'Already applied');
    return void await gotoNext();
  }

  const job = adapter.extract();
  if (job) {
    const res = await sendMsg<{ match_score: number }>({ type: 'SCORE_JOB', job });
    const score = res.ok ? res.data.match_score : 0;
    if (score < effectiveMinMatch(profile)) {
      await bump('skipped', `Skipped ${job.title} (${score}%)`);
      return void await gotoNext();
    }
    await setState({ current: `Applying: ${job.title} (${score}%)` });
  }

  const apply = document.querySelector<HTMLElement>('.apply_now_button');
  if (!apply) { await bump('skipped', 'No apply button'); return void await gotoNext(); }
  await humanDelay();
  apply.click();   // → resume gate or form
}

async function onResumeGate(): Promise<void> {
  const findProceed = () => Array.from(document.querySelectorAll<HTMLElement>('button, a, input[type="submit"]'))
    .find(b => /proceed to application/i.test(b.textContent || (b as HTMLInputElement).value || ''));
  await waitFor(() => !!findProceed(), 8000);
  const proceed = findProceed();
  if (!proceed) { await bump('skipped', 'Resume gate blocked'); return void await gotoNext(); }
  await humanDelay();
  proceed.click();   // → application form
}

async function onForm(): Promise<void> {
  const profile = await getProfile();
  const form = document.querySelector<HTMLElement>('form') || document.body;
  await waitFor(() => !!document.querySelector('#submit, input[type="submit"], form'), 8000);

  // 1) Availability radio → "Yes, available to join immediately" if none chosen.
  if (!document.querySelector('input[name="confirm_availability"]:checked')) {
    document.querySelector<HTMLInputElement>('input[name="confirm_availability"]')?.click();
  }

  // 2) Profile autofill (contact, standard questions).
  runAutofill(form, profile);

  // 3) AI pass — cover letter + any required blank the profile couldn't fill.
  await aiFillForm(form);
  await sleep(800);

  // 4) If a required field is still blank, DON'T submit — alert the user.
  if (hasBlankRequired(form)) {
    await setState({ active: false, current: 'Paused — a question needs your answer.' });
    notify('Jobora — needs your answer', 'An Internshala form has a question I can\'t answer truthfully. Finish it, then restart.');
    alertUser('Internshala form needs your answer');
    return;
  }

  const submit = document.querySelector<HTMLElement>('#submit') ||
    Array.from(document.querySelectorAll<HTMLElement>('button, input[type="submit"]'))
      .find(b => /^\s*submit\s*$/i.test(b.textContent || (b as HTMLInputElement).value || '')) || null;
  if (!submit) { await bump('skipped', 'No submit button'); return void await gotoNext(); }

  await humanDelay();
  submit.click();
  await bump('applied', 'Applied ✓');
  await sleep(2500);   // let the confirmation load
  await gotoNext();
}

// ── Form-fill helpers ────────────────────────────────────────────────────────

function hasBlankRequired(root: HTMLElement): boolean {
  const req = root.querySelectorAll<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>('[required], [aria-required="true"]');
  for (const el of req) {
    if (!isVisible(el) || el.disabled) continue;
    if (el instanceof HTMLSelectElement) { if (!el.value) return true; }
    else if ((el as HTMLInputElement).type === 'radio' || (el as HTMLInputElement).type === 'checkbox') {
      const name = el.getAttribute('name');
      if (name && !root.querySelector(`input[name="${CSS.escape(name)}"]:checked`)) return true;
    } else if (!el.value.trim()) return true;
  }
  return false;
}

async function aiFillForm(root: HTMLElement): Promise<void> {
  const title = (document.querySelector('h1, .heading_1')?.textContent || '').trim().slice(0, 80);
  const ask = async (label: string, fieldType: 'text' | 'choice' | 'number', options: string[]) => {
    const res = await sendMsg<{ answer: string }>({ type: 'ANSWER_FIELD', label, fieldType, options, jobTitle: title, jobCompany: '' });
    return res.ok ? (res.data.answer || '') : '';
  };
  // Cover-letter / text answers (fill textareas even if optional — a cover letter
  // helps; skip the availability textarea which is only for the "No" branch).
  const texts = Array.from(root.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>('input[type="text"], textarea'))
    .filter(el => isVisible(el) && !el.disabled && !el.value.trim() && (el as HTMLInputElement).name !== 'confirm_availability_textarea');
  for (const el of texts) {
    const required = (el as HTMLInputElement).required || el.getAttribute('aria-required') === 'true' || el.tagName === 'TEXTAREA';
    if (!required) continue;
    const label = labelTextFor(el) || (el as HTMLTextAreaElement).placeholder || 'Cover letter';
    const answer = await ask(label, (el as HTMLInputElement).type === 'number' ? 'number' : 'text', []);
    if (answer) setNativeValue(el, answer);
  }
  // Required selects.
  for (const sel of Array.from(root.querySelectorAll<HTMLSelectElement>('select'))) {
    if (!isVisible(sel) || sel.disabled || sel.value) continue;
    if (!(sel.required || sel.getAttribute('aria-required') === 'true')) continue;
    const options = Array.from(sel.options).map(o => o.text.trim()).filter(Boolean);
    const answer = await ask(labelTextFor(sel) || 'Select', 'choice', options);
    if (answer) selectOption(sel, answer);
  }
  // Employer question radio groups (not the availability one).
  const groups = new Set<Element>();
  root.querySelectorAll<HTMLInputElement>('input[type="radio"]').forEach(r => {
    const g = r.closest('.assessment_question, fieldset, .form_group') || r.parentElement?.parentElement;
    if (g) groups.add(g);
  });
  for (const g of groups) {
    if (g.querySelector('input[type="radio"]:checked')) continue;
    const first = g.querySelector<HTMLInputElement>('input[type="radio"]');
    if (!first || first.name === 'confirm_availability') continue;
    const options = Array.from(g.querySelectorAll<HTMLInputElement>('input[type="radio"]'))
      .map(r => (r.id ? g.querySelector(`label[for="${CSS.escape(r.id)}"]`)?.textContent : '') || r.value || '')
      .map(t => (t || '').trim()).filter(Boolean);
    const answer = await ask(labelTextFor(first) || 'Question', 'choice', options);
    if (answer) clickChoice(g, answer);
  }
}

async function bump(kind: 'applied' | 'skipped', line: string): Promise<void> {
  const s = await getBulkState();
  await setState({ [kind]: s[kind] + 1, current: line } as Partial<BulkState>);
  toast(`🚀 ${line}`);
}

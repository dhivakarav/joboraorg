/**
 * Autofill orchestration for the content script.
 *
 * Watches the page for a LinkedIn Easy Apply modal, injects a "⚡ Autofill"
 * button into it, and fills recognised fields from the user's profile — on
 * click, and (debounced) as multi-step forms reveal new fields. It NEVER clicks
 * Next or Submit: the user reviews and submits.
 *
 * Runs in the LinkedIn page context (not the Shadow DOM) so it can touch the
 * real form elements. Styling is inline to avoid depending on the page's CSS.
 */
import { sendMsg } from '../api/messages';
import type { JoBoraUser, ResumeProfile } from '../types/job';
import { getProfile, patchProfile, effectiveMinMatch, type AutofillProfile } from './profile';
import { runAutofill } from './engine';
import { recordApply, getBanRisk } from './banmeter';
import { setNativeValue, isVisible, labelTextFor } from './fill';
import { LinkedInAdapter } from '../adapters/linkedin';

const BTN_ID = 'jobora-autofill-btn';
const BRAND = '#2563EB';

/** Find a visible LinkedIn Easy Apply modal, if one is open. */
function findModal(): HTMLElement | null {
  const candidates = Array.from(
    document.querySelectorAll<HTMLElement>(
      '.jobs-easy-apply-modal, div[data-test-modal][role="dialog"], .artdeco-modal',
    ),
  );
  for (const el of candidates) {
    const heading = el.querySelector('h2, h1, [class*="modal__title"]')?.textContent ?? '';
    if (/apply to|easy apply|your application|contact info|additional questions/i.test(
      heading + ' ' + (el.textContent?.slice(0, 400) ?? ''),
    )) {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) return el;
    }
  }
  return null;
}

/**
 * On non-LinkedIn boards (Naukri, Indeed, Internshala, generic ATS) the
 * application isn't a modal — it's a form on the page. Return the most
 * application-like <form>: several inputs AND a contact field (email/phone).
 */
function findGenericForm(): HTMLElement | null {
  for (const f of Array.from(document.querySelectorAll<HTMLElement>('form'))) {
    if (!isVisible(f)) continue;
    const inputs = f.querySelectorAll(
      'input[type="text"],input[type="email"],input[type="tel"],input:not([type]),textarea,select',
    );
    const contact = f.querySelector(
      'input[type="email"],input[type="tel"],input[name*="email" i],input[name*="phone" i],input[name*="mobile" i]',
    );
    if (inputs.length >= 3 && contact) return f;
  }
  return null;
}

/** The container to autofill: LinkedIn modal, or a generic form elsewhere. */
export function findApplyContainer(): HTMLElement | null {
  const modal = findModal();
  if (modal) return modal;
  if (!location.hostname.endsWith('linkedin.com')) return findGenericForm();
  return null;
}

export function toast(msg: string): void {
  const t = document.createElement('div');
  t.textContent = msg;
  Object.assign(t.style, {
    position: 'fixed', bottom: '24px', left: '50%', transform: 'translateX(-50%)',
    background: '#0F172A', color: '#fff', padding: '10px 16px', borderRadius: '8px',
    fontSize: '13px', fontFamily: 'system-ui, sans-serif', zIndex: '2147483647',
    boxShadow: '0 8px 24px rgba(0,0,0,0.25)', pointerEvents: 'none',
  });
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2600);
}

async function doFill(modal: HTMLElement, announce: boolean): Promise<void> {
  const profile = await getProfile();
  const { filled, skipped } = runAutofill(modal, profile);
  if (announce) {
    if (filled.length) toast(`⚡ Jobora filled ${filled.length} field${filled.length > 1 ? 's' : ''}`
      + (skipped.length ? ` · ${skipped.length} need your review` : ''));
    else if (skipped.length) toast('Nothing to fill here — please answer the remaining fields.');
    else toast('No fillable fields found on this step.');
    // AI cover letter only on explicit click (costs an API call).
    void fillCoverLetters(modal);
  }
}

/**
 * Fill long "cover letter / why you / message" textareas with a tailored letter
 * from the backend (Groq via /jobs/cover-letter). Only runs on an explicit
 * Autofill click, only on clearly cover-letter-ish empty fields, and requires
 * the user to be signed in.
 */
const COVER_RE = /cover letter|why (should|would|do you)|why are you|motivat|message to|tell us|additional information|anything else|about yourself|note to/i;

function isCoverLetterField(ta: HTMLTextAreaElement): boolean {
  const label = labelTextFor(ta).toLowerCase();
  if (COVER_RE.test(label)) return true;
  // Big free-text box with no specific label → likely a cover letter.
  const maxlen = Number(ta.getAttribute('maxlength') || '0');
  return maxlen >= 300 || ta.rows >= 4;
}

async function fillCoverLetters(modal: HTMLElement): Promise<void> {
  const targets = Array.from(modal.querySelectorAll<HTMLTextAreaElement>('textarea'))
    .filter(ta => isVisible(ta) && !ta.disabled && !ta.readOnly && !ta.value.trim() && isCoverLetterField(ta));
  if (!targets.length) return;

  const job = new LinkedInAdapter().extract();
  if (!job) return;

  toast('✍️ Generating a tailored cover letter…');
  const res = await sendMsg<{ cover_letter: string; ai: boolean }>({ type: 'COVER_LETTER', job });
  if (!res.ok || !res.data.cover_letter) {
    toast('Cover letter unavailable — sign in to Jobora to enable it.');
    return;
  }
  for (const ta of targets) setNativeValue(ta, res.data.cover_letter);
  toast(`✍️ Cover letter filled${res.data.ai ? ' (AI)' : ''} — review before submitting.`);
}

// ── #4 Hybrid auto-apply (opt-in, gated by ban meter + match score) ───────────
export const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

function findBtn(container: HTMLElement, re: RegExp): HTMLButtonElement | null {
  for (const b of Array.from(container.querySelectorAll<HTMLButtonElement>('button'))) {
    if (b.disabled || !isVisible(b)) continue;
    const label = `${b.textContent ?? ''} ${b.getAttribute('aria-label') ?? ''}`.trim();
    if (re.test(label)) return b;
  }
  return null;
}

/** True if a visible required field is still empty — never auto-submit then. */
function hasUnfilledRequired(container: HTMLElement): boolean {
  const req = container.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>(
    '[required], [aria-required="true"]',
  );
  for (const el of req) {
    if (!isVisible(el) || el.disabled) continue;
    if (el instanceof HTMLSelectElement) {
      if (!el.value || /^(select|choose|--)/i.test(el.options[el.selectedIndex]?.text ?? '')) return true;
    } else if (el.type === 'radio' || el.type === 'checkbox') {
      const name = el.getAttribute('name');
      if (name && !container.querySelector(`input[name="${CSS.escape(name)}"]:checked`)) return true;
    } else if (!el.value.trim()) {
      return true;
    }
  }
  return false;
}

/**
 * Fill → advance → submit, but ONLY when: the daily ban budget isn't exhausted,
 * the job scores >= the user's threshold, and every required field got filled.
 * Bails safely (never submits a half-empty form) and hands back to the user.
 */
async function autoApply(container: HTMLElement): Promise<void> {
  const profile = await getProfile();
  const risk = await getBanRisk();
  if (risk.level === 'high') { toast(`⛔ ${risk.message}`); return; }

  // Match gate (LinkedIn only — that's where we can score the current job).
  const job = new LinkedInAdapter().extract();
  if (job) {
    const s = await sendMsg<{ match_score: number }>({ type: 'SCORE_JOB', job });
    const floor = effectiveMinMatch(profile);
    if (s.ok && s.data.match_score < floor) {
      toast(`Auto-apply skipped — ${s.data.match_score}% is below your ${floor}% threshold.`);
      return;
    }
    if (profile.matchBypass && s.ok) toast(`🔓 Bypass on — applying despite ${s.data.match_score}% match.`);
  }

  toast('▶ Auto-applying…');
  const status = await runApplyLoop(container);
  if (status === 'paused') toast('⏸ Auto-apply paused — a field needs your answer.');
  else if (status === 'stopped') toast('⏸ Auto-apply stopped — please finish manually.');
}

export type ApplyStatus = 'submitted' | 'paused' | 'stopped';

/**
 * Fill → advance → submit within an already-open apply form. Returns:
 *   submitted — clicked "Submit application"
 *   paused    — a required field it can't answer truthfully is empty
 *   stopped   — no Next/Submit found, or ran out of steps
 * Reused by the single-job button AND the bulk engine.
 */
export async function runApplyLoop(container: HTMLElement): Promise<ApplyStatus> {
  const profile = await getProfile();
  for (let step = 0; step < 8; step++) {
    runAutofill(container, profile);
    await fillCoverLetters(container);
    await sleep(700);
    const submit = findBtn(container, /submit application/i);
    if (submit) { submit.click(); return 'submitted'; }   // ban meter counts via detectSubmitted
    if (hasUnfilledRequired(container)) return 'paused';
    const next = findBtn(container, /continue to next|^next$|review your application|^review$/i);
    if (!next) return 'stopped';
    next.click();
    await sleep(900);
  }
  return 'stopped';
}

// Single persistent, fixed-position button (works for modal AND page forms).
let btnEl: HTMLButtonElement | null = null;
let autoSubmitOn = false;   // cached from the profile; controls button mode + label

function ensureButton(container: HTMLElement | null): void {
  if (!container) { if (btnEl) btnEl.style.display = 'none'; return; }
  if (!btnEl) {
    btnEl = document.createElement('button');
    btnEl.id = BTN_ID;
    btnEl.type = 'button';
    Object.assign(btnEl.style, {
      position: 'fixed', bottom: '20px', right: '20px', zIndex: '2147483646',
      color: '#fff', border: 'none', borderRadius: '22px',
      padding: '10px 16px', fontSize: '13px', fontWeight: '600', cursor: 'pointer',
      fontFamily: 'system-ui, sans-serif', boxShadow: '0 4px 14px rgba(37,99,235,0.4)',
    });
    document.body.appendChild(btnEl);
  }
  paintButton();
  btnEl.style.display = 'block';
  btnEl.onclick = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (autoSubmitOn) void autoApply(container);
    else void doFill(container, true);
  };
}

function paintButton(): void {
  if (!btnEl) return;
  btnEl.textContent = autoSubmitOn ? '▶ Auto-apply & submit' : '⚡ Autofill (Jobora)';
  btnEl.style.background = autoSubmitOn ? '#DC2626' : BRAND;   // red = it will submit
}

let debounce: number | undefined;

/** Start watching for application forms (LinkedIn modal or any board) to autofill. */
export function initAutofill(): void {
  void seedProfileFromAccount();
  void getProfile().then(p => { autoSubmitOn = p.autoSubmit; paintButton(); });
  chrome.storage.onChanged.addListener((c) => {
    if (c.jobora_autofill_profile) {
      void getProfile().then(p => { autoSubmitOn = p.autoSubmit; paintButton(); });
    }
  });

  // Throttle: LinkedIn's Easy Apply modal fires a storm of mutations. Coalesce
  // them into ONE run per animation frame so the heavy DOM scans below never
  // freeze the tab (this was a perf regression).
  let scheduled = false;
  const observer = new MutationObserver(() => {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      detectSubmitted();
      const container = findApplyContainer();
      ensureButton(container);
      if (!container) return;
      // Debounced auto-fill as steps reveal new fields (idempotent: skips filled).
      window.clearTimeout(debounce);
      debounce = window.setTimeout(() => void doFill(container, false), 500);
    });
  });
  observer.observe(document.body, { childList: true, subtree: true });
}

// ── Ban-risk: count a submit when LinkedIn confirms the application was sent ──
let lastSentAt = 0;
function detectSubmitted(): void {
  // Cheap, bounded scan: the confirmation is an <h2> ("Your application was
  // sent to X!"). Avoid expensive descendant selectors like `[class*=post-apply] *`.
  const els = document.querySelectorAll('h2, h3');
  let sent = false;
  for (const el of els) {
    if (/application was sent|your application was submitted/i.test(el.textContent || '')) {
      sent = true; break;
    }
  }
  if (!sent) return;
  const now = Date.now();
  if (now - lastSentAt < 5000) return;   // dedupe the burst of mutations
  lastSentAt = now;
  void recordApply().then(r => toast(`✅ Applied · ${r.message}`));
}

/**
 * Seed empty profile fields from the signed-in Jobora account + resume, so the
 * first application already has the user's real contact info and skills. Only
 * fills blanks — never overwrites what the user set in the popup.
 */
async function seedProfileFromAccount(): Promise<void> {
  const current = await getProfile();
  const patch: Partial<AutofillProfile> = {};

  if (!current.email || !current.firstName) {
    const me = await sendMsg<JoBoraUser>({ type: 'GET_ME' });
    if (me.ok) {
      const [first, ...rest] = (me.data.full_name || '').trim().split(/\s+/);
      if (!current.firstName && first) patch.firstName = first;
      if (!current.lastName && rest.length) patch.lastName = rest.join(' ');
      if (!current.email && me.data.email) patch.email = me.data.email;
      if (!current.phone && me.data.phone) patch.phone = me.data.phone;
      if (!current.currentTitle && me.data.job_title) patch.currentTitle = me.data.job_title;
      if ((!current.yearsExperience || current.yearsExperience === '1') && me.data.years_experience)
        patch.yearsExperience = String(me.data.years_experience);
    }
  }
  if (!current.skills.length) {
    const r = await sendMsg<ResumeProfile>({ type: 'GET_RESUME' });
    if (r.ok && r.data.parsed_skills?.length) patch.skills = r.data.parsed_skills;
  }
  if (Object.keys(patch).length) await patchProfile(patch);
}

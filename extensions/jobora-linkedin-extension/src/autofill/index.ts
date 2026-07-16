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
import { getProfile, patchProfile, type AutofillProfile } from './profile';
import { runAutofill } from './engine';

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

function toast(msg: string): void {
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
  }
}

function injectButton(modal: HTMLElement): void {
  if (modal.querySelector(`#${BTN_ID}`)) return;
  const btn = document.createElement('button');
  btn.id = BTN_ID;
  btn.type = 'button';
  btn.textContent = '⚡ Autofill (Jobora)';
  Object.assign(btn.style, {
    position: 'absolute', top: '14px', right: '56px', zIndex: '10',
    background: BRAND, color: '#fff', border: 'none', borderRadius: '20px',
    padding: '6px 14px', fontSize: '13px', fontWeight: '600', cursor: 'pointer',
    fontFamily: 'system-ui, sans-serif', boxShadow: '0 2px 8px rgba(37,99,235,0.35)',
  });
  btn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    void doFill(modal, true);
  });
  // The modal is position:relative in LinkedIn; ensure our absolute button anchors to it.
  if (getComputedStyle(modal).position === 'static') modal.style.position = 'relative';
  modal.appendChild(btn);
}

let debounce: number | undefined;

/** Start watching for Easy Apply modals and autofill them. */
export function initAutofill(): void {
  void seedProfileFromAccount();

  const observer = new MutationObserver(() => {
    const modal = findModal();
    if (!modal) return;
    injectButton(modal);
    // Debounced auto-fill as steps reveal new fields (idempotent: skips filled ones).
    window.clearTimeout(debounce);
    debounce = window.setTimeout(() => void doFill(modal, false), 500);
  });
  observer.observe(document.body, { childList: true, subtree: true });
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

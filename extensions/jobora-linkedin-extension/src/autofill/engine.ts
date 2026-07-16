/**
 * The autofill engine: given a form container (e.g. the LinkedIn Easy Apply
 * modal) and the user's profile, fill every field it recognises — deterministic,
 * label-driven, no LLM. Returns what it filled and what it skipped so the UI can
 * report it. NEVER submits.
 *
 * Design: match on the field's *visible label text*, not fragile CSS classes,
 * so it survives LinkedIn UI churn and works on generic ATS forms too.
 */
import type { AutofillProfile } from './profile';
import {
  setNativeValue, selectOption, clickChoice, labelTextFor, isVisible,
} from './fill';

export interface AutofillResult {
  filled: string[];   // labels we filled
  skipped: string[];  // labels we saw but couldn't confidently answer
}

const has = (label: string, ...needles: string[]) => {
  const l = label.toLowerCase();
  return needles.some(n => l.includes(n));
};

/** Text/number value for a labelled text field, or null to skip. */
function textValueFor(label: string, p: AutofillProfile): string | null {
  if (has(label, 'email')) return p.email || null;
  if (has(label, 'mobile', 'phone', 'contact number')) return p.phone || null;
  if (has(label, 'first name')) return p.firstName || null;
  if (has(label, 'last name', 'surname')) return p.lastName || null;
  if (has(label, 'full name') || label.toLowerCase() === 'name')
    return `${p.firstName} ${p.lastName}`.trim() || null;
  if (has(label, 'postal', 'zip', 'pin code', 'pincode')) return p.postalCode || null;
  if (has(label, 'city', 'location', 'current location')) return p.city || null;
  if (has(label, 'linkedin')) return p.linkedinUrl || null;
  if (has(label, 'notice period')) return p.noticePeriodDays || null;
  if (has(label, 'expected', 'ctc', 'salary', 'compensation', 'expected pay'))
    return p.expectedCtc || null;
  if (has(label, 'experience') && has(label, 'year'))
    return p.yearsExperience || null;
  if (has(label, 'how many years')) return p.yearsExperience || null;
  return null;
}

/** Resolve a Yes/No-style question to "Yes" or "No" from the profile. */
function yesNoFor(label: string, p: AutofillProfile): 'Yes' | 'No' {
  const yn = (b: boolean): 'Yes' | 'No' => (b ? 'Yes' : 'No');
  if (has(label, 'authorized', 'authorised', 'eligible to work', 'right to work'))
    return yn(p.workAuthorized);
  if (has(label, 'sponsor', 'visa'))
    return yn(p.requiresSponsorship);
  if (has(label, 'immediately', 'available to join', 'start date', 'can you start'))
    return yn(p.availableImmediately);
  if (has(label, 'bachelor', 'degree', 'graduat', 'completed the following'))
    return yn(p.hasBachelors);
  if (has(label, 'relocat'))
    return yn(p.willingToRelocate);
  if (has(label, 'agree', 'consent', 'privacy', 'terms', 'accurate'))
    return 'Yes';
  // "Have you used / worked with / deployed / built X?" — Yes if X is a real skill.
  if (has(label, 'have you', 'do you have', 'experience with', 'worked with', 'used', 'familiar')) {
    const hit = p.skills.some(s => s && label.toLowerCase().includes(s.toLowerCase()));
    if (hit) return 'Yes';
  }
  return p.defaultYesNo;
}

/** Fill the whole container. Only fills empty fields (never clobbers the user). */
export function runAutofill(container: Element, p: AutofillProfile): AutofillResult {
  const filled: string[] = [];
  const skipped: string[] = [];

  // ── Text / email / tel / number inputs + textareas ──
  const textEls = Array.from(
    container.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>(
      'input[type="text"], input[type="email"], input[type="tel"], input[type="number"], input:not([type]), textarea',
    ),
  );
  for (const el of textEls) {
    if (!isVisible(el) || el.disabled || el.readOnly) continue;
    if (el.value.trim()) continue;                 // don't overwrite prefilled
    const label = labelTextFor(el);
    if (!label) continue;
    const val = textValueFor(label, p);
    if (val != null) { setNativeValue(el, val); filled.push(label); }
    else skipped.push(label);
  }

  // ── Selects (dropdowns) ──
  for (const sel of Array.from(container.querySelectorAll<HTMLSelectElement>('select'))) {
    if (!isVisible(sel) || sel.disabled) continue;
    if (sel.value && !/^(select|choose|--)/i.test(sel.options[sel.selectedIndex]?.text ?? ''))
      continue;                                     // already answered
    const label = labelTextFor(sel);
    if (!label) continue;
    if (has(label, 'country')) {
      if (selectOption(sel, p.country)) { filled.push(label); continue; }
    }
    if (has(label, 'phone country code')) continue; // LinkedIn prefills this
    const ans = yesNoFor(label, p);
    if (selectOption(sel, ans)) filled.push(label);
    else skipped.push(label);
  }

  // ── Radio / checkbox groups (Yes / No) ──
  const groups = new Set<Element>();
  container.querySelectorAll<HTMLInputElement>('input[type="radio"]').forEach(r => {
    const group = r.closest('fieldset') || r.parentElement?.parentElement || r.parentElement;
    if (group) groups.add(group);
  });
  for (const group of groups) {
    const anyChecked = group.querySelector('input[type="radio"]:checked');
    if (anyChecked) continue;
    const label = labelTextFor(group.querySelector('input[type="radio"]')!);
    if (!label) continue;
    const ans = yesNoFor(label, p);
    if (clickChoice(group, ans)) filled.push(label);
    else skipped.push(label);
  }

  return { filled, skipped };
}

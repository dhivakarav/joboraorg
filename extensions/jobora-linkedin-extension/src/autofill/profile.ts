/**
 * The user's autofill profile — the single source of truth the filler reads.
 *
 * Stored in chrome.storage.local under `jobora_autofill_profile` and editable in
 * the popup. It can be seeded from the signed-in Jobora account (name/email/
 * phone) and parsed resume (skills), then extended with the answers ATS forms
 * commonly ask for (experience, notice period, work authorization, …).
 */

export interface AutofillProfile {
  // Identity / contact
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  city: string;
  country: string;
  postalCode: string;
  linkedinUrl: string;

  // Current/most-recent employment (for "Work experience" steps)
  currentTitle: string;
  currentCompany: string;

  // Common screening answers
  yearsExperience: string;        // e.g. "1"
  expectedCtc: string;            // e.g. "6" (LPA) — kept as string for text fields
  noticePeriodDays: string;       // e.g. "0"
  availableImmediately: boolean;  // "Can you start immediately?"
  hasBachelors: boolean;          // "Completed Bachelor's degree?"
  willingToRelocate: boolean;
  workAuthorized: boolean;        // "Authorized to work in <country>?"
  requiresSponsorship: boolean;   // "Do you require visa sponsorship?"

  /** Skills the candidate genuinely has — drives "Have you used X?" answers. */
  skills: string[];

  /** Fallback for unrecognised Yes/No questions. */
  defaultYesNo: 'Yes' | 'No';

  /** Auto-apply: when on, the ⚡ button fills AND submits — but only for jobs
   *  scoring >= autoSubmitMinMatch and while under the daily ban limit. */
  autoSubmit: boolean;
  autoSubmitMinMatch: number;

  /** Saved search the bulk "Start auto-apply" engine runs on LinkedIn. */
  searchQuery: string;
  searchLocation: string;
}

const KEY = 'jobora_autofill_profile';

export const EMPTY_PROFILE: AutofillProfile = {
  firstName: '', lastName: '', email: '', phone: '',
  city: '', country: '', postalCode: '', linkedinUrl: '',
  currentTitle: '', currentCompany: '',
  yearsExperience: '1', expectedCtc: '', noticePeriodDays: '0',
  availableImmediately: true, hasBachelors: true, willingToRelocate: true,
  workAuthorized: true, requiresSponsorship: false,
  skills: [],
  defaultYesNo: 'Yes',
  autoSubmit: false,
  autoSubmitMinMatch: 55,
  searchQuery: '',
  searchLocation: '',
};

export async function getProfile(): Promise<AutofillProfile> {
  const { [KEY]: stored } = await chrome.storage.local.get(KEY);
  return { ...EMPTY_PROFILE, ...(stored as Partial<AutofillProfile> | undefined) };
}

export async function setProfile(p: AutofillProfile): Promise<void> {
  await chrome.storage.local.set({ [KEY]: p });
}

export async function patchProfile(patch: Partial<AutofillProfile>): Promise<AutofillProfile> {
  const merged = { ...(await getProfile()), ...patch };
  await setProfile(merged);
  return merged;
}

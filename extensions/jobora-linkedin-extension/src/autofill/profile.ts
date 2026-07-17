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

  /** Password-gated override: when true, auto-apply ignores the match-score
   *  filter and applies to low-match jobs too. Unlocked via BYPASS_PASSWORD. */
  matchBypass: boolean;

  /** Saved search the bulk "Start auto-apply" engine runs on LinkedIn. */
  searchQuery: string;
  searchLocation: string;
}

const KEY = 'jobora_autofill_profile';

/**
 * Soft gate for the match-filter bypass. NOTE: this lives in the client bundle,
 * so it is NOT real security — it's a deliberate "are you sure" speed-bump so
 * the low-match override can't be flipped on by accident.
 */
export const BYPASS_PASSWORD = 'Jobora@321$';

/** The score threshold to actually enforce — 0 when the bypass is unlocked. */
export function effectiveMinMatch(p: AutofillProfile): number {
  return p.matchBypass ? 0 : p.autoSubmitMinMatch;
}

export const EMPTY_PROFILE: AutofillProfile = {
  firstName: '', lastName: '', email: '', phone: '',
  city: '', country: '', postalCode: '', linkedinUrl: '',
  currentTitle: '', currentCompany: '',
  yearsExperience: '2', expectedCtc: '', noticePeriodDays: '0',
  availableImmediately: true, hasBachelors: true, willingToRelocate: true,
  workAuthorized: true, requiresSponsorship: false,
  skills: [],
  defaultYesNo: 'Yes',
  autoSubmit: false,
  autoSubmitMinMatch: 55,
  matchBypass: false,
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

// Serialize writes so rapid patches (e.g. the popup saving several fields at
// once) don't read a stale copy and clobber each other. Each patch is queued
// behind the previous one and re-reads storage after it settles.
let writeQueue: Promise<AutofillProfile> = getProfile();

export async function patchProfile(patch: Partial<AutofillProfile>): Promise<AutofillProfile> {
  writeQueue = writeQueue.then(async () => {
    const merged = { ...(await getProfile()), ...patch };
    await setProfile(merged);
    return merged;
  });
  return writeQueue;
}

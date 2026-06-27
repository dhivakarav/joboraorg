/** Strongly-typed job extracted from a provider page (LinkedIn, Greenhouse, …). */
export interface ExtractedJob {
  /** Internal fingerprint — SHA-256 of `source|company|title|url` (first 32 chars). */
  fingerprint: string;
  /** Provider name, e.g. "LinkedIn" */
  source: string;
  /** Native job ID on the provider's platform */
  jobId: string;
  title: string;
  company: string;
  companyUrl: string;
  companyLogoUrl: string;
  location: string;
  /** Remote / On-site / Hybrid */
  workplaceType: string;
  /** Full-time / Part-time / Contract / Internship */
  employmentType: string;
  /** Entry level / Mid-Senior / Director / … */
  experienceLevel: string;
  salary: string;
  description: string;
  skills: string[];
  /** The actual job application URL */
  url: string;
  /** Whether LinkedIn shows an Easy Apply button */
  easyApply: boolean;
  recruiterName: string;
  recruiterTitle: string;
  postedAt: string;
  extractedAt: string;
}

/** Score + analysis returned by POST /api/jobs/score */
export interface JobScore {
  fingerprint: string;
  match_score: number;
  match_reasons: string[];
  missing_skills: string[];
  eligibility_score: number;
  eligibility_tier: string;
  eligible: boolean;
  eligibility_reason: string;
  already_saved: boolean;
}

/** Jobora user profile (mirrors UserOut schema) */
export interface JoBoraUser {
  id: number;
  full_name: string;
  email: string;
  phone: string;
  years_experience: number;
  job_title: string;
  seeker_type: string;
  status: string;
  is_admin: boolean;
}

/** Auth token pair stored in chrome.storage.local */
export interface StoredAuth {
  access_token: string;
  refresh_token: string;
  expires_at: number; // epoch ms
}

/** Parsed resume fields (mirrors ResumeOut) */
export interface ResumeProfile {
  parsed_name: string;
  parsed_email: string;
  parsed_skills: string[];
  parsed_experience: number;
  has_resume: boolean;
}

/** Application row created by POST /api/jobs/apply */
export interface SavedApplication {
  id: number;
  status: string;
  display_status: string;
  apply_url: string;
}

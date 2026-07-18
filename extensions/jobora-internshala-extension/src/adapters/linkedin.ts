/**
 * LinkedIn job extraction adapter — Phase 3 rewrite.
 *
 * Design principles:
 *   1. Container-first: find the job-detail container first, then query within it.
 *      This prevents false matches from other LinkedIn page sections.
 *   2. Many fallback selectors: LinkedIn's class names change frequently; each
 *      field has 6-10 selectors in priority order so the adapter keeps working
 *      after LinkedIn UI updates.
 *   3. Text-pattern fallback: when CSS selectors fail, pattern-match visible text.
 *   4. waitForReady(): MutationObserver-based promise — resolves when the job
 *      title is present in the DOM, times out after 12s with a soft error.
 *   5. No DOM mutations: only reads, never writes to the page.
 *
 * LinkedIn ToS compliance: reads only data already visible to the signed-in user
 * in their own browser session. No automated login, no headless scraping, no
 * mass data collection. Data is only stored when the user explicitly clicks
 * "Track Job".
 */
import type { IJobAdapter } from './base';
import type { ExtractedJob } from '../types/job';
import { fingerprintSync, cleanText } from './base';

// ── URL matching ──────────────────────────────────────────────────────────────

const LI_HOSTNAME = 'linkedin.com';

/** True when this URL is a LinkedIn jobs page where a specific job may appear. */
function isLinkedInUrl(url: string): boolean {
  try {
    return new URL(url).hostname.endsWith(LI_HOSTNAME);
  } catch {
    return false;
  }
}

/** True when a specific job could be visible (ID in path or currentJobId param). */
export function isLinkedInJobPage(url: string): boolean {
  if (!isLinkedInUrl(url)) return false;
  try {
    const { pathname, searchParams } = new URL(url);
    return (
      /\/jobs\/view\/\d+/.test(pathname) ||            // /jobs/view/123456/
      /\/jobs\/search\//.test(pathname) && !!searchParams.get('currentJobId') ||
      /\/jobs\/collections\//.test(pathname) && !!searchParams.get('currentJobId')
    );
  } catch {
    return false;
  }
}

/** Extract the LinkedIn job ID from any job URL pattern. */
export function extractJobId(url: string): string {
  const viewMatch = url.match(/\/jobs\/view\/(\d+)/);
  if (viewMatch) return viewMatch[1];
  try {
    return new URL(url).searchParams.get('currentJobId') ?? '';
  } catch {
    return '';
  }
}

// ── Container selectors (query the job-detail wrapper first) ──────────────────
// LinkedIn uses different containers for direct view vs search-panel view.

const CONTAINER_SELECTORS = [
  // Current 2026 unified top card wrapper (direct view + search panel)
  '.job-details-jobs-unified-top-card__container--two-pane',
  '.jobs-details__main-content',
  // Two-pane search layout
  '.jobs-search__job-details--wrapper',
  '.jobs-search-two-pane__detail-view',
  // Collection / recommendation panel
  '.scaffold-layout__detail',
  // Direct view full-page
  '.job-view-layout',
  // Older layout fallback
  '.jobs-unified-top-card',
  '.jobs-details',
  // Last resort — whole body
  'body',
];

function findContainer(): Element {
  for (const sel of CONTAINER_SELECTORS) {
    const el = document.querySelector(sel);
    if (el) return el;
  }
  return document.body;
}

// ── Field-level selectors (queried relative to the container) ─────────────────

const SEL_TITLE: string[] = [
  // Current unified top card
  '.job-details-jobs-unified-top-card__job-title h1',
  '.job-details-jobs-unified-top-card__job-title a',
  // Older top card
  '.jobs-unified-top-card__job-title h1',
  '.jobs-unified-top-card__job-title',
  // Generic — any h1 in the job panel
  'h1.job-title',
  'h1[class*="job-title"]',
  // Generic data-tracking attributes (more stable than class names)
  '[data-job-title]',
  // Last resort
  'h1',
];

const SEL_COMPANY: string[] = [
  '.job-details-jobs-unified-top-card__company-name a',
  '.job-details-jobs-unified-top-card__company-name',
  '.jobs-unified-top-card__company-name a',
  '.jobs-unified-top-card__company-name',
  '.topcard__org-name-link',
  'a[class*="company-name"]',
  '[data-company-name]',
];

const SEL_COMPANY_LINK: string[] = [
  '.job-details-jobs-unified-top-card__company-name a[href*="/company/"]',
  '.jobs-unified-top-card__company-name a[href*="/company/"]',
  '.topcard__org-name-link',
  'a[href*="/company/"][class*="company"]',
];

const SEL_LOGO: string[] = [
  // Unified top card logo
  '.job-details-jobs-unified-top-card__company-logo img',
  // Older variants
  '.jobs-unified-top-card__company-logo img',
  '.topcard__logo img',
  // Entity image (generic LinkedIn component)
  '.artdeco-entity-image img',
  'img[class*="company-logo"]',
  'img[class*="organization-logo"]',
];

// The "primary description" line usually contains "Location · Workplace · Posted"
const SEL_PRIMARY_DESCRIPTION: string[] = [
  '.job-details-jobs-unified-top-card__primary-description-container',
  '.jobs-unified-top-card__primary-description-container',
  '.topcard__flavor-row',
];

// Location is often the first bullet in the primary description
const SEL_LOCATION: string[] = [
  '.job-details-jobs-unified-top-card__bullet',
  '.jobs-unified-top-card__bullet',
  '.topcard__flavor--bullet',
  'span[class*="bullet"][class*="location"]',
  // Generic text "City, Country" format
  '.job-details-jobs-unified-top-card__primary-description .t-black--light',
];

const SEL_WORKPLACE_TYPE: string[] = [
  '.job-details-jobs-unified-top-card__workplace-type',
  '.jobs-unified-top-card__workplace-type',
  'span[class*="workplace-type"]',
];

// Insight list items contain employment type + experience level + company size
const SEL_INSIGHTS: string[] = [
  // Current 2026 — insight items are li elements
  'li.job-details-jobs-unified-top-card__job-insight',
  'li[class*="job-insight"]',
  // Older layout
  '.jobs-unified-top-card__job-insight',
  // Individual spans within insights
  '.jobs-unified-top-card__workplace-type',
  'span[class*="insight"]',
];

const SEL_SALARY: string[] = [
  '.job-details-jobs-unified-top-card__salary-info span',
  '.job-details-jobs-unified-top-card__salary-info',
  '.jobs-unified-top-card__salary-info',
  '.compensation__salary',
  'span[class*="salary"]',
  'span[class*="compensation"]',
  // Sometimes inside an insight item
  'li[class*="insight"] span[class*="salary"]',
];

const SEL_DESCRIPTION: string[] = [
  // 2026 unified card
  '.jobs-description__content .jobs-box__html-content',
  '.jobs-description-content__text',
  '.jobs-description .jobs-box__html-content',
  // The "See more" expandable container
  '.jobs-description__container',
  '.jobs-description',
  // Older
  '[class*="description-content"] .jobs-box__html-content',
  '[class*="description"] [class*="html-content"]',
];

// Skills shown in "How you match" or "Skills for this job"
const SEL_SKILLS: string[] = [
  // "How you match" skill pills
  '.job-details-how-you-match__skills-item-subtitle li',
  '.job-details-skill-match-status-list li',
  // Generic skill lists
  '.job-details-how-you-match ul li',
  '.jobs-description-skill-match__skill li',
  // Insight button (sometimes shows skill count)
  'button[class*="insight"] span',
  // Skills section
  '.job-details-skill-match-status-list__skill',
];

const SEL_APPLY_BUTTON: string[] = [
  // Top-card apply buttons (Easy Apply vs external)
  '.jobs-apply-button--top-card button',
  '.jobs-apply-button button',
  'button[class*="jobs-apply-button"]',
  // Older layout
  'button.jobs-apply-button',
];

const SEL_RECRUITER: string[] = [
  '.hirer-card__hirer-information',
  '.job-details-jobs-unified-top-card__hiring-manager',
  '[class*="hiring-manager"]',
  '[class*="hirer-card"]',
];

const SEL_POSTED_DATE: string[] = [
  // "Posted 3 days ago · 200 applicants"
  '.job-details-jobs-unified-top-card__primary-description-without-tagline',
  '.jobs-unified-top-card__posted-date',
  'span[class*="posted-date"]',
  'span[class*="time-badge"]',
  'time[class*="posted"]',
];

// ── Extraction helpers ────────────────────────────────────────────────────────

function qText(root: Element | Document, selectors: string[]): string {
  for (const sel of selectors) {
    const el = root.querySelector(sel);
    const text = cleanText(el);
    if (text) return text;
  }
  return '';
}

function qEl(root: Element | Document, selectors: string[]): Element | null {
  for (const sel of selectors) {
    const el = root.querySelector(sel);
    if (el) return el;
  }
  return null;
}

function qAllText(root: Element | Document, selectors: string[]): string[] {
  for (const sel of selectors) {
    const els = Array.from(root.querySelectorAll(sel));
    const texts = els.map(el => cleanText(el)).filter(t => t.length > 0 && t.length < 80);
    if (texts.length) return texts;
  }
  return [];
}

/**
 * Parse employment type, experience level, and workplace type from insight spans.
 * LinkedIn concatenates multiple insight items into a single string like:
 *   "Full-time · Mid-Senior level · 1,001-5,000 employees · Technology"
 */
function parseInsights(container: Element): {
  employmentType: string;
  experienceLevel: string;
  workplaceType: string;
} {
  const EMPLOYMENT_TYPES = ['Full-time', 'Part-time', 'Contract', 'Temporary',
    'Internship', 'Volunteer', 'Other'] as const;
  const EXPERIENCE_LEVELS = ['Internship', 'Entry level', 'Associate',
    'Mid-Senior level', 'Director', 'Executive'] as const;
  const WORKPLACE_TYPES = ['Remote', 'Hybrid', 'On-site'] as const;

  let employmentType = '';
  let experienceLevel = '';
  let workplaceType = '';

  // Collect ALL text from insight elements, split on ·
  const parts: string[] = [];
  for (const sel of SEL_INSIGHTS) {
    const els = Array.from(container.querySelectorAll(sel));
    if (els.length) {
      for (const el of els) {
        const raw = cleanText(el);
        parts.push(...raw.split('·').map(p => p.trim()));
      }
      break;
    }
  }
  // Also check standalone workplace type selector
  const wtEl = qEl(container, SEL_WORKPLACE_TYPE);
  if (wtEl) parts.push(cleanText(wtEl));

  for (const part of parts) {
    const low = part.toLowerCase();
    if (!employmentType) {
      const found = EMPLOYMENT_TYPES.find(t => low.includes(t.toLowerCase()));
      if (found) employmentType = found;
    }
    if (!experienceLevel) {
      const found = EXPERIENCE_LEVELS.find(l => low.includes(l.toLowerCase()));
      if (found) experienceLevel = found;
    }
    if (!workplaceType) {
      const found = WORKPLACE_TYPES.find(w => low === w.toLowerCase() || low.includes(` ${w.toLowerCase()}`));
      if (found) workplaceType = found;
    }
  }

  return { employmentType, experienceLevel, workplaceType };
}

/**
 * Extract location from the primary description line.
 * The line typically reads: "Bangalore, India · Hybrid · 3 days ago · 45 applicants"
 */
function parseLocation(container: Element): string {
  // Try the specific bullet selector first
  const bullet = qEl(container, SEL_LOCATION);
  if (bullet) return cleanText(bullet).split('·')[0].trim();

  // Fallback: parse the primary description container
  const primary = qEl(container, SEL_PRIMARY_DESCRIPTION);
  if (primary) {
    const raw = cleanText(primary);
    // Take everything up to the first occurrence of " · "
    return raw.split('·')[0].trim();
  }

  return '';
}

/**
 * Extract the posted date.
 * Returns relative text like "3 days ago", "1 week ago", "Just now".
 */
function parsePostedDate(container: Element): string {
  const el = qEl(container, SEL_POSTED_DATE);
  if (!el) return '';
  const text = cleanText(el);
  // Primary description may contain "City · Hybrid · 3 days ago · 200 applicants"
  // Extract only the time part
  const timePart = text.split('·').find(p => /\d+\s+(hour|day|week|month|year)s?\s+ago/i.test(p) || /just\s+now/i.test(p));
  return timePart ? timePart.trim() : '';
}

/**
 * Extract full job description as clean text, preserving paragraph breaks.
 * LinkedIn often hides the lower half behind a "Show more" button — extract
 * the full HTML content regardless of visual state.
 */
function parseDescription(container: Element): string {
  for (const sel of SEL_DESCRIPTION) {
    const el = container.querySelector(sel);
    if (!el) continue;
    // Convert block elements to newlines for readability
    const clone = el.cloneNode(true) as Element;
    clone.querySelectorAll('br').forEach(br => br.replaceWith('\n'));
    clone.querySelectorAll('p, div, li, h1, h2, h3, h4').forEach(block => {
      block.insertAdjacentText('afterend', '\n');
    });
    const text = (clone.textContent ?? '').replace(/[ \t]+/g, ' ').replace(/\n{3,}/g, '\n\n').trim();
    if (text.length > 50) return text;
  }
  return '';
}

/**
 * Extract recruiter / hiring manager name and title.
 */
function parseRecruiter(container: Element): { name: string; title: string } {
  const block = qEl(container, SEL_RECRUITER);
  if (!block) return { name: '', title: '' };
  // Name is typically in an anchor or the first strong/span
  const nameEl = block.querySelector('a, .hirer-card__hirer-name, strong, [class*="name"]');
  const titleEl = block.querySelector('.hirer-card__hirer-job-title, [class*="title"], [class*="position"]');
  return {
    name:  cleanText(nameEl),
    title: cleanText(titleEl),
  };
}

/**
 * True when this is an Easy Apply button (not an external link).
 */
function parseEasyApply(container: Element): boolean {
  for (const sel of SEL_APPLY_BUTTON) {
    const btn = container.querySelector(sel) as HTMLButtonElement | null;
    if (!btn) continue;
    const text = (btn.textContent ?? '').toLowerCase();
    if (text.includes('easy apply')) return true;
    if (text.includes('apply') && !text.includes('external') && !text.includes('site'))
      return false; // external apply
  }
  return false;
}

// ── MutationObserver-based readiness check ────────────────────────────────────

const TITLE_READY_SELECTORS = [
  '.job-details-jobs-unified-top-card__job-title h1',
  '.jobs-unified-top-card__job-title h1',
  'h1[class*="job-title"]',
  '.job-view-layout h1',
  '.scaffold-layout__detail h1',
];

function isTitlePresent(): boolean {
  return TITLE_READY_SELECTORS.some(sel => {
    const el = document.querySelector(sel);
    return el && (el.textContent ?? '').trim().length > 0;
  });
}

/**
 * Returns a promise that resolves when the job title appears in the DOM,
 * or rejects with a timeout error after `maxWaitMs` milliseconds.
 */
export function waitForJobReady(maxWaitMs = 12_000): Promise<void> {
  if (isTitlePresent()) return Promise.resolve();

  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      observer.disconnect();
      reject(new Error('Timed out waiting for job details to load'));
    }, maxWaitMs);

    const observer = new MutationObserver(() => {
      if (isTitlePresent()) {
        clearTimeout(timer);
        observer.disconnect();
        resolve();
      }
    });

    observer.observe(document.body, { childList: true, subtree: true });
  });
}

// ── Adapter ───────────────────────────────────────────────────────────────────

export class LinkedInAdapter implements IJobAdapter {
  readonly name = 'LinkedIn';

  matches(url: string): boolean {
    return isLinkedInUrl(url);
  }

  isJobPage(url: string): boolean {
    return isLinkedInJobPage(url);
  }

  /**
   * Synchronously extract a job from the current DOM.
   * Returns null when the page is not ready (title not yet rendered).
   * Call `waitForJobReady()` first to ensure the DOM is settled.
   */
  extract(): ExtractedJob | null {
    const pageUrl = window.location.href;
    if (!this.isJobPage(pageUrl)) return null;
    if (!isTitlePresent()) return null;

    const container = findContainer();

    const title = qText(container, SEL_TITLE);
    if (!title) return null;

    const company = qText(container, SEL_COMPANY);

    const companyLinkEl = qEl(container, SEL_COMPANY_LINK) as HTMLAnchorElement | null;
    const companyUrl = companyLinkEl?.href ?? '';

    const logoEl = qEl(container, SEL_LOGO) as HTMLImageElement | null;
    const companyLogoUrl = logoEl?.src ?? '';

    const jobLocation  = parseLocation(container);
    const { employmentType, experienceLevel, workplaceType } = parseInsights(container);
    const salary      = qText(container, SEL_SALARY);
    const description = parseDescription(container);
    const skills      = qAllText(container, SEL_SKILLS).slice(0, 25);
    const easyApply   = parseEasyApply(container);
    const { name: recruiterName, title: recruiterTitle } = parseRecruiter(container);
    const postedAt    = parsePostedDate(container);
    const jobId       = extractJobId(pageUrl);

    // Canonical URL: strip query params (stable, dedup-friendly)
    const cleanUrl = (() => {
      try {
        const u = new URL(pageUrl);
        // For /jobs/view/ID/ keep the path; for search/collections keep currentJobId
        if (/\/jobs\/view\/\d+/.test(u.pathname)) {
          return `${u.origin}${u.pathname}`.replace(/\/$/, '');
        }
        const jobIdParam = u.searchParams.get('currentJobId') ?? '';
        return `${u.origin}${u.pathname}?currentJobId=${jobIdParam}`;
      } catch {
        return pageUrl.split('?')[0];
      }
    })();

    return {
      fingerprint: fingerprintSync('LinkedIn', company, title, cleanUrl),
      source: 'LinkedIn',
      jobId,
      title,
      company,
      companyUrl,
      companyLogoUrl,
      location: jobLocation,
      workplaceType,
      employmentType,
      experienceLevel,
      salary,
      description,          // full text — truncated only at API call time
      skills,
      url: cleanUrl,
      easyApply,
      recruiterName,
      recruiterTitle,
      postedAt,
      extractedAt: new Date().toISOString(),
    };
  }
}

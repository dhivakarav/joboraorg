/**
 * LinkedIn job extraction adapter.
 *
 * LinkedIn is a single-page app — DOM selectors change over time. We use
 * multiple fallback selectors per field so the adapter degrades gracefully
 * rather than breaking completely when LinkedIn ships a UI change.
 *
 * LinkedIn ToS: Jobora ONLY reads data already visible to the authenticated
 * user in their browser — no automated login, no scraping at scale, no storing
 * of data beyond what the user explicitly saves to their Jobora account.
 */
import type { IJobAdapter } from './base';
import type { ExtractedJob } from '../types/job';
import { fingerprintSync, cleanText } from './base';

const LI_HOST = 'www.linkedin.com';

// ── Selector lists (first match wins) ─────────────────────────────────────────

const SEL_TITLE = [
  '.job-details-jobs-unified-top-card__job-title h1',
  '.jobs-unified-top-card__job-title h1',
  'h1.t-24',
  'h1[class*="job-title"]',
  'h1',
];

const SEL_COMPANY = [
  '.job-details-jobs-unified-top-card__company-name a',
  '.job-details-jobs-unified-top-card__company-name',
  '.jobs-unified-top-card__company-name a',
  '.jobs-unified-top-card__company-name',
  'a[class*="company-name"]',
];

const SEL_COMPANY_LINK = [
  '.job-details-jobs-unified-top-card__company-name a',
  '.jobs-unified-top-card__company-name a',
];

const SEL_LOCATION = [
  '.job-details-jobs-unified-top-card__bullet',
  '.jobs-unified-top-card__bullet',
  '.jobs-unified-top-card__primary-description-container .t-black--light',
  'span[class*="bullet"]',
];

const SEL_DESCRIPTION = [
  '.jobs-description__content .jobs-box__html-content',
  '.jobs-description-content__text',
  '.jobs-description .jobs-box__html-content',
  '[class*="description-content"]',
  '.jobs-description',
];

const SEL_EASY_APPLY = [
  '.jobs-apply-button--top-card',
  '.jobs-apply-button',
  'button[class*="easy-apply"]',
];

const SEL_SKILLS = [
  '.job-details-how-you-match__skills-item-subtitle li',
  '.jobs-unified-top-card__job-insight-text-button span',
  '.job-details-skill-match-status-list li',
];

const SEL_SALARY = [
  '.job-details-jobs-unified-top-card__salary-info span',
  '.jobs-unified-top-card__salary-info',
  'span[class*="salary"]',
];

const SEL_LOGO = [
  '.job-details-jobs-unified-top-card__company-logo img',
  '.artdeco-entity-image img',
  'img[class*="company-logo"]',
];

const SEL_INSIGHTS = [
  '.job-details-jobs-unified-top-card__job-insight span',
  '.jobs-unified-top-card__job-insight span',
  'li.job-details-jobs-unified-top-card__job-insight span',
];

// ── Helpers ────────────────────────────────────────────────────────────────────

function firstMatch(doc: Document, selectors: string[]): Element | null {
  for (const sel of selectors) {
    const el = doc.querySelector(sel);
    if (el) return el;
  }
  return null;
}

function firstMatchText(doc: Document, selectors: string[]): string {
  return cleanText(firstMatch(doc, selectors));
}

function allText(doc: Document, selectors: string[]): string[] {
  for (const sel of selectors) {
    const els = Array.from(doc.querySelectorAll(sel));
    const texts = els.map(el => cleanText(el)).filter(Boolean);
    if (texts.length) return texts;
  }
  return [];
}

/** Extract LinkedIn job ID from the current URL. */
function extractJobId(url: string): string {
  // /jobs/view/4123456789/  or  ?currentJobId=4123456789
  const viewMatch = url.match(/\/jobs\/view\/(\d+)/);
  if (viewMatch) return viewMatch[1];
  const paramMatch = url.match(/[?&]currentJobId=(\d+)/);
  if (paramMatch) return paramMatch[1];
  return '';
}

/**
 * Parse employment type and experience level from the insight badges.
 * LinkedIn renders these as text like "Full-time · Mid-Senior level"
 * or "Internship · Entry level".
 */
function parseInsights(doc: Document): { employmentType: string; experienceLevel: string; workplaceType: string } {
  const spans = allText(doc, SEL_INSIGHTS);

  const EMPLOYMENT_TYPES = ['Full-time', 'Part-time', 'Contract', 'Temporary', 'Internship', 'Volunteer', 'Other'];
  const EXPERIENCE_LEVELS = ['Internship', 'Entry level', 'Associate', 'Mid-Senior level', 'Director', 'Executive'];
  const WORKPLACE_TYPES = ['Remote', 'Hybrid', 'On-site'];

  let employmentType = '';
  let experienceLevel = '';
  let workplaceType = '';

  for (const span of spans) {
    if (!employmentType) {
      const found = EMPLOYMENT_TYPES.find(t => span.toLowerCase().includes(t.toLowerCase()));
      if (found) employmentType = found;
    }
    if (!experienceLevel) {
      const found = EXPERIENCE_LEVELS.find(l => span.toLowerCase().includes(l.toLowerCase()));
      if (found) experienceLevel = found;
    }
    if (!workplaceType) {
      const found = WORKPLACE_TYPES.find(w => span.toLowerCase().includes(w.toLowerCase()));
      if (found) workplaceType = found;
    }
  }

  return { employmentType, experienceLevel, workplaceType };
}

// ── Adapter ────────────────────────────────────────────────────────────────────

export class LinkedInAdapter implements IJobAdapter {
  readonly name = 'LinkedIn';

  matches(url: string): boolean {
    try {
      return new URL(url).hostname.includes(LI_HOST);
    } catch {
      return false;
    }
  }

  isJobPage(url: string): boolean {
    return this.matches(url) && /\/jobs\/(view|search|collections)\//.test(url);
  }

  extract(): ExtractedJob | null {
    const doc = document;
    const pageUrl = window.location.href;

    if (!this.isJobPage(pageUrl)) return null;

    const title = firstMatchText(doc, SEL_TITLE);
    if (!title) return null;  // page not ready yet

    const company = firstMatchText(doc, SEL_COMPANY);
    const companyEl = firstMatch(doc, SEL_COMPANY_LINK);
    const companyUrl = companyEl instanceof HTMLAnchorElement
      ? (companyEl.href || '')
      : '';

    const logoEl = firstMatch(doc, SEL_LOGO);
    const companyLogoUrl = logoEl instanceof HTMLImageElement ? (logoEl.src || '') : '';

    // Location: first bullet may contain "City, State · Remote · Full-time"
    const locationRaw = firstMatchText(doc, SEL_LOCATION);
    // Split off workplace type that LinkedIn sometimes appends to location
    const jobLocation = locationRaw.split('·')[0].trim();

    const descEl = firstMatch(doc, SEL_DESCRIPTION);
    const description = descEl ? (descEl.textContent ?? '').replace(/\s+/g, ' ').trim() : '';

    const salary = firstMatchText(doc, SEL_SALARY);

    const easyApplyEl = firstMatch(doc, SEL_EASY_APPLY);
    const easyApply = easyApplyEl
      ? easyApplyEl.textContent?.toLowerCase().includes('easy apply') ?? false
      : false;

    const skills = allText(doc, SEL_SKILLS).slice(0, 20);

    const { employmentType, experienceLevel, workplaceType } = parseInsights(doc);

    const jobId = extractJobId(pageUrl);

    // Recruiter info (not always present)
    const recruiterEl = doc.querySelector('.hirer-card__hirer-information');
    const recruiterName = cleanText(recruiterEl?.querySelector('.ember-view') ?? null);
    const recruiterTitle = cleanText(recruiterEl?.querySelector('.hirer-card__hirer-job-title') ?? null);

    // Canonical apply URL: clean query params for a stable fingerprint
    const cleanUrl = pageUrl.split('?')[0].replace(/\/$/, '');

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
      description: description.slice(0, 3000), // cap at 3000 chars
      skills,
      url: cleanUrl,
      easyApply,
      recruiterName,
      recruiterTitle,
      postedAt: '',
      extractedAt: new Date().toISOString(),
    };
  }
}

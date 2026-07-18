/**
 * Internshala job/internship extraction adapter.
 *
 * Works on internship & job DETAIL pages (internshala.com/internship/detail/…
 * and /job/detail/…). The listing pages use `.individual_internship[internshipid]`
 * cards which the bulk engine walks; this adapter reads the open detail page.
 *
 * Only reads data already visible to the signed-in user — no scraping at scale.
 */
import type { IJobAdapter } from './base';
import type { ExtractedJob } from '../types/job';
import { fingerprintSync, cleanText } from './base';

function isInternshalaUrl(url: string): boolean {
  try { return new URL(url).hostname.endsWith('internshala.com'); } catch { return false; }
}

export function isInternshalaJobPage(url: string): boolean {
  if (!isInternshalaUrl(url)) return false;
  try {
    const { pathname } = new URL(url);
    return /\/(internship|job)\/detail\//.test(pathname);
  } catch { return false; }
}

function qText(selectors: string[]): string {
  for (const sel of selectors) {
    const el = document.querySelector(sel);
    const t = cleanText(el);
    if (t) return t;
  }
  return '';
}

const SEL_TITLE = ['.profile_on_detail_page', '.heading_4_5.profile', 'h1.heading_1', 'h1'];
const SEL_COMPANY = ['.company_name a', '.company_name', '.heading_6.company_name', '.company-name'];
const SEL_LOCATION = ['#location_names', '.location_names', '.location_link', '.item_body.location_names'];
const SEL_STIPEND = ['.stipend', '.stipend_container .stipend', '[class*="stipend"]'];
const SEL_DESC = ['.internship_details', '.about_internship', '.text-container', '.detail_view'];

/** Skills — Internshala shows them as `.round_tabs`. Filter out obvious perks. */
function parseSkills(): string[] {
  const PERKS = /certificate|letter of recommendation|flexible|job offer|5 days|informal dress|free snacks|pre placement/i;
  const heading = Array.from(document.querySelectorAll('.section_heading, .heading_5, h3, h4'))
    .find(h => /skills required/i.test(h.textContent || ''));
  let tabs: Element[] = [];
  if (heading?.nextElementSibling) tabs = Array.from(heading.nextElementSibling.querySelectorAll('.round_tabs'));
  if (!tabs.length) tabs = Array.from(document.querySelectorAll('#skillContainer .round_tabs, .skills_container .round_tabs'));
  return tabs.map(t => cleanText(t)).filter(s => s && !PERKS.test(s)).slice(0, 15);
}

export class InternshalaAdapter implements IJobAdapter {
  readonly name = 'Internshala';

  matches(url: string): boolean { return isInternshalaUrl(url); }
  isJobPage(url: string): boolean { return isInternshalaJobPage(url); }

  extract(): ExtractedJob | null {
    const pageUrl = window.location.href;
    if (!this.isJobPage(pageUrl)) return null;

    const title = qText(SEL_TITLE).replace(/\s*-\s*(internship|job).*$/i, '').trim();
    if (!title) return null;

    // Company: strip a trailing badge word (NGO / Actively hiring) if present.
    const company = qText(SEL_COMPANY).replace(/\b(NGO|Actively hiring)\b/gi, '').trim();
    const location = qText(SEL_LOCATION);
    const salary = qText(SEL_STIPEND);
    const description = qText(SEL_DESC);
    const skills = parseSkills();

    const logoEl = document.querySelector<HTMLImageElement>('.internship_logo img, .company_logo img');
    const cleanUrl = pageUrl.split('?')[0];
    const isWfh = /work from home/i.test(location);

    return {
      fingerprint: fingerprintSync('Internshala', company, title, cleanUrl),
      source: 'Internshala',
      jobId: (cleanUrl.match(/(\d+)\/?$/)?.[1]) || '',
      title,
      company,
      companyUrl: '',
      companyLogoUrl: logoEl?.src ?? '',
      location: location || 'India',
      workplaceType: isWfh ? 'Remote' : '',
      employmentType: 'Internship',
      experienceLevel: 'Internship',
      salary,
      description,
      skills,
      url: cleanUrl,
      easyApply: true,               // Internshala apply is always on-platform
      recruiterName: '',
      recruiterTitle: '',
      postedAt: qText(['.posted_by_container .status', '.posted_by_container']),
      extractedAt: new Date().toISOString(),
    };
  }
}

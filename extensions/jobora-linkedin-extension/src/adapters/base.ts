import type { ExtractedJob } from '../types/job';

/**
 * Every provider adapter must implement this interface.
 * Adding a new provider (Indeed, Greenhouse, Workday, Naukri …) only requires:
 *   1. Implementing IJobAdapter
 *   2. Registering in registry.ts
 */
export interface IJobAdapter {
  /** Human-readable provider name, e.g. "LinkedIn" */
  readonly name: string;

  /** Returns true if the current URL belongs to this provider. */
  matches(url: string): boolean;

  /**
   * Returns true if the current URL is a SPECIFIC job detail page
   * (not a search results list or homepage).
   */
  isJobPage(url: string): boolean;

  /**
   * Extract the job from the current page DOM.
   * Returns null when the page is not ready or no job is visible.
   */
  extract(): ExtractedJob | null;
}

/** SHA-256 fingerprint (first 32 hex chars) matching the backend's logic. */
export async function fingerprint(source: string, company: string, title: string, url: string): Promise<string> {
  const basis = `${source}|${company}|${title}|${url}`.toLowerCase();
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(basis));
  return Array.from(new Uint8Array(buf))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('')
    .slice(0, 32);
}

/** Synchronous fingerprint approximation (XOR fold — not cryptographic, just unique enough for dedup). */
export function fingerprintSync(source: string, company: string, title: string, url: string): string {
  const basis = `${source}|${company}|${title}|${url}`.toLowerCase();
  let h = 0;
  for (let i = 0; i < basis.length; i++) {
    h = (Math.imul(31, h) + basis.charCodeAt(i)) | 0;
  }
  return Math.abs(h).toString(16).padStart(8, '0').repeat(4).slice(0, 32);
}

/** Safely query a selector; returns trimmed text or empty string. */
export function text(root: Document | Element, selector: string): string {
  return (root.querySelector(selector)?.textContent ?? '').trim();
}

/** Try multiple selectors and return the first non-empty match. */
export function firstText(root: Document | Element, ...selectors: string[]): string {
  for (const sel of selectors) {
    const t = text(root, sel);
    if (t) return t;
  }
  return '';
}

/** Extract visible text from an element, collapsing whitespace. */
export function cleanText(el: Element | null): string {
  if (!el) return '';
  return el.textContent?.replace(/\s+/g, ' ').trim() ?? '';
}

/**
 * Workday job board adapter — STUB (Phase 3+).
 *
 * Workday postings live on `<company>.wd<N>.myworkdayjobs.com/…`.
 * Workday uses a headless React frontend backed by a stable REST API
 * (`/wday/cxs/<company>/<posting>/jobs/<id>`) — the best extraction
 * strategy is to fetch that API directly rather than scraping the DOM.
 */
import type { IJobAdapter } from './base';
import type { ExtractedJob } from '../types/job';

export class WorkdayAdapter implements IJobAdapter {
  readonly name = 'Workday';

  matches(url: string): boolean {
    return /\.myworkdayjobs\.com/.test(url);
  }

  isJobPage(url: string): boolean {
    return this.matches(url) && url.includes('/job/');
  }

  extract(): ExtractedJob | null {
    // TODO: implement in Phase 3 using the Workday REST API
    return null;
  }
}

/**
 * Lever job board adapter — STUB (Phase 3+).
 *
 * Lever postings live on `jobs.lever.co/<company>/<job-id>`.
 * Lever renders job data in both HTML and as a JSON blob in a
 * `<script id="__NEXT_DATA__">` tag, making extraction straightforward.
 */
import type { IJobAdapter } from './base';
import type { ExtractedJob } from '../types/job';

export class LeverAdapter implements IJobAdapter {
  readonly name = 'Lever';

  matches(url: string): boolean {
    return url.includes('jobs.lever.co');
  }

  isJobPage(url: string): boolean {
    // /apply suffix = form page, not a job description page
    return this.matches(url) && !url.endsWith('/apply');
  }

  extract(): ExtractedJob | null {
    // TODO: implement in Phase 3 using __NEXT_DATA__ JSON parsing
    return null;
  }
}

/**
 * Greenhouse job board adapter — STUB (Phase 3+).
 *
 * Greenhouse boards live on `boards.greenhouse.io/<company>/jobs/<id>` or
 * custom company domains. The extraction logic will read from Greenhouse's
 * structured JSON-LD data (`<script type="application/ld+json">`) which is
 * stable and well-documented — much more reliable than CSS selectors.
 */
import type { IJobAdapter } from './base';
import type { ExtractedJob } from '../types/job';

export class GreenhouseAdapter implements IJobAdapter {
  readonly name = 'Greenhouse';

  matches(url: string): boolean {
    return url.includes('boards.greenhouse.io') || url.includes('job_app?for=');
  }

  isJobPage(url: string): boolean {
    return this.matches(url) && /\/jobs\/\d+/.test(url);
  }

  extract(): ExtractedJob | null {
    // TODO: implement in Phase 3 using JSON-LD <script> parsing
    return null;
  }
}

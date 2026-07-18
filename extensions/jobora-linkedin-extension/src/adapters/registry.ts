/**
 * Adapter registry — maps URLs to the correct provider adapter.
 *
 * To add a new provider in future phases:
 *   1. Implement IJobAdapter in a new file
 *   2. Add an instance to `ALL_ADAPTERS` below
 *   That's it — no other file needs changing.
 */
import type { IJobAdapter } from './base';
import { LinkedInAdapter } from './linkedin';
import { InternshalaAdapter } from './internshala';
import { GreenhouseAdapter } from './greenhouse';
import { LeverAdapter } from './lever';
import { WorkdayAdapter } from './workday';

const ALL_ADAPTERS: IJobAdapter[] = [
  new LinkedInAdapter(),
  new InternshalaAdapter(),
  new GreenhouseAdapter(),
  new LeverAdapter(),
  new WorkdayAdapter(),
];

/** Returns the adapter for the given URL, or null if no adapter matches. */
export function adapterFor(url: string): IJobAdapter | null {
  return ALL_ADAPTERS.find(a => a.matches(url)) ?? null;
}

/** Returns true if any adapter considers this URL a job page. */
export function isJobPage(url: string): boolean {
  return ALL_ADAPTERS.some(a => a.isJobPage(url));
}

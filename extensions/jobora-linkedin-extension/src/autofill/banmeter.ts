/**
 * Ban-risk meter.
 *
 * LinkedIn (and every board) flags accounts that apply too fast/too much. This
 * tracks how many applications were submitted today and reports a risk level so
 * the UI can warn the user BEFORE their account gets restricted — and so the
 * (future) auto-apply engine can throttle itself.
 *
 * Counts a submit when LinkedIn shows its "Your application was sent" confirmation.
 */

const KEY = 'jobora_apply_log';

// Conservative daily ceilings (well under where LinkedIn starts flagging).
export const DAILY_SAFE = 15;
export const DAILY_LIMIT = 25;

export type RiskLevel = 'safe' | 'caution' | 'high';

export interface BanRisk {
  count: number;      // applications submitted today
  safe: number;       // green threshold
  limit: number;      // hard ceiling
  level: RiskLevel;
  message: string;
}

interface LogEntry { date: string; count: number }

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

async function read(): Promise<LogEntry> {
  const { [KEY]: v } = await chrome.storage.local.get(KEY);
  const entry = v as LogEntry | undefined;
  if (!entry || entry.date !== today()) return { date: today(), count: 0 };
  return entry;
}

/** Record one submitted application (idempotency is the caller's job). */
export async function recordApply(): Promise<BanRisk> {
  const entry = await read();
  entry.count += 1;
  await chrome.storage.local.set({ [KEY]: entry });
  return risk(entry.count);
}

export async function getBanRisk(): Promise<BanRisk> {
  return risk((await read()).count);
}

function risk(count: number): BanRisk {
  let level: RiskLevel;
  let message: string;
  if (count >= DAILY_LIMIT) {
    level = 'high';
    message = `${count}/${DAILY_LIMIT} today — STOP. High ban risk; try again tomorrow.`;
  } else if (count >= DAILY_SAFE) {
    level = 'caution';
    message = `${count}/${DAILY_LIMIT} today — slow down; you're near the safe limit.`;
  } else {
    level = 'safe';
    message = `${count}/${DAILY_SAFE} today — safe to keep applying.`;
  }
  return { count, safe: DAILY_SAFE, limit: DAILY_LIMIT, level, message };
}

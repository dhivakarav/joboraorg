import { test as base, expect } from "@playwright/test";
import fs from "fs";

// ---- config (override via env) ----
export const API_URL = process.env.API_URL || "http://localhost:8000";
export const SMOKE_EMAIL = process.env.SMOKE_EMAIL || "smoke.user@example.com";
export const SMOKE_PASSWORD = process.env.SMOKE_PASSWORD || "SmokeTest123";
export const ADMIN_EMAIL = process.env.JOBORA_ADMIN_EMAIL || "admin@jobara.io";
export const ADMIN_PASSWORD = process.env.JOBORA_ADMIN_PASSWORD || "JobaraDev!2026";

const ART = "e2e/.artifacts";
const ERR = `${ART}/errors.json`;
export const ORIGIN = process.env.E2E_BASE_URL || "http://localhost:5173";
export const SMOKE_STATE = `${ART}/smoke-state.json`;
export const ADMIN_STATE = `${ART}/admin-state.json`;

// Console noise that is not a real error.
const BENIGN_CONSOLE = [/favicon/i, /Download the React DevTools/i, /\[vite\]/i];
// 4xx statuses that are expected app behaviour, not breakage.
const EXPECTED_4XX = new Set([401, 403]); // pre-auth /auth/me, guarded routes

// Extends `page` with global capture of console errors, uncaught exceptions, and
// failed network requests. Records them per-test for the report and FAILS the
// test (soft) if any of the three required-zero categories is non-empty.
export const test = base.extend({
  page: async ({ page }, use, testInfo) => {
    const consoleErrors = [], networkFailures = [], pageErrors = [], warn4xx = [];

    page.on("console", (m) => {
      if (m.type() !== "error") return;
      const t = m.text();
      if (!BENIGN_CONSOLE.some((r) => r.test(t))) consoleErrors.push(t);
    });
    page.on("pageerror", (e) => pageErrors.push(String(e)));
    page.on("requestfailed", (r) => {
      const u = r.url();
      const err = r.failure()?.errorText || "failed";
      // ERR_ABORTED = request cancelled by navigation/unmount (not a failure).
      // Only same-API network failures matter; external assets (fonts) are ignored.
      if (/ERR_ABORTED/i.test(err)) return;
      if (!u.includes("/api/")) return;
      networkFailures.push(`${r.method()} ${u} — ${err}`);
    });
    page.on("response", (r) => {
      const u = r.url();
      if (!u.includes("/api/")) return;
      const s = r.status();
      if (s >= 500) networkFailures.push(`${s} ${r.request().method()} ${u}`);
      else if (s >= 400 && !EXPECTED_4XX.has(s)) warn4xx.push(`${s} ${r.request().method()} ${u}`);
    });

    await use(page);

    fs.mkdirSync(ART, { recursive: true });
    let all = {};
    try { all = JSON.parse(fs.readFileSync(ERR, "utf8")); } catch { /* fresh */ }
    all[testInfo.title] = { consoleErrors, networkFailures, pageErrors, warn4xx };
    fs.writeFileSync(ERR, JSON.stringify(all, null, 2));

    // Required-zero categories — soft so all three are reported before failing.
    expect.soft(pageErrors, `uncaught exceptions on "${testInfo.title}"`).toEqual([]);
    expect.soft(consoleErrors, `console errors on "${testInfo.title}"`).toEqual([]);
    expect.soft(networkFailures, `failed API/network requests on "${testInfo.title}"`).toEqual([]);
  },
});

export { expect };

// ---- helpers ----
export async function login(page, email, pwd, expectUrl) {
  await page.goto("/login");
  await page.locator("input[type=email]").fill(email);
  await page.locator("input[type=password]").fill(pwd);
  await page.locator("form button").click();
  // A successful login always redirects off /login.
  await page.waitForURL((u) => !u.pathname.endsWith("/login"), { timeout: 15000 });
  if (expectUrl) await page.waitForURL(`**${expectUrl}`, { timeout: 15000 });
}

export async function shot(page, name) {
  fs.mkdirSync("e2e/screenshots", { recursive: true });
  await page.screenshot({ path: `e2e/screenshots/${name}.png`, fullPage: true });
}

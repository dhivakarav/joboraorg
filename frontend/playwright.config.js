import { defineConfig, devices } from "@playwright/test";

const BASE = process.env.E2E_BASE_URL || "http://localhost:5173";

// Smoke-test config. Serial (workers:1) keeps the run deterministic and under the
// login rate limit. The Vite dev server (which proxies /api → :8000) is started
// automatically; the BACKEND must be running separately on :8000.
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  workers: 1,
  retries: 0,
  reporter: [
    ["list"],
    ["json", { outputFile: "e2e/.artifacts/results.json" }],
    ["html", { outputFolder: "e2e/.artifacts/html", open: "never" }],
    ["./e2e/md-reporter.js"],
  ],
  globalSetup: "./e2e/global-setup.js",
  use: {
    baseURL: BASE,
    viewport: { width: 1280, height: 900 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    actionTimeout: 15_000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run dev",
    url: BASE,
    reuseExistingServer: true,
    timeout: 60_000,
  },
});

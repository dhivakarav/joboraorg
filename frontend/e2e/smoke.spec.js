import { test, expect, login, shot,
  SMOKE_EMAIL, SMOKE_PASSWORD, SMOKE_STATE, ADMIN_STATE } from "./support.js";

// Every test runs through the error-capturing `page` fixture, which fails on any
// console error, uncaught exception, or failed API/network request. Execution is
// serialized via workers:1. Auth is reused via storageState (seeded in global
// setup) so the suite logs in only in the dedicated login test — no rate limiting.

// ---------------- Anonymous flows ----------------
test.describe("auth", () => {
  // 1. Signup — register form reaches the pending screen.
  test("1. Signup", async ({ page }) => {
    const email = `smoke+${Date.now()}@example.com`;
    await page.goto("/register");
    await page.locator("form input").first().fill("New Smoke User");
    await page.locator("input[type=email]").fill(email);
    await page.locator("input[type=password]").fill("SmokeTest123");
    await page.locator("form button").click();
    await page.waitForURL("**/pending", { timeout: 15000 });
    await shot(page, "01-signup-pending");
  });

  // 2. Login — the one real interactive login; lands on the dashboard.
  test("2. Login", async ({ page }) => {
    await login(page, SMOKE_EMAIL, SMOKE_PASSWORD, "/app/dashboard");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    await shot(page, "02-dashboard");
  });
});

// ---------------- Authenticated (smoke user) ----------------
test.describe("user", () => {
  test.use({ storageState: SMOKE_STATE });

  // 3 & 4. Resume upload + parsing.
  test("3+4. Resume upload & parsing", async ({ page }) => {
    await page.goto("/app/resume");
    await page.locator("input[type=file]").setInputFiles("e2e/fixtures/resume.pdf");
    await expect(page.getByText(/uploaded|parsed|smoke@example\.com/i).first()).toBeVisible({ timeout: 15000 });
    await shot(page, "03-resume");
  });

  // 5 & 6. Find Jobs + internship filter.
  test("5+6. Find Jobs + internship filter", async ({ page }) => {
    await page.goto("/app/jobs");
    await expect(page.getByRole("heading", { name: "Find Jobs" })).toBeVisible();
    await page.waitForLoadState("networkidle");
    await expect(page.getByText("Internships & New Grad only")).toBeVisible();
    await page.locator('input[type="checkbox"]').first().click(); // flip the hard filter
    await page.waitForLoadState("networkidle");
    await shot(page, "05-find-jobs");
  });

  // 7. Dashboard statistics.
  test("7. Dashboard statistics", async ({ page }) => {
    await page.goto("/app/dashboard");
    await expect(page.getByText(/Verified Submitted|Tracked|Total/).first()).toBeVisible();
    await shot(page, "07-dashboard-stats");
  });

  // 8. Activity Log.
  test("8. Activity Log", async ({ page }) => {
    await page.goto("/app/activity");
    await expect(page.getByRole("heading", { name: "Activity Log" })).toBeVisible();
    await page.waitForLoadState("networkidle");
    await shot(page, "08-activity-log");
  });

  // 9. Verification Center.
  test("9. Verification Center", async ({ page }) => {
    await page.goto("/app/verification");
    await expect(page.getByRole("heading", { name: "Verification Center" })).toBeVisible();
    await page.waitForLoadState("networkidle");
    await shot(page, "09-verification-center");
  });

  // 11. Greenhouse → opens the real-submit wizard (per-app confirm). Best-effort.
  test("11. Greenhouse submit wizard", async ({ page, context }) => {
    await page.goto("/app/jobs");
    await page.waitForLoadState("networkidle");
    // A Greenhouse card opens the submit wizard; a non-Greenhouse one tracks directly.
    const ghCard = page.locator(".card-elevated", { hasText: "Greenhouse" })
      .filter({ has: page.getByRole("button", { name: "Track & Apply" }) }).first();
    if (await ghCard.count() > 0) {
      await ghCard.getByRole("button", { name: "Track & Apply" }).click();
      await expect(page.getByRole("heading", { name: /Submit application/ })).toBeVisible({ timeout: 10000 });
      await shot(page, "11-greenhouse-wizard");
      await page.keyboard.press("Escape").catch(() => {});
      return;
    }
    // Fallback: a generic Track & Apply card still tracks directly.
    const btn = page.getByRole("button", { name: "Track & Apply" }).first();
    if (await btn.count() === 0) {
      test.info().annotations.push({ type: "note", description: "No Track & Apply listing in live results" });
      await shot(page, "11-track-apply-none");
      return;
    }
    const popupP = context.waitForEvent("page").catch(() => null);
    await btn.click();
    const popup = await popupP;
    if (popup) await popup.close();
    await expect(page.getByText("✓ Tracked").first()).toBeVisible({ timeout: 10000 });
    await shot(page, "11-track-apply");
  });

  // 12. Lever Assisted Apply (best-effort).
  test("12. Lever Assisted Apply", async ({ page }) => {
    await page.goto("/app/jobs");
    await page.waitForLoadState("networkidle");
    const card = page.locator(".card-elevated", { hasText: "Lever" })
      .filter({ has: page.getByRole("button", { name: "Assisted Apply" }) }).first();
    if (await card.count() === 0) {
      test.info().annotations.push({ type: "note", description: "No Lever Assisted-Apply listing in live results — skipped interaction" });
      await shot(page, "12-lever-none");
      return;
    }
    await card.getByRole("button", { name: "Assisted Apply" }).click();
    await expect(page.getByText(/Lever · Assisted|Assisted Apply/).first()).toBeVisible();
    await shot(page, "12-lever-assisted");
  });

  // 13. Ashby Assisted Apply (best-effort).
  test("13. Ashby Assisted Apply", async ({ page }) => {
    await page.goto("/app/jobs");
    await page.waitForLoadState("networkidle");
    const card = page.locator(".card-elevated", { hasText: "Ashby" })
      .filter({ has: page.getByRole("button", { name: "Assisted Apply" }) }).first();
    if (await card.count() === 0) {
      test.info().annotations.push({ type: "note", description: "No Ashby Assisted-Apply listing in live results — skipped interaction" });
      await shot(page, "13-ashby-none");
      return;
    }
    await card.getByRole("button", { name: "Assisted Apply" }).click();
    await expect(page.getByText(/Ashby · Assisted|Assisted Apply/).first()).toBeVisible();
    await shot(page, "13-ashby-assisted");
  });

  // 14. Logout.
  test("14. Logout", async ({ page }) => {
    await page.goto("/app/dashboard");
    await page.getByRole("button", { name: /log out/i }).first().click();
    await page.waitForURL("**/login", { timeout: 10000 });
    await shot(page, "14-logout");
  });

  // 15. Mobile responsiveness (drawer nav).
  test("15. Mobile responsiveness", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/app/dashboard");
    await expect(page.getByRole("button", { name: "Open menu" })).toBeVisible();
    await page.getByRole("button", { name: "Open menu" }).click();
    await expect(page.getByRole("link", { name: "Find Jobs" })).toBeVisible();
    await shot(page, "15-mobile-drawer");
  });
});

// ---------------- Admin ----------------
test.describe("admin", () => {
  test.use({ storageState: ADMIN_STATE });

  // 10. Admin Operations.
  test("10. Admin Operations", async ({ page }) => {
    await page.goto("/admin/operations");
    await expect(page.getByRole("heading", { name: "Operations" })).toBeVisible();
    await page.waitForLoadState("networkidle");
    for (const t of ["Metrics", "Feedback & Bugs", "Invites"]) {
      await expect(page.getByRole("button", { name: t })).toBeVisible();
    }
    await page.getByRole("button", { name: "Invites" }).click();
    await page.waitForLoadState("networkidle");
    await shot(page, "10-admin-operations");
  });
});

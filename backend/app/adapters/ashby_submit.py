"""Ashby SUBMIT pipeline (Phase G3) — React-SPA aware.

Clicks Ashby's "Submit Application", then proves the outcome **by polling DOM
state** — because Ashby renders its success panel *in place with no navigation*
(the URL never changes). It detects:
  - an in-app confirmation panel (success markers and/or an `application-success`
    container) + an optional reference number, OR
  - an in-app reCAPTCHA challenge / validation error.

Status is "Applied" ONLY when a confirmation panel is detected. reCAPTCHA,
validation errors, or an ambiguous result are recorded as FAILED/CAPTCHA with
evidence — never a false success.

It reuses the *already-verified* Greenhouse detectors (success/failure markers,
reference patterns) by importing them — Greenhouse and Lever code are NOT
modified. Only the SPA polling + Ashby selectors are new here.

Performs the click only against the controlled mock; it does NOT write to the DB.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

# Reuse Greenhouse's verified detectors (read-only import; Greenhouse unchanged).
from .greenhouse_submit import FAILURE_MARKERS, REF_PATTERNS, SUCCESS_MARKERS

log = logging.getLogger("jobara.ashby.submit")

# Ashby in-app success container markers (DOM-state, not URL).
SUCCESS_CONTAINERS = (
    "[class*='application-form-success']",
    ".application-success",
    "[class*='submitted']",
)
ASHBY_SUCCESS_MARKERS = SUCCESS_MARKERS + [
    r"application submitted",
    r"your application has been submitted",
    r"successfully submitted",
]
ASHBY_SUBMIT_SELECTORS = (
    "button:has-text('Submit Application')",
    "#submit-app",
    "button[type='submit']",
)
POLL_MS = 700
POLL_ROUNDS = 18          # ~12.6s total to allow SPA re-render


@dataclass
class SubmitResult:
    form_url: str
    submit_clicked: bool = False
    confirmation_detected: bool = False
    detected_via: str = ""            # "dom-state(container)" / "dom-state(text)"
    status: str = "Failed"            # "Applied" only if confirmed
    application_id: Optional[str] = None
    confirmation_url: str = ""        # for SPA this stays == form_url (no nav)
    url_changed: bool = False
    screenshot_path: str = ""
    html_snapshot_path: str = ""
    platform_response: str = ""
    failure_reason: str = ""
    steps: list = field(default_factory=list)

    def step(self, m): self.steps.append(m); log.info(m)


async def submit_application(form_url: str, fill: Callable, evidence_dir: str,
                             tag: str = "submit") -> SubmitResult:
    from playwright.async_api import async_playwright

    res = SubmitResult(form_url=form_url)
    Path(evidence_dir).mkdir(parents=True, exist_ok=True)
    res.step(f"=== Ashby G3 submit start (SPA): {form_url} ===")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 1400})
        page = await ctx.new_page()
        try:
            await page.goto(form_url, wait_until="domcontentloaded", timeout=35000)
            await page.wait_for_selector(
                "#_systemfield_name, button:has-text('Submit Application')", timeout=20000)
            res.step("SPA form loaded")

            await fill(page)
            res.step("form filled (caller)")
            start_url = page.url

            clicked = False
            for sel in ASHBY_SUBMIT_SELECTORS:
                if await page.locator(sel).count():
                    res.step(f"clicking submit: {sel}")
                    try:
                        await page.locator(sel).first.click()
                        clicked = True
                        break
                    except Exception as e:
                        res.step(f"click {sel} failed: {e}")
            res.submit_clicked = clicked
            if not clicked:
                res.failure_reason = "Submit control not found"
                await _evidence(page, res, evidence_dir, tag)
                return res

            # --- POLL DOM STATE: Ashby re-renders in place, no navigation ---
            outcome = None  # ("success"|"captcha"|"failed", reason)
            for _ in range(POLL_ROUNDS):
                await page.wait_for_timeout(POLL_MS)
                body = (await page.inner_text("body")) if await page.locator("body").count() else ""
                low = body.lower()

                # failure first — must never read as success
                hit_fail = None
                for pat, reason in FAILURE_MARKERS:
                    if re.search(pat, low):
                        hit_fail = reason
                        break
                if hit_fail:
                    outcome = ("captcha" if "CAPTCHA" in hit_fail else "failed", hit_fail)
                    break

                # success: an in-app container OR success text
                container = False
                for csel in SUCCESS_CONTAINERS:
                    if await page.locator(csel).count() > 0:
                        container = True
                        break
                if container or any(re.search(m, low) for m in ASHBY_SUCCESS_MARKERS):
                    res.detected_via = "dom-state(container)" if container else "dom-state(text)"
                    outcome = ("success", "")
                    break

            res.confirmation_url = page.url
            res.url_changed = page.url != start_url
            title = await page.title()
            body = (await page.inner_text("body")) if await page.locator("body").count() else ""
            res.platform_response = f"TITLE: {title}\nURL: {page.url}\nURL_CHANGED: {res.url_changed}\nBODY:\n{body[:700]}"

            if not outcome:
                res.status = "Failed"
                res.failure_reason = "No confirmation panel rendered after submit (ambiguous)"
                res.step("No SPA confirmation detected — recording as FAILED (no false success)")
            elif outcome[0] == "captcha":
                res.status = "CAPTCHA Required"
                res.failure_reason = outcome[1]
                res.step(f"FAILURE detected (SPA): {outcome[1]}")
            elif outcome[0] == "failed":
                res.status = "Failed"
                res.failure_reason = outcome[1]
                res.step(f"FAILURE detected (SPA): {outcome[1]}")
            else:  # success
                res.confirmation_detected = True
                for pat in (REF_PATTERNS + [r"\b(ASH-[A-Z0-9]{6,})\b"]):
                    m = re.search(pat, body, re.IGNORECASE)
                    if m:
                        res.application_id = m.group(1)
                        break
                res.status = "Applied"
                res.step(f"CONFIRMATION detected via {res.detected_via} "
                         f"(url_changed={res.url_changed}). application_id={res.application_id}")

            await _evidence(page, res, evidence_dir, tag)
            return res
        except Exception as exc:
            res.status = "Failed"
            res.failure_reason = f"Exception: {exc}"
            try:
                await _evidence(page, res, evidence_dir, tag)
            except Exception:
                pass
            return res
        finally:
            await ctx.close()
            await browser.close()


async def _evidence(page, res: SubmitResult, evidence_dir: str, tag: str):
    base = Path(evidence_dir)
    shot = base / f"{tag}_confirmation.png"
    html = base / f"{tag}_snapshot.html"
    try:
        await page.screenshot(path=str(shot), full_page=True)
        res.screenshot_path = str(shot)
    except Exception as e:
        res.step(f"screenshot failed: {e}")
    try:
        html.write_text(await page.content())
        res.html_snapshot_path = str(html)
    except Exception as e:
        res.step(f"html snapshot failed: {e}")
    res.step(f"evidence saved: {res.screenshot_path}, {res.html_snapshot_path}")

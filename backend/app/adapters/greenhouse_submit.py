"""Greenhouse SUBMIT pipeline (Phase G3).

Clicks Submit, then proves the outcome before claiming success:
  - detects a confirmation page (success markers + confirmation number), OR
  - detects CAPTCHA / validation failure / rejection.

Status is "Applied" ONLY when a confirmation is detected. CAPTCHA, validation
errors, or an ambiguous result are recorded as FAILED with evidence — never a
false success. Evidence saved: confirmation URL, screenshot, HTML snapshot, and
the exact page text/title.

This module performs the click; it does NOT write to the database. Wiring a
*verified* result into an Application row is a separate integration step that
should only run against a real, authorized submission (the user's own genuine
application) — not the controlled mock used to validate this code.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger("jobara.greenhouse.submit")

# Success phrasings observed on real Greenhouse confirmation states
# (boards.greenhouse.io / job-boards.greenhouse.io) plus generic variants.
SUCCESS_MARKERS = [
    r"thank you for applying",
    r"application (?:has been|was) submitted",
    r"your application has been (?:submitted|received)",
    r"we(?:'| ha)ve received your application",
    r"application submitted",
    r"thanks for applying",
    r"confirmation number",
]
FAILURE_MARKERS = [
    (r"recaptcha|captcha|security check|are you a robot|verify you(?:'| a)re human",
     "CAPTCHA challenge"),
    (r"there were errors with your submission|this field is required|please correct|"
     r"is required\b|invalid (?:email|phone)", "Validation error"),
    (r"too many requests|rate limit", "Rate limited"),
]
# NOTE: real Greenhouse frequently does NOT show the applicant a numeric
# application id on the confirmation page. When no id is found we record
# "Submitted" (confirmation detected) rather than "Verified Submitted".
REF_PATTERNS = [
    r"\b(GH-[A-Z0-9]{6,})\b",                                      # explicit GH token
    r"confirmation number(?:\s+is)?[:\s]+([A-Z0-9][A-Z0-9\-]{4,})",
    r"application id[:\s]+([A-Z0-9\-]{4,})",
    r"reference(?:\s+number)?[:\s#]+([A-Z0-9\-]{4,})",
]


def classify_confirmation(title: str, body: str) -> tuple:
    """Pure detector: (status, application_id, reason) from page text.

    status ∈ {"Verified Submitted","Submitted","CAPTCHA Required","Failed"}.
    Failure markers win over success (a failure must never read as success).
    """
    hay = f"{title}\n{body}".lower()
    for pat, reason in FAILURE_MARKERS:
        if re.search(pat, hay):
            return ("CAPTCHA Required" if "CAPTCHA" in reason else "Failed", None, reason)
    if any(re.search(m, hay) for m in SUCCESS_MARKERS):
        app_id = None
        for pat in REF_PATTERNS:
            m = re.search(pat, body, re.IGNORECASE)
            if m:
                app_id = m.group(1)
                break
        # "Verified Submitted" requires an extractable id (caller also requires a
        # stored screenshot). Otherwise it's a confirmed-but-unverified Submit.
        return ("Verified Submitted" if app_id else "Submitted", app_id, "")
    return ("Failed", None, "No confirmation markers found after submit (ambiguous)")


@dataclass
class SubmitResult:
    form_url: str
    submit_clicked: bool = False
    confirmation_detected: bool = False
    status: str = "Failed"            # "Applied" only if confirmed
    application_id: Optional[str] = None
    confirmation_url: str = ""
    screenshot_path: str = ""
    html_snapshot_path: str = ""
    platform_response: str = ""       # exact page title + text excerpt
    failure_reason: str = ""
    steps: list = field(default_factory=list)

    def step(self, m): self.steps.append(m); log.info(m)


async def submit_application(form_url: str, fill: Callable, evidence_dir: str,
                             tag: str = "submit") -> SubmitResult:
    """fill(page) must populate the form (caller-supplied). Then we submit + verify."""
    from playwright.async_api import async_playwright

    res = SubmitResult(form_url=form_url)
    Path(evidence_dir).mkdir(parents=True, exist_ok=True)
    res.step(f"=== G3 submit start: {form_url} ===")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 1400})
        page = await ctx.new_page()
        try:
            await page.goto(form_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector("#first_name, form", timeout=15000)
            res.step("form loaded")

            await fill(page)
            res.step("form filled (caller)")

            # Click submit (Greenhouse uses #submit_app; fall back to a submit button).
            clicked = False
            for sel in ("#submit_app", "button[type='submit']", "input[type='submit']"):
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

            # Wait for navigation / confirmation render.
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await page.wait_for_timeout(1000)

            res.confirmation_url = page.url
            title = await page.title()
            body = (await page.inner_text("body")) if await page.locator("body").count() else ""
            res.platform_response = f"TITLE: {title}\nURL: {page.url}\nBODY:\n{body[:800]}"

            lower = (title + "\n" + body).lower()

            # Failure detection first — never let a failure look like success.
            for pat, reason in FAILURE_MARKERS:
                if re.search(pat, lower):
                    res.failure_reason = reason
                    res.status = "Failed"
                    res.step(f"FAILURE detected: {reason}")
                    await _evidence(page, res, evidence_dir, tag)
                    return res

            # Success detection.
            if any(re.search(m, lower) for m in SUCCESS_MARKERS):
                res.confirmation_detected = True
                for pat in REF_PATTERNS:
                    m = re.search(pat, body, re.IGNORECASE)
                    if m:
                        res.application_id = m.group(1)
                        break
                res.status = "Applied"
                res.step(f"CONFIRMATION detected. application_id={res.application_id}")
            else:
                res.failure_reason = "No confirmation markers found after submit (ambiguous)"
                res.status = "Failed"
                res.step("No confirmation detected — recording as FAILED (no false success)")

            await _evidence(page, res, evidence_dir, tag)
            return res
        except Exception as exc:
            res.failure_reason = f"Exception: {exc}"
            res.status = "Failed"
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
        content = await page.content()
        html.write_text(content)
        res.html_snapshot_path = str(html)
    except Exception as e:
        res.step(f"html snapshot failed: {e}")
    res.step(f"evidence saved: {res.screenshot_path}, {res.html_snapshot_path}")

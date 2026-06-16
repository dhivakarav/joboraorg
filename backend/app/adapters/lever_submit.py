"""Lever SUBMIT pipeline (Phase G3).

Clicks Lever's "Submit Application", then proves the outcome before claiming
success:
  - detects a confirmation page (success markers and/or a redirect to the Lever
    `/thanks` page + a reference number), OR
  - detects hCaptcha / validation failure.

Status is "Applied" ONLY when a confirmation is detected. hCaptcha, validation
errors, or an ambiguous result are recorded as FAILED/CAPTCHA with evidence —
never a false success.

It reuses the *already-verified* Greenhouse detection logic (success/failure
markers, reference patterns) by importing them — Greenhouse code is NOT modified.
Only the form-specific selectors and the `/thanks` URL signal are Lever-specific.

This module performs the click only against the controlled mock; it does NOT
write to the database. Wiring a verified result into an Application row must only
happen for a real, authorized submission by the user — and on Lever that is
gated by hCaptcha (see the production readiness report).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

# Reuse Greenhouse's verified detectors (read-only import; Greenhouse unchanged).
from .greenhouse_submit import FAILURE_MARKERS, REF_PATTERNS, SUCCESS_MARKERS

log = logging.getLogger("jobara.lever.submit")

LEVER_SUBMIT_SELECTORS = (
    ".template-btn-submit",
    "button[type='submit']",
    "button:has-text('Submit Application')",
    "input[type='submit']",
)


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
    platform_response: str = ""
    failure_reason: str = ""
    steps: list = field(default_factory=list)

    def step(self, m): self.steps.append(m); log.info(m)


async def submit_application(form_url: str, fill: Callable, evidence_dir: str,
                             tag: str = "submit") -> SubmitResult:
    """fill(page) populates the form (caller-supplied). Then we submit + verify."""
    from playwright.async_api import async_playwright

    res = SubmitResult(form_url=form_url)
    Path(evidence_dir).mkdir(parents=True, exist_ok=True)
    res.step(f"=== Lever G3 submit start: {form_url} ===")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 1400})
        page = await ctx.new_page()
        try:
            await page.goto(form_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector("form, input[name='name']", timeout=15000)
            res.step("form loaded")

            await fill(page)
            res.step("form filled (caller)")

            clicked = False
            for sel in LEVER_SUBMIT_SELECTORS:
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

            # Failure first — a failure must never read as success.
            for pat, reason in FAILURE_MARKERS:
                if re.search(pat, lower):
                    res.status = "CAPTCHA Required" if "CAPTCHA" in reason else "Failed"
                    res.failure_reason = reason
                    res.step(f"FAILURE detected: {reason}")
                    await _evidence(page, res, evidence_dir, tag)
                    return res

            # Success — text markers OR a redirect to Lever's /thanks page.
            on_thanks = "/thanks" in page.url
            if on_thanks or any(re.search(m, lower) for m in SUCCESS_MARKERS):
                res.confirmation_detected = True
                for pat in REF_PATTERNS:
                    m = re.search(pat, body, re.IGNORECASE)
                    if m:
                        res.application_id = m.group(1)
                        break
                # Lever reference token (LVR-...) if present.
                if not res.application_id:
                    m = re.search(r"\b(LVR-[A-Z0-9]{6,})\b", body)
                    if m:
                        res.application_id = m.group(1)
                res.status = "Applied"
                res.step(f"CONFIRMATION detected (thanks={on_thanks}). "
                         f"application_id={res.application_id}")
            else:
                res.status = "Failed"
                res.failure_reason = "No confirmation markers found after submit (ambiguous)"
                res.step("No confirmation detected — recording as FAILED (no false success)")

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

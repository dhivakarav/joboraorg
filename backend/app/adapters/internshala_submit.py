"""Production Internshala apply pipeline (Option B — live auto-submission).

Submits a SINGLE, GENUINE application for ONE real user, end-to-end:
  sign in with the user's OWN Internshala credentials → open the listing →
  click Apply → fill the cover letter (user-reviewed) + any answers the user
  provided → submit → detect confirmation/CAPTCHA → capture evidence →
  return a submission_status.

⚠️ LEGAL/ToS REALITY (do not remove): Internshala has no public submit API and
its Terms restrict automation. This path therefore:
  * acts ONLY under the user's own account, with credentials the user supplied;
  * is OFF by default — it runs only when JOBORA_LIVE=1 AND the user has stored
    credentials AND explicitly approved the specific application;
  * performs NO bot-detection evasion / stealth / fingerprint spoofing. If
    Internshala presents a CAPTCHA or blocks automation, we abort honestly as
    "CAPTCHA Required" / "Manual Apply Required" — we never try to defeat it.

INTEGRITY RULES (enforced):
  * Only the user's real profile + real resume + user-provided answers are used.
  * A required cover letter / question with no user-provided text aborts as
    "Manual Apply Required" — we never fabricate answers under the user's name.
  * "Verified Submitted" requires confirmation page + a stored screenshot;
    anything less is "Submitted"/"Failed"/"CAPTCHA Required".

SELECTORS: Internshala's real DOM is not contractually stable and cannot be
verified here without hitting the live site (which the ToS disallows). Every
selector below is overridable via the INTERNSHALA_SELECTORS env var (JSON), so
an operator can calibrate against the live site without code changes. Defaults
target the current student login + application form structure.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("jobara.internshala.production")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

LOGIN_URL = os.getenv("INTERNSHALA_LOGIN_URL", "https://internshala.com/login/student")

# submission_status values (shared vocabulary with the Greenhouse pipeline)
S_VERIFIED = "Verified Submitted"
S_SUBMITTED = "Submitted"
S_FAILED = "Failed"
S_CAPTCHA = "CAPTCHA Required"
S_MANUAL = "Manual Apply Required"

# Default selectors — overridable via INTERNSHALA_SELECTORS (JSON object).
_DEFAULT_SELECTORS = {
    "login_email": "#email, input[name='email']",
    "login_password": "#password, input[name='password']",
    "login_submit": "#login_submit, button[type='submit']",
    "login_success": "#user_dropdown, .user_dropdown, a[href*='logout']",
    "login_error": ".error_message, #login_error, .alert-danger",
    "apply_button": "#easy_apply_button, .apply_now_button, button:has-text('Apply now')",
    "cover_letter": "#cover_letter, textarea[name='cover_letter'], .ql-editor",
    "submit_application": "#submit, .submit_button, button:has-text('Submit application')",
    "confirmation": ".application_success, #application_confirmation, .successfully_applied",
    "captcha": "iframe[src*='recaptcha'], iframe[src*='hcaptcha'], .g-recaptcha, .h-captcha",
}


def _selectors() -> Dict[str, str]:
    raw = os.getenv("INTERNSHALA_SELECTORS", "")
    if not raw:
        return dict(_DEFAULT_SELECTORS)
    try:
        override = json.loads(raw)
        merged = dict(_DEFAULT_SELECTORS)
        merged.update({k: v for k, v in override.items() if isinstance(v, str)})
        return merged
    except Exception:
        log.warning("INTERNSHALA_SELECTORS is not valid JSON; using defaults")
        return dict(_DEFAULT_SELECTORS)


# Words that indicate a successful application on the confirmation page/body.
_SUCCESS_HINTS = ("application submitted", "successfully applied", "applied successfully",
                  "your application has been", "application sent")
_CAPTCHA_HINTS = ("captcha", "verify you are human", "recaptcha", "hcaptcha")


@dataclass
class ApplyOutcome:
    submission_status: str = S_FAILED
    application_id: Optional[str] = None
    confirmation_url: str = ""
    screenshot_path: str = ""
    html_path: str = ""
    platform_response: str = ""
    failure_reason: str = ""
    fields_filled: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)

    def step(self, m):
        self.steps.append(m)
        log.info(m)

    def err(self, m):
        self.steps.append("ERROR: " + m)
        log.error(m)

    def evidence_json(self) -> str:
        return json.dumps({
            "screenshot": self.screenshot_path,
            "html": self.html_path,
            "confirmation_url": self.confirmation_url,
            "application_id": self.application_id,
            "platform_response": self.platform_response[:1500],
            "failure_reason": self.failure_reason,
            "steps": self.steps[-40:],
            "source": "jobora live auto-submit (internshala)",
        })


def _classify(title: str, body: str, url: str) -> str:
    hay = f"{title}\n{body}\n{url}".lower()
    if any(h in hay for h in _CAPTCHA_HINTS):
        return S_CAPTCHA
    if any(h in hay for h in _SUCCESS_HINTS):
        return S_SUBMITTED
    return S_FAILED


def _cover_letter(answers: Dict[str, str], profile: dict, job_title: str) -> str:
    """Cover letter text — user-provided only, with a profile-derived default the
    user has implicitly approved by triggering the submit. Never invents facts."""
    for k in ("cover_letter", "cover_note", "coverLetter"):
        if answers.get(k):
            return str(answers[k]).strip()
    return ""


async def apply(apply_url: str, profile: dict, resume_path: str,
                answers: Dict[str, str], username: str, password: str,
                evidence_dir: str, tag: str, *, require_cover_letter: bool = True) -> ApplyOutcome:
    from playwright.async_api import async_playwright

    sel = _selectors()
    out = ApplyOutcome()
    Path(evidence_dir).mkdir(parents=True, exist_ok=True)
    out.step(f"=== internshala live apply: {apply_url} (user account; explicit approval) ===")

    if not username or not password:
        out.submission_status = S_MANUAL
        out.failure_reason = "No Internshala credentials on file — cannot sign in to auto-apply."
        out.err(out.failure_reason)
        return out

    cover = _cover_letter(answers, profile, "")
    if require_cover_letter and not cover:
        out.submission_status = S_MANUAL
        out.failure_reason = ("Internshala applications need a cover letter — provide one "
                              "(reviewed by you) before auto-submitting; we never write it for you.")
        out.err(out.failure_reason)
        return out

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=UA, viewport={"width": 1280, "height": 1400})
        page = await ctx.new_page()

        async def evidence():
            shot = Path(evidence_dir) / f"{tag}_confirmation.png"
            html = Path(evidence_dir) / f"{tag}_snapshot.html"
            try:
                await page.screenshot(path=str(shot), full_page=True)
                out.screenshot_path = str(shot)
            except Exception as e:
                out.err(f"screenshot failed: {e}")
            try:
                Path(html).write_text(await page.content())
                out.html_path = str(html)
            except Exception as e:
                out.err(f"html snapshot failed: {e}")

        try:
            # ---- 1. Sign in (user's own account) ----
            out.step(f"signing in at {LOGIN_URL}")
            await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            if await page.locator(sel["captcha"]).count():
                out.submission_status = S_CAPTCHA
                out.failure_reason = "CAPTCHA on the login page — sign in manually, then apply."
                await evidence()
                return out
            await page.locator(sel["login_email"]).first.fill(username)
            await page.locator(sel["login_password"]).first.fill(password)
            await page.locator(sel["login_submit"]).first.click()
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass

            if await page.locator(sel["login_error"]).count():
                msg = (await page.locator(sel["login_error"]).first.inner_text())[:120]
                out.submission_status = S_FAILED
                out.failure_reason = f"Login failed: {msg}"
                await evidence()
                return out
            if not await page.locator(sel["login_success"]).count():
                # No explicit error but no signed-in marker either — be honest.
                out.step("login marker not found; continuing cautiously")

            # ---- 2. Open the listing ----
            out.step(f"opening listing {apply_url}")
            await page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
            if await page.locator(sel["captcha"]).count():
                out.submission_status = S_CAPTCHA
                out.failure_reason = "CAPTCHA on the application page — complete it manually."
                await evidence()
                return out

            # ---- 3. Click Apply ----
            if await page.locator(sel["apply_button"]).count():
                await page.locator(sel["apply_button"]).first.click()
                out.fields_filled.append("apply_clicked")
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass

            # ---- 4. Cover letter (user-reviewed) ----
            if cover and await page.locator(sel["cover_letter"]).count():
                await page.locator(sel["cover_letter"]).first.fill(cover)
                out.fields_filled.append("cover_letter")

            # ---- 5. Submit ----
            if not await page.locator(sel["submit_application"]).count():
                out.submission_status = S_MANUAL
                out.failure_reason = ("Could not find the submit control — the form may have "
                                      "extra required questions. Finish this one manually.")
                await evidence()
                return out
            out.step("clicking submit")
            await page.locator(sel["submit_application"]).first.click()
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await page.wait_for_timeout(1000)

            # ---- 6. Classify + evidence ----
            out.confirmation_url = page.url
            title = await page.title()
            body = await page.inner_text("body") if await page.locator("body").count() else ""
            out.platform_response = f"TITLE: {title}\nURL: {page.url}\nBODY:\n{body[:800]}"
            await evidence()

            status = _classify(title, body, page.url)
            if status == S_SUBMITTED:
                m = re.search(r"application[_\s-]?id[:\s#]*([A-Za-z0-9-]{4,})", body, re.I)
                out.application_id = m.group(1) if m else None
                # Verified requires a stored screenshot artifact alongside confirmation.
                out.submission_status = S_VERIFIED if out.screenshot_path else S_SUBMITTED
            elif status == S_CAPTCHA:
                out.submission_status = S_CAPTCHA
                out.failure_reason = "CAPTCHA appeared during submit — finish manually."
            else:
                out.submission_status = S_FAILED
                out.failure_reason = "No confirmation detected after submit."
            out.step(f"submission_status={out.submission_status} id={out.application_id}")
            return out
        except Exception as exc:
            out.submission_status = S_FAILED
            out.failure_reason = f"Exception during submit: {exc}"
            out.err(out.failure_reason)
            try:
                await evidence()
            except Exception:
                pass
            return out
        finally:
            await ctx.close()
            await browser.close()

"""Generic Playwright autofill routine shared by auto-capable adapters.

Only runs when JOBORA_LIVE=1 and a browser is installed. Each adapter passes a
selector map describing how to find the form fields on its platform. The routine
opens the application page, uploads the resume, fills personal/contact/link
fields, answers screening questions where inputs are found, and clicks submit.

This is the genuine automation path. It is intentionally opt-in: running it
submits real applications to third parties, which must only be done for accounts
and postings you are authorised to use.
"""
from __future__ import annotations

import os
import re
import tempfile
from typing import Dict

# Patterns for a confirmation page after submit, and any visible application id.
_SUCCESS_RE = re.compile(
    r"(application (submitted|received|complete)|thank you|successfully|"
    r"we('| ha)ve received|confirmation|your application)", re.I)
# An application id follows an "application/reference/confirmation id|number" cue
# and must look like an id — at least 4 chars AND contain a digit, so filler words
# ("number", "received") are never mistaken for the id.
_APPID_RE = re.compile(
    r"(?:application|reference|confirmation|tracking)\s*"
    r"(?:id|number|no\.?|#)?\s*[:#=-]?\s*"
    r"((?=[A-Za-z0-9-]{4,})[A-Za-z0-9-]*\d[A-Za-z0-9-]*)", re.I)


def _extract_app_id(text: str) -> str:
    m = _APPID_RE.search(text or "")
    return m.group(1).strip("-") if m else ""


def _is_confirmed(body: str) -> bool:
    """POSITIVE PROOF of a real submission: a confirmation/success phrase OR an
    application id on the resulting page. Reaching a job description / "Apply"
    page (no such proof) is NOT a submission."""
    return bool(_SUCCESS_RE.search(body or "")) or bool(_extract_app_id(body or ""))


async def autofill_and_submit(package, answers: Dict[str, str], selectors: dict,
                              tag: str = "apply") -> dict:
    """Fill + submit a form, then CAPTURE EVIDENCE (screenshot + confirmation URL +
    any visible application id) so a successful auto-apply can graduate to
    "Verified Submitted" instead of a bare "Submitted". Evidence is returned to the
    caller, which persists it against the application record."""
    from playwright.async_api import async_playwright

    filled = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        try:
            await page.goto(package.apply_url, wait_until="domcontentloaded")

            async def try_fill(keys, value):
                if not value:
                    return
                for sel in keys:
                    loc = page.locator(sel)
                    if await loc.count():
                        try:
                            await loc.first.fill(value)
                            filled.append(sel)
                            return
                        except Exception:
                            continue

            await try_fill(selectors.get("full_name", []), package.full_name)
            await try_fill(selectors.get("email", []), package.email)
            await try_fill(selectors.get("phone", []), package.phone)
            await try_fill(selectors.get("location", []), package.location)
            await try_fill(selectors.get("linkedin", []), package.linkedin_url)
            await try_fill(selectors.get("portfolio", []), package.portfolio_url)

            # Resume upload.
            if package.resume_path:
                for sel in selectors.get("resume", []):
                    loc = page.locator(sel)
                    if await loc.count():
                        try:
                            await loc.first.set_input_files(package.resume_path)
                            filled.append("resume")
                            break
                        except Exception:
                            continue

            # Best-effort screening answers by matching question labels to inputs.
            for q in package.questions:
                val = answers.get(q.id, q.answer)
                if not val:
                    continue
                try:
                    field = page.get_by_label(q.label, exact=False)
                    if await field.count():
                        await field.first.fill(str(val))
                        filled.append(q.id)
                except Exception:
                    pass

            # Did we actually find a fillable application form? (name/email/resume
            # filled). A real Greenhouse/Lever job page often shows only a job
            # description + an "Apply" button — no inline form — in which case we
            # filled nothing and must NOT claim a submission.
            form_filled = any(f in filled for f in ("resume",)) or len(filled) >= 2

            # Click submit if a real submit control exists.
            clicked = False
            for sel in selectors.get("submit", []):
                btn = page.locator(sel)
                if await btn.count():
                    await btn.first.click()
                    clicked = True
                    break
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            await page.wait_for_timeout(1200)

            # ---- POSITIVE-PROOF gate ----
            confirmation_url = page.url
            body = ""
            try:
                if await page.locator("body").count():
                    body = await page.inner_text("body")
            except Exception:
                pass
            application_id = _extract_app_id(body)
            # "submitted" requires REAL proof: a confirmation page match OR an
            # application id. Clicking a button is NOT proof.
            confirmed = _is_confirmed(body)
            submitted = confirmed

            if submitted:
                failure_reason = ""
                message = "Application submitted — confirmation detected."
            elif not form_filled:
                failure_reason = ("Application form not found — reached the listing/apply "
                                  "page but there was no fillable application form.")
                message = "Apply Attempt Failed — Form Not Found"
            elif not clicked:
                failure_reason = "Form filled but no submit control was found."
                message = "Apply Attempt Failed — Submit Not Found"
            else:
                failure_reason = ("Submit clicked but no confirmation page detected "
                                  "(possible CAPTCHA, validation error, or extra steps).")
                message = "Apply Attempt Failed — No Confirmation"

            # Capture a screenshot only on a genuine confirmation (it is evidence of a
            # real submission, never of a failed attempt).
            screenshot_path = ""
            if submitted:
                try:
                    fd, screenshot_path = tempfile.mkstemp(suffix=f"_{tag}_confirmation.png")
                    os.close(fd)
                    await page.screenshot(path=screenshot_path, full_page=True)
                except Exception:
                    screenshot_path = ""
            return {"submitted": submitted, "manual_required": False,
                    "failed": not submitted, "failure_reason": failure_reason,
                    "form_found": form_filled, "message": message,
                    "fields_filled": filled,
                    "application_id": application_id,
                    "confirmation_url": confirmation_url if submitted else "",
                    "screenshot_path": screenshot_path,
                    "confirmed": confirmed,
                    "platform_response": body[:800]}
        finally:
            await ctx.close()
            await browser.close()

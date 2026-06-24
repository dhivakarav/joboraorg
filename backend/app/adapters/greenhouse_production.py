"""Production Greenhouse apply pipeline (Production Phase 1).

Submits a SINGLE, GENUINE application for ONE real user, end-to-end:
  fill (real profile + user-reviewed answers) → upload real resume →
  validate required fields → submit → detect confirmation/CAPTCHA →
  extract application id → capture evidence → return a submission_status.

INTEGRITY RULES (enforced):
  * Only the user's real profile + real resume + user-provided answers are used.
  * Screening questions are NEVER fabricated. A required question with no
    user-provided answer aborts as "Manual Apply Required" — we do not invent.
  * "Verified Submitted" requires ALL of: confirmation page + application id +
    stored screenshot. Anything less is "Submitted"/"Failed"/"CAPTCHA Required".

The caller (endpoint) is responsible for gating (explicit click, resume present,
profile complete, live-mode ready) before invoking apply().
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .greenhouse_fill import GHField, _fill_field, _read_value, fetch_fields
from .greenhouse_submit import classify_confirmation

log = logging.getLogger("jobara.greenhouse.production")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
EMBED_URL = "https://boards.greenhouse.io/embed/job_app?token={jid}"

# submission_status values
S_VERIFIED = "Verified Submitted"
S_SUBMITTED = "Submitted"
S_FAILED = "Failed"
S_CAPTCHA = "CAPTCHA Required"
S_MANUAL = "Manual Apply Required"


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
    questions_answered: List[str] = field(default_factory=list)
    missing_required: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)

    def step(self, m): self.steps.append(m); log.info(m)
    def err(self, m): self.steps.append("ERROR: " + m); log.error(m)

    def evidence_json(self) -> str:
        return json.dumps({
            "screenshot": self.screenshot_path,
            "html": self.html_path,
            "platform_response": self.platform_response[:2000],
            "failure_reason": self.failure_reason,
            "fields_filled": self.fields_filled,
            "questions_answered": self.questions_answered,
        })


def parse_board_job(job: dict) -> Optional[tuple]:
    """Derive (board, job_id) from a job dict (external_id or apply_url)."""
    ext = job.get("external_id") or ""
    m = re.match(r"gh-([a-zA-Z0-9_-]+)-(\d+)$", ext)
    if m:
        return m.group(1), int(m.group(2))
    url = job.get("apply_url") or ""
    jm = re.search(r"gh_jid=(\d+)", url) or re.search(r"/jobs/(\d+)", url)
    bm = re.search(r"(?:boards|job-boards)\.greenhouse\.io/(?:embed/job_app\?[^/]*for=)?([a-zA-Z0-9_-]+)", url)
    if jm and bm:
        return bm.group(1), int(jm.group(1))
    return None


def resolve_form_url(job: dict) -> Optional[str]:
    bj = parse_board_job(job)
    if bj:
        return EMBED_URL.format(jid=bj[1])
    url = job.get("form_url") or job.get("apply_url") or ""
    # The Greenhouse embed form is keyed by the job id (token) alone, so we can build
    # it from a gh_jid even when the apply URL is on the COMPANY's own careers domain
    # (e.g. coinbase.com/careers/...?gh_jid=, druva.com/.../jobs/NNN/?gh_jid=NNN) —
    # which parse_board_job can't recognise as a greenhouse board. (Verified: the
    # embed form loads with the standard fields for these ids.)
    m = re.search(r"gh_jid=(\d+)", url) or re.search(r"/jobs/(\d+)", url)
    if m:
        return EMBED_URL.format(jid=m.group(1))
    # Allow an explicit greenhouse embed/boards URL straight through (tests/mock).
    if "greenhouse.io" in url or url.startswith("http://127.0.0.1") or url.startswith("http://localhost"):
        return url
    return None


def _split_name(profile: dict) -> tuple:
    name = (profile.get("name") or "").strip()
    if profile.get("first_name") or profile.get("last_name"):
        return profile.get("first_name", ""), profile.get("last_name", "")
    parts = name.split()
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    return name, name or "Applicant"


async def _fill_react_input(loc, value: str) -> bool:
    """Fill a (possibly React-controlled) input and VERIFY the value persisted.

    Greenhouse's modern embed form uses controlled React inputs that can silently
    drop a programmatic `.fill()`. So we fill, read the value back, and if it didn't
    stick, retry by focusing + typing character-by-character (which fires the same
    key events a human would). Returns True only if the value is actually present.
    """
    value = str(value)
    try:
        await loc.scroll_into_view_if_needed(timeout=3000)
    except Exception:
        pass
    try:
        await loc.fill(value, timeout=5000)
    except Exception:
        pass
    try:
        if (await loc.input_value() or "").strip() == value.strip():
            return True
    except Exception:
        pass
    # Retry: clear, focus, and type (fires real keydown/input events React listens to).
    try:
        await loc.click(timeout=3000)
        await loc.fill("", timeout=3000)
        await loc.type(value, delay=15)
        return (await loc.input_value() or "").strip() == value.strip()
    except Exception:
        return False


async def apply(form_url: str, fields: List[GHField], profile: dict, resume_path: str,
                answers: Dict[str, str], evidence_dir: str, tag: str) -> ApplyOutcome:
    from playwright.async_api import async_playwright

    out = ApplyOutcome()
    Path(evidence_dir).mkdir(parents=True, exist_ok=True)
    out.step(f"=== production apply: {form_url} (genuine user; explicit click) ===")

    # GUARD: never launch the browser / call page.goto() without a real form URL.
    # If the apply page is on a company careers domain we can't map to a Greenhouse
    # form (no gh_jid / board), fail gracefully as Manual Apply — don't crash.
    if not form_url:
        out.submission_status = S_MANUAL
        out.failure_reason = ("Could not resolve a Greenhouse application form for this "
                              "listing (its apply page isn't a standard Greenhouse board "
                              "and carries no gh_jid). Apply manually via the listing link.")
        out.step(out.failure_reason)
        return out

    first, last = _split_name(profile)
    core_vals = {
        "first_name": first, "last_name": last,
        "email": profile.get("email", ""), "phone": profile.get("phone", ""),
        # Location is a real Greenhouse application field (often required). Fill it
        # from the user's profile so submissions aren't incomplete / rejected.
        "location": profile.get("location", "") or "",
    }

    # Integrity gate: required screening questions must be answered by the user.
    for f in fields:
        if f.name in ("first_name", "last_name", "email", "phone", "resume",
                      "resume_text", "cover_letter", "cover_letter_text"):
            continue
        if f.required:
            key = f.name.rstrip("[]")
            if not (answers.get(key) or answers.get(f.name)):
                out.missing_required.append(f"{f.name} — '{f.label[:50]}'")
    if out.missing_required:
        out.submission_status = S_MANUAL
        out.failure_reason = (f"{len(out.missing_required)} required screening question(s) "
                              f"need your answer — will not auto-fill. Apply manually or "
                              f"answer them first.")
        out.step(out.failure_reason)
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
            await page.goto(form_url, wait_until="domcontentloaded", timeout=30000)
            # Wait for the actual first_name INPUT to be visible (not just any <form>):
            # the modern Greenhouse embed is a React app, and the <form> exists before
            # the inputs hydrate — filling too early silently drops the values.
            try:
                await page.wait_for_selector("#first_name", state="visible", timeout=15000)
            except Exception:
                await page.wait_for_selector("#first_name, form", timeout=5000)
            await page.wait_for_timeout(400)   # let React finish hydrating handlers
            out.step("form loaded")

            # core fields (genuine profile)
            for name, val in core_vals.items():
                if not val:
                    continue
                # Greenhouse's location input is a Google-Places autocomplete whose
                # name is job_application[location] (not "location"), so it needs
                # broader selectors than the simple #name / [name=name] core fields.
                if name == "location":
                    sel = ("#location, [name='job_application[location]'], "
                           "[name='location'], input[autocomplete='address-level2'], "
                           "input[aria-label*='Location' i]")
                else:
                    sel = f"#{name}, [name='{name}']"
                loc = page.locator(sel)
                if not await loc.count():
                    continue
                if not await _fill_react_input(loc.first, str(val)):
                    out.err(f"core field '{name}' did not retain its value after fill")
                    continue
                out.fields_filled.append(name)
                # Location autocomplete: after typing, pick the first suggestion so
                # the value is actually accepted by the form's validation.
                if name == "location":
                    try:
                        await page.wait_for_timeout(900)
                        opt = page.locator(".pac-item, #location_autocomplete li, "
                                           "[role='option']").first
                        if await opt.count():
                            await opt.click()
                    except Exception:
                        pass

            # resume (genuine file)
            if resume_path and Path(resume_path).exists():
                for sel in ("input#resume", "input[name='resume']", "input[type='file']"):
                    if await page.locator(sel).count():
                        await page.locator(sel).first.set_input_files(resume_path)
                        await page.wait_for_timeout(1200)
                        out.fields_filled.append("resume")
                        break

            # screening answers (user-provided only)
            for f in fields:
                key = f.name.rstrip("[]")
                val = answers.get(key) or answers.get(f.name)
                if not val or f.name in ("first_name", "last_name", "email", "phone",
                                         "resume", "resume_text", "cover_letter", "cover_letter_text"):
                    continue
                if await _fill_field(page, f, str(val), out):
                    out.questions_answered.append(f.name)

            # re-validate required fields actually hold values before submitting
            unmet = []
            for f in fields:
                if not f.required or f.name in ("resume_text", "cover_letter", "cover_letter_text"):
                    continue
                if f.name == "resume":
                    if "resume" not in out.fields_filled:
                        unmet.append("resume")
                    continue
                if not await _read_value(page, f):
                    unmet.append(f.name)
            if unmet:
                out.submission_status = S_MANUAL
                out.failure_reason = f"Required fields not satisfied after fill: {', '.join(unmet)}"
                out.err(out.failure_reason)
                await evidence()
                return out

            # SUBMIT
            clicked = False
            for sel in ("#submit_app", "button[type='submit']", "input[type='submit']"):
                if await page.locator(sel).count():
                    out.step(f"clicking submit: {sel}")
                    await page.locator(sel).first.click()
                    clicked = True
                    break
            if not clicked:
                out.submission_status = S_FAILED
                out.failure_reason = "Submit control not found"
                await evidence()
                return out

            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await page.wait_for_timeout(1000)

            out.confirmation_url = page.url
            title = await page.title()
            body = await page.inner_text("body") if await page.locator("body").count() else ""
            out.platform_response = f"TITLE: {title}\nURL: {page.url}\nBODY:\n{body[:800]}"

            status, app_id, reason = classify_confirmation(title, body)
            out.application_id = app_id
            await evidence()
            if status == "CAPTCHA Required":
                out.submission_status, out.failure_reason = S_CAPTCHA, reason
            elif status == "Failed":
                out.submission_status, out.failure_reason = S_FAILED, reason
            elif status == "Verified Submitted":
                # Verified requires ALL three: confirmation + id + stored screenshot.
                out.submission_status = S_VERIFIED if out.screenshot_path else S_SUBMITTED
                if not out.screenshot_path:
                    out.failure_reason = "Confirmation + id detected but no screenshot stored"
            else:  # Submitted (confirmed, no id — common on real Greenhouse)
                out.submission_status = S_SUBMITTED
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

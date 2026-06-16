"""Ashby application-form INSPECTOR (Phase G0-G1).

READ-ONLY. Proves Jobara can reach a real Ashby application form and locate the
fields it would eventually fill. Submits nothing, clicks nothing, writes no DB.

Ashby is a **React SPA** and differs from Greenhouse AND Lever:
  * There is **no `<form>` element** — inputs are loose in the application tab,
    so detection is scoped to the page/application pane, not a form.
  * The public Posting API exposes **no form spec** (like Lever) — the rendered
    DOM is the only source of truth.
  * System fields use ids: `_systemfield_name`, `_systemfield_email`,
    `_systemfield_resume`; phone is an `input[type=tel]`; custom questions are
    UUID-named inputs/textareas.
  * **Yes/No questions render as `<button>` pairs** (backed by a hidden
    checkbox), not radio inputs.
  * The anti-bot gate is **Google reCAPTCHA** (`g-recaptcha-response`).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

import httpx

log = logging.getLogger("jobara.ashby.inspect")

POSTING_API = "https://api.ashbyhq.com/posting-api/job-board/{board}"
APPLY_URL = "https://jobs.ashbyhq.com/{board}/{job_id}/application"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                   r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
SYSTEM_IDS = {"_systemfield_name", "_systemfield_email", "_systemfield_resume"}


@dataclass
class FieldSpec:
    key: str            # id or name we will target
    label: str
    type: str
    required: bool
    found_in_dom: bool = True


@dataclass
class InspectReport:
    board: str
    job_id: str
    title: str = ""
    location: str = ""
    form_url: str = ""
    form_reached: bool = False
    has_form_element: bool = False        # Ashby = False (SPA, expected)
    core_fields: List[FieldSpec] = field(default_factory=list)
    screening_questions: List[FieldSpec] = field(default_factory=list)
    yesno_questions: int = 0              # rendered as <button>Yes/No</button> pairs
    resume_input_detected: bool = False
    resume_locator: str = ""
    submit_detected: bool = False
    captcha_present: bool = False
    captcha_kind: str = ""
    errors: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)

    def step(self, m):
        self.steps.append(m)
        log.info(m, extra={"extra_fields": {"board": self.board, "job_id": self.job_id}})

    def error(self, m):
        self.errors.append(m)
        log.error(m, extra={"extra_fields": {"board": self.board, "job_id": self.job_id}})


def parse_ref(value: str) -> Optional[tuple]:
    """Accept "Board job_id" or an Ashby apply/job URL."""
    value = value.strip()
    m = re.search(r"ashbyhq\.com/([^/]+)/([0-9a-fA-F-]{8,})", value)
    if m:
        return m.group(1), m.group(2)
    parts = value.split()
    if len(parts) == 2:
        return parts[0], parts[1]
    return None


def fetch_meta(report: InspectReport):
    """Title/location from the board API (NOTE: no form spec is exposed)."""
    url = POSTING_API.format(board=report.board)
    report.step(f"Fetching board metadata (Ashby API exposes NO form spec): {url}")
    try:
        r = httpx.get(url, params={"includeCompensation": "true"}, timeout=20,
                      headers={"User-Agent": UA})
        if r.status_code == 200:
            for j in r.json().get("jobs", []):
                if str(j.get("id")) == str(report.job_id):
                    report.title = j.get("title", "")
                    report.location = j.get("location", "")
                    report.step(f"Posting: '{report.title}' — {report.location or '-'}")
                    return
        report.step("Posting not found in board feed (metadata unavailable; DOM authoritative)")
    except Exception as exc:
        report.step(f"Board API fetch skipped ({exc}); DOM is authoritative for fields")


async def render_and_detect(report: InspectReport):
    from playwright.async_api import async_playwright

    report.form_url = APPLY_URL.format(board=report.board, job_id=report.job_id)
    report.step(f"Launching Chromium and navigating to apply SPA: {report.form_url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=UA)
        page = await ctx.new_page()
        try:
            await page.goto(report.form_url, wait_until="domcontentloaded", timeout=35000)
            # SPA: wait for the application inputs to hydrate.
            try:
                await page.wait_for_selector(
                    "#_systemfield_name, input[type='email'], button:has-text('Submit Application')",
                    timeout=20000)
            except Exception:
                report.error("Application form did not hydrate within timeout")
                return
            await page.wait_for_timeout(1500)
            report.form_reached = True
            report.step("Application SPA hydrated and reachable")

            report.has_form_element = (await page.locator("form").count()) > 0

            # Enumerate ALL controls on the page (no form scoping for the SPA).
            els = await page.eval_on_selector_all(
                "input, textarea, select",
                """es => es.map(e => ({
                    tag: e.tagName.toLowerCase(),
                    type: (e.getAttribute('type') || e.type || '').toLowerCase(),
                    name: e.getAttribute('name') || '',
                    id: e.id || '',
                    required: e.required || e.getAttribute('aria-required') === 'true'
                }))""")

            # --- system / core fields ---
            def add_core(key, label, typ, req):
                report.core_fields.append(FieldSpec(key=key, label=label, type=typ, required=req))

            by_id = {e["id"]: e for e in els if e["id"]}
            if "_systemfield_name" in by_id:
                add_core("#_systemfield_name", "Full name", "text",
                         by_id["_systemfield_name"]["required"])
            if "_systemfield_email" in by_id:
                add_core("#_systemfield_email", "Email", "email",
                         by_id["_systemfield_email"]["required"])
            tel = next((e for e in els if e["type"] == "tel"), None)
            if tel:
                add_core("input[type='tel']", "Phone", "tel", tel["required"])

            # --- resume upload (system file field) ---
            for sel in ("#_systemfield_resume", "input#_systemfield_resume",
                        "input[type='file']"):
                if await page.locator(sel).count() > 0:
                    report.resume_input_detected = True
                    report.resume_locator = sel
                    break

            # --- custom screening questions: UUID-named inputs/textareas ---
            for e in els:
                nm, idv = e["name"], e["id"]
                key = nm or idv
                if not key:
                    continue
                if idv in SYSTEM_IDS or e["type"] in ("tel", "file"):
                    continue
                if nm == "g-recaptcha-response" or idv.startswith("g-recaptcha"):
                    continue
                if _UUID.match(nm) or _UUID.match(idv):
                    kind = e["tag"] if e["tag"] in ("textarea", "select") else e["type"]
                    if kind == "checkbox":
                        continue  # backing field for a Yes/No button group, counted below
                    report.screening_questions.append(
                        FieldSpec(key=f"[name='{nm}']" if nm else f"#{idv}",
                                  label="(custom question)", type=kind, required=e["required"]))

            # --- Yes/No questions rendered as button pairs ---
            yes_btns = await page.locator("button:has-text('Yes')").count()
            no_btns = await page.locator("button:has-text('No')").count()
            report.yesno_questions = min(yes_btns, no_btns)

            # --- submit control ---
            for sel in ("button:has-text('Submit Application')",
                        "button[type='submit']"):
                if await page.locator(sel).count() > 0:
                    report.submit_detected = True
                    break

            # --- captcha (Ashby = Google reCAPTCHA) ---
            if (await page.locator("textarea[name='g-recaptcha-response'], "
                                   "[id^='g-recaptcha-response'], iframe[src*='recaptcha'], "
                                   ".g-recaptcha").count() > 0):
                report.captcha_present = True
                report.captcha_kind = "reCAPTCHA"
            elif await page.locator("iframe[src*='hcaptcha'], .h-captcha").count() > 0:
                report.captcha_present = True
                report.captcha_kind = "hCaptcha"

            report.step(
                f"DOM detection complete: {len(report.core_fields)} core fields, "
                f"{len(report.screening_questions)} text/area questions, "
                f"{report.yesno_questions} yes/no button questions, "
                f"resume={report.resume_input_detected}, submit={report.submit_detected}, "
                f"captcha={report.captcha_kind or 'none'}, has_form_el={report.has_form_element}")
        except Exception as exc:
            report.error(f"Render/detection failed: {exc}")
        finally:
            await ctx.close()
            await browser.close()


async def inspect(board: str, job_id: str) -> InspectReport:
    report = InspectReport(board=board, job_id=job_id)
    report.step(f"=== Ashby inspection start: {board}/{job_id} ===")
    fetch_meta(report)
    await render_and_detect(report)
    report.step("=== Inspection complete (READ-ONLY — nothing submitted, DB untouched) ===")
    return report

"""Lever application-form INSPECTOR (Phase G0-G1).

READ-ONLY. Proves Jobara can reach a real Lever application form and locate the
fields it would eventually fill. It does **not** submit, does **not** click any
button, and does **not** touch the database.

IMPORTANT architectural difference vs. Greenhouse:
  Greenhouse exposes an authoritative field spec via its Board API
  (`?questions=true`). **Lever's public postings API does NOT** expose the
  application form fields or custom screening questions — only job metadata.
  Therefore, for Lever, the *rendered DOM is the only source of truth* for the
  form. The posting API is used solely for title/location.

The render also detects whether the form embeds an hCaptcha — Lever public apply
forms ship an `h-captcha-response` field, which is a hard gate on unattended
automated submission. We surface it so the readiness verdict is honest.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

import httpx

log = logging.getLogger("jobara.lever.inspect")

POSTING_API = "https://api.lever.co/v0/postings/{company}/{pid}?mode=json"
APPLY_URL = "https://jobs.lever.co/{company}/{pid}/apply"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

# Lever's fixed/system fields (everything else under cards[...] is a custom question).
CORE_NAMES = ["name", "email", "phone", "org", "location",
              "urls[LinkedIn]", "urls[GitHub]", "urls[Portfolio]", "urls[Other]"]


@dataclass
class FieldSpec:
    name: str
    type: str
    required: bool
    found_in_dom: bool = False
    locator: str = ""


@dataclass
class QuestionField:
    name: str          # cards[<uuid>][fieldN]
    card: str          # the <uuid>
    type: str          # text / textarea / radio / checkbox / select-one
    required: bool


@dataclass
class InspectReport:
    company: str
    posting_id: str
    title: str = ""
    location: str = ""
    form_url: str = ""
    form_reached: bool = False
    core_fields: List[FieldSpec] = field(default_factory=list)
    question_fields: List[QuestionField] = field(default_factory=list)
    question_cards: int = 0                # distinct custom-question cards
    resume_input_detected: bool = False
    resume_locator: str = ""
    submit_detected: bool = False
    submit_label: str = ""
    captcha_present: bool = False
    captcha_kind: str = ""
    errors: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)

    def step(self, msg: str):
        self.steps.append(msg)
        log.info(msg, extra={"extra_fields": {"company": self.company, "pid": self.posting_id}})

    def error(self, msg: str):
        self.errors.append(msg)
        log.error(msg, extra={"extra_fields": {"company": self.company, "pid": self.posting_id}})


_UUID = r"[0-9a-fA-F-]{8,}"


def parse_ref(value: str) -> Optional[tuple]:
    """Accept "company posting_id", a jobs.lever.co URL, or an api.lever.co URL."""
    value = value.strip()
    # jobs.lever.co/<company>/<uuid>[/apply]  or api.lever.co/v0/postings/<company>/<uuid>
    m = re.search(r"lever\.co/(?:v0/postings/)?([A-Za-z0-9_.-]+)/(" + _UUID + r")", value)
    if m:
        return m.group(1), m.group(2)
    parts = value.split()
    if len(parts) == 2:
        return parts[0], parts[1]
    return None


def fetch_meta(report: InspectReport):
    """Posting metadata only — Lever's API does NOT carry the form/question spec."""
    url = POSTING_API.format(company=report.company, pid=report.posting_id)
    report.step(f"Fetching posting metadata (NOTE: Lever API has no form spec): {url}")
    try:
        r = httpx.get(url, timeout=20, headers={"User-Agent": UA})
        if r.status_code == 200:
            d = r.json()
            report.title = d.get("text", "")
            cat = d.get("categories") or {}
            report.location = cat.get("location", "") or d.get("country", "")
            report.step(f"Posting: '{report.title}' — {report.location or '-'}")
        else:
            report.step(f"Posting API returned {r.status_code} (metadata unavailable; DOM is authoritative)")
    except Exception as exc:
        report.step(f"Posting API fetch skipped ({exc}); DOM is authoritative for fields")


async def render_and_detect(report: InspectReport):
    from playwright.async_api import async_playwright

    report.form_url = APPLY_URL.format(company=report.company, pid=report.posting_id)
    report.step(f"Launching Chromium and navigating to apply form: {report.form_url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=UA)
        page = await ctx.new_page()
        try:
            await page.goto(report.form_url, wait_until="domcontentloaded", timeout=30000)
            report.step(f"Page loaded (final URL: {page.url})")

            title = (await page.title()) or ""
            if "404" in title or "not found" in title.lower():
                report.error("Apply page is 404 (posting closed/expired between discovery and apply)")
                return

            try:
                await page.wait_for_selector("form, input[name='name'], input[type='file']", timeout=15000)
                report.form_reached = True
                report.step("Application form rendered and reachable")
            except Exception:
                report.error("Form did not render within timeout — cannot detect fields")
                return

            # Enumerate the entire form once, in the browser, then classify in Python.
            elements = await page.eval_on_selector_all(
                "form input, form textarea, form select",
                """els => els.map(e => ({
                    tag: e.tagName.toLowerCase(),
                    type: (e.getAttribute('type') || e.type || '').toLowerCase(),
                    name: e.getAttribute('name') || '',
                    required: e.required || e.getAttribute('aria-required') === 'true'
                }))""",
            )

            present = {}     # name -> (type, required)
            for e in elements:
                nm = e["name"]
                if not nm:
                    continue
                # first occurrence wins for required (radio groups repeat the name)
                if nm not in present:
                    present[nm] = (e["tag"] if e["tag"] in ("textarea", "select") else e["type"], e["required"])
                elif e["required"]:
                    t, _ = present[nm]
                    present[nm] = (t, True)

            # Core/system fields
            for nm in CORE_NAMES:
                if nm in present:
                    t, req = present[nm]
                    report.core_fields.append(FieldSpec(name=nm, type=t, required=req,
                                                        found_in_dom=True,
                                                        locator=f"[name='{nm}']"))
                else:
                    report.core_fields.append(FieldSpec(name=nm, type="", required=False))

            # Custom screening questions: cards[<uuid>][...]
            cards = set()
            for nm, (t, req) in present.items():
                cm = re.match(r"cards\[([^\]]+)\]", nm)
                if cm:
                    cards.add(cm.group(1))
                    report.question_fields.append(
                        QuestionField(name=nm, card=cm.group(1), type=t, required=req))
            report.question_cards = len(cards)

            # Resume upload
            for sel in ("input[name='resume']", "input[type='file']", "input[id*='resume']"):
                if await page.locator(sel).count() > 0:
                    report.resume_input_detected = True
                    report.resume_locator = sel
                    break

            # Submit control
            for sel in ("button[type='submit']", ".template-btn-submit",
                        "button:has-text('Submit Application')", "input[type='submit']"):
                loc = page.locator(sel)
                if await loc.count() > 0:
                    report.submit_detected = True
                    try:
                        report.submit_label = (await loc.first.inner_text()).strip()[:40]
                    except Exception:
                        report.submit_label = sel
                    break

            # Captcha detection (Lever ships hCaptcha on public apply forms)
            if "h-captcha-response" in present or await page.locator(
                    "iframe[src*='hcaptcha'], .h-captcha, [data-hcaptcha-widget-id]").count() > 0:
                report.captcha_present = True
                report.captcha_kind = "hCaptcha"
            elif await page.locator("iframe[src*='recaptcha'], .g-recaptcha").count() > 0:
                report.captcha_present = True
                report.captcha_kind = "reCAPTCHA"

            core_found = sum(1 for f in report.core_fields if f.found_in_dom)
            req_q = sum(1 for q in report.question_fields if q.required)
            report.step(
                f"DOM detection complete: {core_found}/{len(report.core_fields)} core fields, "
                f"{report.question_cards} custom-question cards "
                f"({len(report.question_fields)} inputs, {req_q} required), "
                f"resume={report.resume_input_detected}, submit={report.submit_detected}, "
                f"captcha={report.captcha_kind or 'none'}")
        except Exception as exc:
            report.error(f"Render/detection failed: {exc}")
        finally:
            await ctx.close()
            await browser.close()


async def inspect(company: str, posting_id: str) -> InspectReport:
    report = InspectReport(company=company, posting_id=posting_id)
    report.step(f"=== Lever inspection start: {company}/{posting_id} ===")
    fetch_meta(report)
    await render_and_detect(report)
    report.step("=== Inspection complete (READ-ONLY — nothing submitted, DB untouched) ===")
    return report

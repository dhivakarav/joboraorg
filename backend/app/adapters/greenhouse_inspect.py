"""Greenhouse application-form INSPECTOR (Phase G0-G1).

READ-ONLY. This module proves Jobara can reach a real Greenhouse application
form and locate the fields it would eventually fill. It does **not** submit
anything, does **not** click submit, and does **not** touch the database.

Two sources are combined:
  1. The Greenhouse Board API (`?questions=true`) — the authoritative spec of
     every field on the posting (names, types, required flags). No rendering.
  2. A real Playwright render of the embedded application form — to confirm the
     fields, the resume file input, and the screening questions are actually
     present and reachable in the DOM (iframe-aware).

Every step is logged. The result is a structured report.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

import httpx

log = logging.getLogger("jobara.greenhouse.inspect")

BOARD_API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{jid}?questions=true"
# The embedded application form (serves the real form directly; redirects to
# job-boards.greenhouse.io/embed/job_app under the hood).
EMBED_URL = "https://boards.greenhouse.io/embed/job_app?token={jid}"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")


@dataclass
class FieldSpec:
    name: str
    type: str
    label: str
    required: bool
    found_in_dom: bool = False
    locator: str = ""


@dataclass
class InspectReport:
    board: str
    job_id: int
    title: str = ""
    location: str = ""
    form_url: str = ""
    used_iframe: bool = False
    form_reached: bool = False
    core_fields: List[FieldSpec] = field(default_factory=list)        # name/email/phone/...
    screening_questions: List[FieldSpec] = field(default_factory=list)
    resume_field_declared: bool = False
    resume_input_detected: bool = False
    resume_locator: str = ""
    errors: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)

    def step(self, msg: str):
        self.steps.append(msg)
        log.info(msg, extra={"extra_fields": {"board": self.board, "job_id": self.job_id}})

    def error(self, msg: str):
        self.errors.append(msg)
        log.error(msg, extra={"extra_fields": {"board": self.board, "job_id": self.job_id}})


# --------------------------------------------------------------------------
# Reference parsing
# --------------------------------------------------------------------------
def parse_ref(value: str) -> Optional[tuple]:
    """Accept a board+id, or a Greenhouse URL, and return (board, job_id)."""
    m = re.search(r"gh_jid=(\d+)", value)
    jid = int(m.group(1)) if m else None
    bm = re.search(r"(?:boards(?:-api)?\.greenhouse\.io|job-boards\.greenhouse\.io)/(?:embed/job_app\?[^/]*for=)?([a-zA-Z0-9_-]+)", value)
    board = bm.group(1) if bm else None
    if not jid:
        m2 = re.search(r"/jobs/(\d+)", value)
        jid = int(m2.group(1)) if m2 else None
    if board and jid:
        return board, jid
    return None


# --------------------------------------------------------------------------
# Step 1: authoritative field spec from the Board API
# --------------------------------------------------------------------------
def fetch_spec(report: InspectReport) -> dict:
    url = BOARD_API.format(board=report.board, jid=report.job_id)
    report.step(f"Fetching authoritative field spec from Board API: {url}")
    r = httpx.get(url, timeout=20, headers={"User-Agent": UA})
    r.raise_for_status()
    data = r.json()
    report.title = data.get("title", "")
    report.location = (data.get("location") or {}).get("name", "")
    report.step(f"Posting: '{report.title}' — {report.location}")

    core_names = {"first_name", "last_name", "email", "phone", "resume",
                  "resume_text", "cover_letter", "cover_letter_text"}
    for q in data.get("questions", []):
        required = bool(q.get("required"))
        label = q.get("label", "")
        for f in q.get("fields", []):
            fs = FieldSpec(name=f.get("name", ""), type=f.get("type", ""),
                           label=label, required=required)
            if fs.name == "resume":
                report.resume_field_declared = True
            if fs.name in core_names:
                report.core_fields.append(fs)
            else:
                report.screening_questions.append(fs)
    report.step(f"API declares {len(report.core_fields)} core fields, "
                f"{len(report.screening_questions)} screening fields. "
                f"Resume field declared: {report.resume_field_declared}")
    return data


# --------------------------------------------------------------------------
# Step 2: render the real form and detect fields (iframe-aware)
# --------------------------------------------------------------------------
async def render_and_detect(report: InspectReport):
    from playwright.async_api import async_playwright

    report.form_url = EMBED_URL.format(jid=report.job_id)
    report.step(f"Launching Chromium and navigating to embedded form: {report.form_url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=UA)
        page = await ctx.new_page()
        try:
            await page.goto(report.form_url, wait_until="domcontentloaded", timeout=30000)
            report.step(f"Page loaded (final URL: {page.url})")

            # --- iframe detection: legacy embeds wrap the form in #grnhse_iframe ---
            root = page
            iframe_el = await page.query_selector("iframe#grnhse_iframe, iframe[src*='greenhouse']")
            if iframe_el:
                report.used_iframe = True
                report.step("Detected Greenhouse iframe — switching into frame context")
                frame = await iframe_el.content_frame()
                if frame:
                    root = frame
                else:
                    report.error("iframe found but content_frame() returned None")
            else:
                report.step("No iframe — form is top-level on the embed page")

            # --- wait for the form to actually render ---
            try:
                await root.wait_for_selector("#first_name, [name='first_name'], form#application_form, form",
                                             timeout=15000)
                report.form_reached = True
                report.step("Application form rendered and reachable")
            except Exception:
                report.error("Form did not render within timeout — cannot detect fields")
                return

            # --- detect core fields by id then name ---
            for fs in report.core_fields:
                if fs.type == "input_file":
                    continue  # handled separately below
                for sel in (f"#{fs.name}", f"[name='{fs.name}']", f"[name='job_application[{fs.name}]']"):
                    try:
                        if await root.locator(sel).count() > 0:
                            fs.found_in_dom = True
                            fs.locator = sel
                            break
                    except Exception:
                        continue

            # --- detect resume file input (hidden behind the Attach widget) ---
            for sel in ("input#resume", "input[name='resume']", "input[type='file']",
                        "input[id*='resume']", "button:has-text('Attach')"):
                try:
                    if await root.locator(sel).count() > 0:
                        report.resume_input_detected = True
                        report.resume_locator = sel
                        break
                except Exception:
                    continue
            report.step(f"Resume upload input detected: {report.resume_input_detected}"
                        + (f" (via {report.resume_locator})" if report.resume_input_detected else ""))

            # --- detect screening questions in the DOM ---
            for fs in report.screening_questions:
                for sel in (f"#{fs.name}", f"[name='{fs.name}']", f"[id*='{fs.name}']",
                            f"[name*='{fs.name}']"):
                    try:
                        if await root.locator(sel).count() > 0:
                            fs.found_in_dom = True
                            fs.locator = sel
                            break
                    except Exception:
                        continue

            core_found = sum(1 for f in report.core_fields if f.found_in_dom)
            q_found = sum(1 for f in report.screening_questions if f.found_in_dom)
            report.step(f"DOM detection complete: {core_found}/"
                        f"{sum(1 for f in report.core_fields if f.type!='input_file')} core text fields, "
                        f"{q_found}/{len(report.screening_questions)} screening fields found")
        except Exception as exc:
            report.error(f"Render/detection failed: {exc}")
        finally:
            await ctx.close()
            await browser.close()


async def inspect(board: str, job_id: int) -> InspectReport:
    report = InspectReport(board=board, job_id=job_id)
    report.step(f"=== Greenhouse inspection start: {board}/{job_id} ===")
    try:
        fetch_spec(report)
    except Exception as exc:
        report.error(f"Board API fetch failed: {exc}")
        return report
    await render_and_detect(report)
    report.step("=== Inspection complete (READ-ONLY — nothing submitted, DB untouched) ===")
    return report

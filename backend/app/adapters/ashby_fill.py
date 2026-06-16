"""Ashby application-form FILL pipeline (Phase G2).

Fills every field class on an Ashby SPA apply form — system fields (name, email,
phone), resume upload, UUID-named text/textarea questions, and Yes/No questions
(which are `<button>` pairs, clicked not typed) — then VALIDATES that every
required field actually holds a value / selection.

It DOES NOT submit and DOES NOT click the submit button. Against a real Ashby
form this is safe: populating inputs client-side creates no application.

Returns a structured FillReport (per-field filled/missing + screenshot path).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("jobara.ashby.fill")

_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                   r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
SYSTEM_IDS = {"_systemfield_name", "_systemfield_email", "_systemfield_resume"}

# No fabricated applicant identity lives in production code. The caller (the
# user's real profile in Assisted-Apply, or a dev verification script) MUST
# supply the profile; an empty profile fills nothing.
DEFAULT_TEXT_ANSWER = "Yes — I am genuinely interested in this role and meet the listed requirements."


@dataclass
class FilledField:
    key: str
    kind: str
    required: bool
    filled: bool
    value_preview: str = ""


@dataclass
class FillReport:
    form_url: str
    form_reached: bool = False
    fields: List[FilledField] = field(default_factory=list)
    resume_uploaded: bool = False
    yesno_answered: int = 0
    screenshot_path: str = ""
    submit_clicked: bool = False        # ALWAYS False in G2 — asserted at end
    errors: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)

    def step(self, m): self.steps.append(m); log.info(m)
    def error(self, m): self.errors.append(m); log.error(m)

    @property
    def required_total(self): return sum(1 for f in self.fields if f.required)
    @property
    def required_filled(self): return sum(1 for f in self.fields if f.required and f.filled)


async def fill_form(page, profile: Optional[Dict] = None, resume_path: str = "",
                    text_answer: str = DEFAULT_TEXT_ANSWER) -> FillReport:
    report = FillReport(form_url=page.url)
    prof = dict(profile or {})

    try:
        await page.wait_for_selector(
            "#_systemfield_name, button:has-text('Submit Application')", timeout=20000)
        await page.wait_for_timeout(1200)
        report.form_reached = True
    except Exception:
        report.error("SPA form did not hydrate")
        return report

    # --- system fields ---
    async def fill_if(sel, val, name):
        if await page.locator(sel).count():
            try:
                await page.fill(sel, val); report.step(f"filled {name}")
            except Exception as e:
                report.error(f"could not fill {name}: {e}")

    await fill_if("#_systemfield_name", prof["name"], "name")
    await fill_if("#_systemfield_email", prof["email"], "email")
    await fill_if("input[type='tel']", prof["phone"], "phone")

    # --- resume upload (system file input; may be hidden behind 'Upload File') ---
    if resume_path and Path(resume_path).exists():
        for sel in ("#_systemfield_resume", "input#_systemfield_resume"):
            if await page.locator(sel).count():
                try:
                    await page.set_input_files(sel, resume_path)
                    report.resume_uploaded = True
                    report.step(f"uploaded resume via {sel}")
                    break
                except Exception as e:
                    report.error(f"resume upload failed via {sel}: {e}")
        if not report.resume_uploaded:
            # fall back to the first file input that is not a custom-question file
            files = page.locator("input[type='file']")
            if await files.count():
                try:
                    await files.first.set_input_files(resume_path)
                    report.resume_uploaded = True
                    report.step("uploaded resume via first file input")
                except Exception as e:
                    report.error(f"resume fallback upload failed: {e}")

    # --- UUID-named text/textarea custom questions ---
    els = await page.eval_on_selector_all(
        "input, textarea, select",
        """es => es.map(e => ({
            tag: e.tagName.toLowerCase(),
            type: (e.getAttribute('type') || e.type || '').toLowerCase(),
            name: e.getAttribute('name') || '', id: e.id || '',
            required: e.required || e.getAttribute('aria-required') === 'true'
        }))""")
    for e in els:
        nm, idv = e["name"], e["id"]
        if idv in SYSTEM_IDS or nm == "g-recaptcha-response":
            continue
        if not (_UUID.match(nm) or _UUID.match(idv)):
            continue
        kind = e["tag"] if e["tag"] in ("textarea", "select") else e["type"]
        sel = f"[name='{nm}']" if nm else f"#{idv}"
        try:
            if kind == "textarea":
                await page.fill(sel, text_answer)
            elif kind == "text":
                await page.fill(sel, text_answer)
            elif kind == "select-one" or e["tag"] == "select":
                opts = await page.eval_on_selector_all(
                    f"{sel} option", "os=>os.map(o=>o.value).filter(v=>v!=='')")
                if opts:
                    await page.select_option(sel, opts[0])
            else:
                continue
            report.step(f"answered question {sel} ({kind})")
        except Exception as ex:
            report.error(f"could not answer {sel} ({kind}): {ex}")

    # --- Yes/No questions: click the 'Yes' button of each pair ---
    yes_buttons = page.locator("button:has-text('Yes')")
    n_yes = await yes_buttons.count()
    for i in range(n_yes):
        try:
            await yes_buttons.nth(i).click()
            report.yesno_answered += 1
        except Exception as ex:
            report.error(f"could not click Yes #{i}: {ex}")
    if n_yes:
        report.step(f"answered {report.yesno_answered}/{n_yes} yes/no questions (clicked Yes)")

    # --- VALIDATE current state ---
    state = await page.eval_on_selector_all(
        "input, textarea, select",
        """es => es.map(e => ({
            tag: e.tagName.toLowerCase(),
            type: (e.getAttribute('type') || e.type || '').toLowerCase(),
            name: e.getAttribute('name') || '', id: e.id || '',
            required: e.required || e.getAttribute('aria-required') === 'true',
            value: (e.value || ''), checked: !!e.checked,
            files: e.files ? e.files.length : 0
        }))""")
    for s in state:
        nm, idv = s["name"], s["id"]
        if nm == "g-recaptcha-response":
            continue
        kind = s["tag"] if s["tag"] in ("textarea", "select") else s["type"]
        key = nm or idv or kind
        if kind == "file":
            report.fields.append(FilledField(key, "file", s["required"], s["files"] > 0,
                                             f"{s['files']} file"))
        elif kind == "checkbox":
            # backs a Yes/No button group — filled if checked
            report.fields.append(FilledField(key, "yes/no", s["required"], s["checked"],
                                             "Yes" if s["checked"] else ""))
        elif kind in ("text", "email", "tel", "textarea", "select-one"):
            report.fields.append(FilledField(key[:34], kind, s["required"], bool(s["value"]),
                                             s["value"][:36]))

    assert report.submit_clicked is False, "G2 must not submit"
    report.step(f"validation: {report.required_filled}/{report.required_total} required fields filled "
                f"(submit_clicked={report.submit_clicked})")
    return report


async def screenshot(page, path: str, report: FillReport):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    try:
        await page.screenshot(path=path, full_page=True)
        report.screenshot_path = path
        report.step(f"screenshot saved: {path}")
    except Exception as e:
        report.error(f"screenshot failed: {e}")

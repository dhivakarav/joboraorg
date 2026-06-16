"""Lever application-form FILL pipeline (Phase G2).

Fills every field class on a Lever apply form — core/system fields, resume
upload, and custom screening questions (text, textarea, radio, checkbox,
select) — then VALIDATES that every required field actually holds a value.

It DOES NOT submit and DOES NOT click the submit button. Against a real Lever
form this is safe: populating inputs client-side creates no application. Against
the controlled mock it is the precursor to the G3 submit test.

Returns a structured FillReport (per-field filled/missing + screenshot path).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("jobara.lever.fill")


@dataclass
class FilledField:
    name: str
    kind: str            # text/email/file/textarea/radio/checkbox/select
    required: bool
    filled: bool
    value_preview: str = ""


@dataclass
class FillReport:
    form_url: str
    form_reached: bool = False
    fields: List[FilledField] = field(default_factory=list)
    resume_uploaded: bool = False
    screenshot_path: str = ""
    submit_clicked: bool = False        # ALWAYS False in G2 — asserted at the end
    errors: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)

    def step(self, m): self.steps.append(m); log.info(m)
    def error(self, m): self.errors.append(m); log.error(m)

    @property
    def required_total(self): return sum(1 for f in self.fields if f.required)
    @property
    def required_filled(self): return sum(1 for f in self.fields if f.required and f.filled)


# No fabricated applicant identity lives in production code. The caller (the
# user's real profile in Assisted-Apply, or a dev verification script) MUST
# supply the profile; an empty profile fills nothing.
DEFAULT_TEXT_ANSWER = "Yes — I am genuinely interested in this role and meet the listed requirements."


async def fill_form(page, profile: Optional[Dict] = None, resume_path: str = "",
                    text_answer: str = DEFAULT_TEXT_ANSWER) -> FillReport:
    report = FillReport(form_url=page.url)
    prof = dict(profile or {})

    try:
        await page.wait_for_selector("form, input[name='name']", timeout=15000)
        report.form_reached = True
    except Exception:
        report.error("Form did not render")
        return report

    # Enumerate the form so we fill exactly what's there (DOM is authoritative).
    elements = await page.eval_on_selector_all(
        "form input, form textarea, form select",
        """els => els.map(e => ({
            tag: e.tagName.toLowerCase(),
            type: (e.getAttribute('type') || e.type || '').toLowerCase(),
            name: e.getAttribute('name') || '',
            required: e.required || e.getAttribute('aria-required') === 'true'
        }))""",
    )

    # --- core / system fields ---
    for nm, val in prof.items():
        sel = f"[name='{nm}']"
        if await page.locator(sel).count():
            try:
                await page.fill(sel, val)
                report.step(f"filled core {nm}")
            except Exception as e:
                report.error(f"could not fill {nm}: {e}")

    # --- resume upload ---
    if resume_path and Path(resume_path).exists():
        for sel in ("input[name='resume']", "input[type='file']"):
            if await page.locator(sel).count():
                try:
                    await page.set_input_files(sel, resume_path)
                    report.resume_uploaded = True
                    report.step(f"uploaded resume via {sel}")
                    break
                except Exception as e:
                    report.error(f"resume upload failed: {e}")

    # --- custom screening questions: cards[<uuid>][...] ---
    handled_radio_groups = set()
    handled_checkbox_groups = set()
    for e in elements:
        nm = e["name"]
        if not nm or not nm.startswith("cards["):
            continue
        kind = e["tag"] if e["tag"] in ("textarea", "select") else e["type"]
        try:
            if kind == "textarea":
                await page.fill(f"textarea[name='{nm}']", text_answer)
            elif kind == "text":
                await page.fill(f"input[name='{nm}'][type='text']", text_answer)
            elif kind == "radio":
                if nm in handled_radio_groups:
                    continue
                handled_radio_groups.add(nm)
                await page.locator(f"input[name='{nm}'][type='radio']").first.check()
            elif kind == "checkbox":
                if nm in handled_checkbox_groups:
                    continue
                handled_checkbox_groups.add(nm)
                await page.locator(f"input[name='{nm}'][type='checkbox']").first.check()
            elif kind == "select-one" or e["tag"] == "select":
                opts = await page.eval_on_selector_all(
                    f"select[name='{nm}'] option",
                    "os=>os.map(o=>o.value).filter(v=>v!=='')")
                if opts:
                    await page.select_option(f"select[name='{nm}']", opts[0])
            else:
                continue
            report.step(f"answered question {nm} ({kind})")
        except Exception as ex:
            report.error(f"could not answer {nm} ({kind}): {ex}")

    # --- VALIDATE: read back current state for every field, flag required-but-empty ---
    state = await page.eval_on_selector_all(
        "form input, form textarea, form select",
        """els => els.map(e => ({
            tag: e.tagName.toLowerCase(),
            type: (e.getAttribute('type') || e.type || '').toLowerCase(),
            name: e.getAttribute('name') || '',
            required: e.required || e.getAttribute('aria-required') === 'true',
            value: (e.value || ''),
            checked: !!e.checked,
            files: e.files ? e.files.length : 0
        }))""",
    )
    seen = set()
    for s in state:
        nm = s["name"]
        if not nm:
            continue
        kind = s["tag"] if s["tag"] in ("textarea", "select") else s["type"]
        if kind in ("hidden",):
            continue
        # collapse radio/checkbox groups to one row (filled if ANY member is checked)
        if kind in ("radio", "checkbox"):
            key = (nm, kind)
            if key in seen:
                continue
            seen.add(key)
            group = [x for x in state if x["name"] == nm]
            filled = any(x["checked"] for x in group)
            req = any(x["required"] for x in group)
            report.fields.append(FilledField(nm, kind, req, filled, "checked" if filled else ""))
            continue
        if kind == "file":
            report.fields.append(FilledField(nm, "file", s["required"], s["files"] > 0,
                                             f"{s['files']} file"))
            continue
        val = s["value"]
        report.fields.append(FilledField(nm, kind, s["required"], bool(val), val[:40]))

    # --- assert we never submitted in G2 ---
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

"""Greenhouse application-form FILLER (Phase G2).

Fills every field on a real Greenhouse form, uploads the resume, and answers
screening questions by type (text, dropdown/react-select, radio, checkbox),
then validates that required fields hold a value.

HARD CONSTRAINTS (enforced):
  * NEVER clicks Submit. There is no submit code path in this module.
  * NEVER writes to the database. No model imports.
Screenshots are captured after: form loaded, resume uploaded, fields filled.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import httpx

log = logging.getLogger("jobara.greenhouse.fill")

BOARD_API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{jid}?questions=true"
EMBED_URL = "https://boards.greenhouse.io/embed/job_app?token={jid}"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

CORE_TEXT = {"first_name", "last_name", "email", "phone"}


@dataclass
class GHField:
    name: str
    type: str
    label: str
    required: bool
    values: list  # [(label, value)] for selects


@dataclass
class FillReport:
    board: str
    job_id: int
    title: str = ""
    form_url: str = ""
    form_loaded: bool = False
    resume_uploaded: bool = False
    fields_filled: List[str] = field(default_factory=list)
    questions_answered: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)
    missing_required: List[str] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)

    def step(self, m): self.steps.append(m); log.info(m)
    def err(self, m): self.errors.append(m); log.error(m)


def fetch_fields(board: str, jid: int) -> tuple:
    r = httpx.get(BOARD_API.format(board=board, jid=jid), timeout=20, headers={"User-Agent": UA})
    r.raise_for_status()
    data = r.json()
    fields = []
    for q in data.get("questions", []):
        for f in q.get("fields", []):
            fields.append(GHField(
                name=f.get("name", ""), type=f.get("type", ""),
                label=q.get("label", ""), required=bool(q.get("required")),
                values=[(v.get("label"), v.get("value")) for v in f.get("values", [])],
            ))
    return data.get("title", ""), fields


def _answer_for(f: GHField, profile: dict) -> Optional[str]:
    """Pick a value to put in a field (test data). Returns the label to choose."""
    if f.name == "first_name":
        return profile["first_name"]
    if f.name == "last_name":
        return profile["last_name"]
    if f.name == "email":
        return profile["email"]
    if f.name == "phone":
        return profile["phone"]
    if f.name in ("location", "job_application[location]") or "location" in f.name.lower():
        return profile.get("location", "") or None
    if f.type in ("input_text", "textarea"):
        return profile.get("text_answer", "N/A")
    if "select" in f.type:
        # Prefer an affirmative/likely-valid option, else the first value.
        labels = [lbl for lbl, _ in f.values if lbl]
        for pref in ("Yes", "United States", "United States of America"):
            if pref in labels:
                return pref
        return labels[0] if labels else None
    return None


async def fill_form(board: str, job_id: int, profile: dict, resume_path: str,
                    shot_dir: str) -> FillReport:
    from playwright.async_api import async_playwright

    rep = FillReport(board=board, job_id=job_id)
    rep.form_url = EMBED_URL.format(jid=job_id)
    Path(shot_dir).mkdir(parents=True, exist_ok=True)
    rep.step(f"=== G2 fill start: {board}/{job_id} (NO submit, NO DB) ===")

    try:
        rep.title, fields = fetch_fields(board, job_id)
    except Exception as exc:
        rep.err(f"Board API fetch failed: {exc}")
        return rep
    rep.step(f"Posting: '{rep.title}' — {len(fields)} fields declared")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=UA, viewport={"width": 1280, "height": 1600})
        page = await ctx.new_page()

        async def shot(tag):
            path = str(Path(shot_dir) / f"{board}_{job_id}_{tag}.png")
            try:
                await page.screenshot(path=path, full_page=True)
                rep.screenshots.append(path)
                rep.step(f"screenshot: {tag} → {path}")
            except Exception as e:
                rep.err(f"screenshot {tag} failed: {e}")

        try:
            await page.goto(rep.form_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector("#first_name, form", timeout=15000)
            rep.form_loaded = True
            rep.step("form loaded")
            await shot("01_form_loaded")

            # --- resume upload first ---
            resume_field = next((f for f in fields if f.name == "resume"), None)
            if resume_field and resume_path and Path(resume_path).exists():
                done = False
                for sel in ("input#resume", "input[name='resume']", "input[type='file']"):
                    loc = page.locator(sel)
                    if await loc.count():
                        try:
                            await loc.first.set_input_files(resume_path)
                            await page.wait_for_timeout(1200)  # let GH show the filename / S3 upload
                            rep.resume_uploaded = True
                            rep.fields_filled.append("resume")
                            rep.step(f"resume uploaded via {sel}")
                            done = True
                            break
                        except Exception as e:
                            rep.err(f"resume upload via {sel} failed: {e}")
                if not done:
                    rep.err("resume file input not fillable")
            await shot("02_resume_uploaded")

            # --- fill every other field by type ---
            for f in fields:
                if f.name in ("resume", "resume_text", "cover_letter", "cover_letter_text"):
                    continue
                want = _answer_for(f, profile)
                if want is None:
                    rep.skipped.append(f"{f.name} (no value for type {f.type})")
                    continue
                ok = await _fill_field(page, f, want, rep)
                if ok:
                    if f.name in CORE_TEXT:
                        rep.fields_filled.append(f.name)
                    else:
                        rep.questions_answered.append(f.name)

            await shot("03_fields_filled")

            # --- validate required fields actually hold a value ---
            for f in fields:
                if not f.required or f.name in ("resume", "resume_text", "cover_letter", "cover_letter_text"):
                    continue
                val = await _read_value(page, f)
                if not val:
                    rep.missing_required.append(f"{f.name} ({f.type}) — '{f.label[:40]}'")
            # resume required?
            if resume_field and resume_field.required and not rep.resume_uploaded:
                rep.missing_required.append("resume (input_file)")

            if rep.missing_required:
                rep.validation_errors.append(
                    f"{len(rep.missing_required)} required field(s) not satisfied")
            rep.step(f"validation: {len(rep.missing_required)} required field(s) missing")
            rep.step("=== G2 fill complete — STOPPED before submit (nothing submitted) ===")
        except Exception as exc:
            rep.err(f"fill failed: {exc}")
            await shot("99_error")
        finally:
            await ctx.close()
            await browser.close()
    return rep


async def _fill_field(page, f: GHField, want: str, rep: FillReport) -> bool:
    qid = f.name.rstrip("[]")
    try:
        # 1) native radio (match by label/value text)
        radios = page.locator(f"input[type='radio'][name='{f.name}']")
        if await radios.count():
            await radios.first.check()
            return True
        # 2) native checkbox
        checks = page.locator(f"input[type='checkbox'][name='{f.name}']")
        if await checks.count():
            await checks.first.check()
            return True
        # 3) native <select>
        native = page.locator(f"select#{qid}, select[name='{f.name}']")
        if await native.count():
            try:
                await native.first.select_option(label=want)
            except Exception:
                await native.first.select_option(index=1)
            return True
        # 4) react-select combobox (Greenhouse default for dropdowns)
        if "select" in f.type:
            combo = page.locator(f"#{qid}")
            if await combo.count():
                await combo.first.click()
                await page.wait_for_timeout(300)
                # type to filter, then pick the matching/first option
                try:
                    await page.keyboard.type(want[:20])
                    await page.wait_for_timeout(400)
                except Exception:
                    pass
                opt = page.locator(f"#react-select-{qid}-option-0, [id^='react-select-{qid}-option']").first
                if await opt.count():
                    await opt.click()
                    return True
                # fallback: press Enter to accept highlighted
                await page.keyboard.press("Enter")
                return True
        # 5) text / textarea
        if f.type in ("input_text", "textarea"):
            loc = page.locator(f"#{qid}, [name='{f.name}']")
            if await loc.count():
                await loc.first.fill(want)
                return True
    except Exception as e:
        rep.err(f"fill {f.name} ({f.type}) failed: {e}")
        return False
    rep.skipped.append(f"{f.name} (no matching input found)")
    return False


async def _read_value(page, f: GHField) -> str:
    qid = f.name.rstrip("[]")
    try:
        if f.type in ("input_text", "textarea"):
            loc = page.locator(f"#{qid}, [name='{f.name}']")
            if await loc.count():
                return (await loc.first.input_value()) or ""
        if "select" in f.type:
            # Native <select> first (some forms / the test mock), then react-select.
            native = page.locator(f"select#{qid}, select[name='{f.name}']")
            if await native.count():
                try:
                    return (await native.first.input_value()) or ""
                except Exception:
                    pass
        if "select" in f.type:
            # react-select shows the chosen value in .select__single-value/.multi-value
            container = page.locator(f"#{qid}").locator(
                "xpath=ancestor::div[contains(@class,'select__container')][1]")
            if await container.count():
                txt = await container.first.inner_text()
                # strip the label text; if a value chip exists it'll be present
                chip = container.first.locator(".select__single-value, .select__multi-value__label")
                if await chip.count():
                    return (await chip.first.inner_text()) or ""
                return ""
        radios = page.locator(f"input[type='radio'][name='{f.name}']:checked")
        if await radios.count():
            return "checked"
        checks = page.locator(f"input[type='checkbox'][name='{f.name}']:checked")
        if await checks.count():
            return "checked"
    except Exception:
        return ""
    return ""

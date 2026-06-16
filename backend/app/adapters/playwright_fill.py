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

from typing import Dict


async def autofill_and_submit(package, answers: Dict[str, str], selectors: dict) -> dict:
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

            # Submit.
            submitted = False
            for sel in selectors.get("submit", []):
                btn = page.locator(sel)
                if await btn.count():
                    await btn.first.click()
                    submitted = True
                    break
            await page.wait_for_timeout(1500)
            return {"submitted": submitted, "manual_required": False,
                    "fields_filled": filled,
                    "message": "Application submitted." if submitted
                               else "Form filled but submit control not found."}
        finally:
            await ctx.close()
            await browser.close()

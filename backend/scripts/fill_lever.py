"""G2: fill a REAL Lever apply form and validate — WITHOUT submitting.

Opens the live form, fills every field class (core, resume, screening
questions), validates that required fields hold values, saves a screenshot, and
then exits. It NEVER clicks submit and writes NO database record. Filling a form
client-side does not create an application.

Usage:
    python -m scripts.fill_lever <company> <posting_id>
    python -m scripts.fill_lever "https://jobs.lever.co/ro/<uuid>/apply"
"""
import asyncio
import sys
from pathlib import Path

from app.adapters.lever_fill import fill_form, screenshot
from app.adapters.lever_inspect import APPLY_URL, UA, parse_ref
from app.logging_config import setup_logging

EVID = "/tmp/jobara_lever_g2"
RESUME = "/tmp/jobara_test_resume.pdf"

# Dev verification identity (lives here in the test harness, never in app code).
TEST_PROFILE = {
    "name": "Test Candidate",
    "email": "g2.test@example.com",
    "phone": "+1 415 555 0100",
    "org": "Independent",
    "location": "Remote",
    "urls[LinkedIn]": "https://www.linkedin.com/in/test-candidate",
    "urls[GitHub]": "https://github.com/test-candidate",
    "urls[Portfolio]": "https://test-candidate.dev",
}


def make_resume():
    if Path(RESUME).exists():
        return
    txt = "Test Candidate\ng2.test@example.com\nSenior Engineer"
    stream = "BT /F1 11 Tf 50 760 Td 13 TL " + " ".join(
        "(%s) Tj T*" % l for l in txt.split("\n")) + " ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>",
            "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            "/Resources << /Font << /F1 5 0 R >> >> >>",
            "<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    pdf = "%PDF-1.4\n"; offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(pdf)); pdf += "%d 0 obj\n%s\nendobj\n" % (i, o)
    x = len(pdf); pdf += "xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for o in offs:
        pdf += "%010d 00000 n \n" % o
    pdf += "trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, x)
    Path(RESUME).write_bytes(pdf.encode("latin-1"))


async def run(company, pid):
    from playwright.async_api import async_playwright
    url = APPLY_URL.format(company=company, pid=pid)
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=UA, viewport={"width": 1280, "height": 1600})
        page = await ctx.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            report = await fill_form(page, profile=TEST_PROFILE, resume_path=RESUME)
            await screenshot(page, f"{EVID}/{company}_{pid[:8]}_filled.png", report)
            return report
        finally:
            await ctx.close(); await b.close()


def main():
    setup_logging("INFO")
    make_resume()
    args = sys.argv[1:]
    if len(args) == 1:
        ref = parse_ref(args[0])
        if not ref:
            print("Could not parse company/posting_id"); sys.exit(1)
        company, pid = ref
    elif len(args) == 2:
        company, pid = args
    else:
        print(__doc__); sys.exit(1)

    report = asyncio.run(run(company, pid))

    line = "=" * 70
    print(f"\n{line}\nLEVER G2 FILL + VALIDATE REPORT (no submit)\n{line}")
    print(f"Form URL        : {report.form_url}")
    print(f"Form reached    : {report.form_reached}")
    print(f"Resume uploaded : {report.resume_uploaded}")
    print(f"Submit clicked  : {report.submit_clicked}  (G2 invariant: must be False)")
    print(f"\nFIELDS (filled / required):")
    for f in report.fields:
        mark = "OK " if f.filled else ("MISS" if f.required else "-- ")
        req = "required" if f.required else "optional"
        print(f"  [{mark}] {f.name[:34]:34} {f.kind:9} {req:9} {f.value_preview}")
    print(f"\nRequired fields filled: {report.required_filled}/{report.required_total}")
    print(f"Screenshot           : {report.screenshot_path}")
    print(f"Errors               : {len(report.errors)}")
    for e in report.errors:
        print(f"  - {e}")
    ok = (report.form_reached and report.resume_uploaded
          and report.required_filled == report.required_total and not report.submit_clicked)
    print(f"\nG2 RESULT: {'PASS' if ok else 'PARTIAL/REVIEW'} "
          f"(reached+resume+all-required-filled+no-submit)")
    print(f"{line}\nNOTE: Form was NOT submitted. No database record created/updated.\n{line}")


if __name__ == "__main__":
    main()

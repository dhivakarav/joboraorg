"""G3 controlled test against the local mock Lever form.

Runs the real submit -> confirm -> extract -> evidence pipeline. NO real company
is contacted; NO database row is written. Exercises three paths:
  ok         -> confirmation + reference id  -> status "Applied"
  captcha    -> hCaptcha challenge           -> status "CAPTCHA Required" (NOT applied)
  validation -> validation error             -> status "Failed"        (NOT applied)

The captcha path is the important one: real public Lever forms ALL ship an
hCaptcha, so this proves the pipeline records that as a failure, never a false
success.
"""
import asyncio
import sys
from pathlib import Path

from app.adapters.lever_submit import submit_application
from app.logging_config import setup_logging

EVID = "/tmp/jobara_lever_g3"
MOCK = "http://127.0.0.1:8097"
CO, PID = "mockco", "11111111-2222-3333-4444-555555555555"
RESUME = "/tmp/jobara_test_resume.pdf"

PROFILE = {"name": "Test Candidate", "email": "g3.test@example.com",
           "phone": "+1 415 555 0100", "org": "Independent"}


def make_resume():
    if Path(RESUME).exists():
        return
    txt = "Test Candidate\ng3.test@example.com\nSenior Engineer"
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


async def fill(page):
    await page.fill("input[name='name']", PROFILE["name"])
    await page.fill("input[name='email']", PROFILE["email"])
    await page.fill("input[name='phone']", PROFILE["phone"])
    await page.fill("input[name='org']", PROFILE["org"])
    if await page.locator("input[name='resume']").count():
        await page.set_input_files("input[name='resume']", RESUME)
    if await page.locator("textarea").count():
        await page.locator("textarea").first.fill("I'm excited about this role.")
    if await page.locator("input[type='radio']").count():
        await page.locator("input[type='radio']").first.check()


def report(title, r):
    line = "=" * 68
    print(f"\n{line}\n{title}\n{line}")
    print(f"Job URL              : {r.form_url}")
    print(f"Submit clicked       : {r.submit_clicked}")
    print(f"Submission result    : {r.status}")
    print(f"Confirmation detected: {'Yes' if r.confirmation_detected else 'No'}")
    print(f"Application ID       : {r.application_id or '(none)'}")
    print(f"Confirmation URL     : {r.confirmation_url}")
    print(f"Screenshot path      : {r.screenshot_path}")
    print(f"HTML snapshot        : {r.html_snapshot_path}")
    print(f"Failure reason       : {r.failure_reason or '(none)'}")
    print(f"--- exact platform response (excerpt) ---\n{r.platform_response[:280]}")
    applied = r.status == "Applied" and r.confirmation_detected and bool(r.application_id) and bool(r.screenshot_path)
    print(f"--> DB action: {'WOULD set status=Applied (confirmation+id+evidence all present)' if applied else 'NO status change (not a verified submission)'}")


def main():
    setup_logging("INFO")
    make_resume()
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    base = f"{MOCK}/{CO}/{PID}/apply"

    if which in ("ok", "all"):
        r = asyncio.run(submit_application(f"{base}?mode=ok", fill, EVID, tag="success"))
        report("G3 — SUCCESS PATH (mock): confirmation + reference id", r)
    if which in ("captcha", "all"):
        r = asyncio.run(submit_application(f"{base}?mode=captcha", fill, EVID, tag="captcha"))
        report("G3 — hCAPTCHA PATH (mock): must record CAPTCHA, not success", r)
    if which in ("validation", "all"):
        r = asyncio.run(submit_application(f"{base}?mode=validation", fill, EVID, tag="validation"))
        report("G3 — VALIDATION-ERROR PATH (mock): must record Failed", r)
    print("\nNOTE: mock target only — no real employer contacted, no DB row written.")


if __name__ == "__main__":
    main()

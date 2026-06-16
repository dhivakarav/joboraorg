"""G3 controlled test against the local mock Ashby SPA form.

Runs the real submit -> (poll DOM state) -> confirm -> extract -> evidence
pipeline. NO real company is contacted; NO database row is written. Exercises:
  ok         -> in-app success panel + reference id -> "Applied"
  captcha    -> in-app reCAPTCHA challenge          -> "CAPTCHA Required" (not applied)
  validation -> in-app validation error            -> "Failed"          (not applied)

The point: Ashby shows its result IN PLACE with NO navigation (url_changed=False),
so confirmation is detected by DOM state — proving requirement #7.
"""
import asyncio
import sys
from pathlib import Path

from app.adapters.ashby_submit import submit_application
from app.logging_config import setup_logging

EVID = "/tmp/jobara_ashby_g3"
MOCK = "http://127.0.0.1:8096"
BOARD, JID = "MockCo", "11111111-2222-3333-4444-555555555555"
RESUME = "/tmp/jobara_test_resume.pdf"

PROFILE = {"name": "Test Candidate", "email": "g3.test@example.com", "phone": "+14155550100"}


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
    await page.fill("#_systemfield_name", PROFILE["name"])
    await page.fill("#_systemfield_email", PROFILE["email"])
    if await page.locator("input[type='tel']").count():
        await page.fill("input[type='tel']", PROFILE["phone"])
    if await page.locator("#_systemfield_resume").count():
        await page.set_input_files("#_systemfield_resume", RESUME)
    if await page.locator("textarea[name='0086e069-bc0c-467b-8d38-c3f023146e79']").count():
        await page.fill("textarea[name='0086e069-bc0c-467b-8d38-c3f023146e79']",
                        "I'm excited about this role.")
    yes = page.locator("button:has-text('Yes')")
    if await yes.count():
        await yes.first.click()


def report(title, r):
    line = "=" * 68
    print(f"\n{line}\n{title}\n{line}")
    print(f"Job URL              : {r.form_url}")
    print(f"Submit clicked       : {r.submit_clicked}")
    print(f"URL changed          : {r.url_changed}  (Ashby SPA expected: False)")
    print(f"Submission result    : {r.status}")
    print(f"Confirmation detected: {'Yes' if r.confirmation_detected else 'No'}"
          + (f"  via {r.detected_via}" if r.detected_via else ""))
    print(f"Application ID       : {r.application_id or '(none)'}")
    print(f"Screenshot path      : {r.screenshot_path}")
    print(f"HTML snapshot        : {r.html_snapshot_path}")
    print(f"Failure reason       : {r.failure_reason or '(none)'}")
    print(f"--- exact platform response (excerpt) ---\n{r.platform_response[:300]}")
    applied = (r.status == "Applied" and r.confirmation_detected
               and bool(r.application_id) and bool(r.screenshot_path))
    print(f"--> DB action: {'WOULD set status=Applied (confirmation+id+evidence all present)' if applied else 'NO status change (not a verified submission)'}")


def main():
    setup_logging("INFO")
    make_resume()
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    base = f"{MOCK}/{BOARD}/{JID}/application"

    if which in ("ok", "all"):
        r = asyncio.run(submit_application(f"{base}?mode=ok", fill, EVID, tag="success"))
        report("G3 — SUCCESS PATH (mock SPA): in-place confirmation + reference id", r)
    if which in ("captcha", "all"):
        r = asyncio.run(submit_application(f"{base}?mode=captcha", fill, EVID, tag="captcha"))
        report("G3 — reCAPTCHA PATH (mock SPA): must record CAPTCHA, not success", r)
    if which in ("validation", "all"):
        r = asyncio.run(submit_application(f"{base}?mode=validation", fill, EVID, tag="validation"))
        report("G3 — VALIDATION PATH (mock SPA): must record Failed", r)
    print("\nNOTE: mock target only — no real employer contacted, no DB row written.")


if __name__ == "__main__":
    main()

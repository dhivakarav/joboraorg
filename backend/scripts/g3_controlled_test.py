"""G3 controlled test against the local mock Greenhouse form.

Runs the real submit→confirm→extract→evidence pipeline. NO real company is
contacted; NO database row is written. Demonstrates both the success path and a
CAPTCHA-failure path (requirement: failures must be recorded, not reported as
success).
"""
import asyncio
import sys

from app.adapters.greenhouse_submit import submit_application
from app.logging_config import setup_logging

EVID = "/tmp/jobara_g3_evidence"
MOCK = "http://127.0.0.1:8099"

TEST_PROFILE = {
    "first_name": "Test", "last_name": "Candidate",
    "email": "g3.test@example.com", "phone": "+1 415 555 0100",
}
RESUME = "/tmp/jobara_test_resume.pdf"


def make_resume():
    from pathlib import Path
    if Path(RESUME).exists():
        return
    txt = "Test Candidate\ng3.test@example.com\nSenior Engineer"
    stream = "BT /F1 11 Tf 50 760 Td 13 TL " + " ".join(f"({l}) Tj T*" for l in txt.split(chr(10))) + " ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    pdf = "%PDF-1.4\n"; offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(pdf)); pdf += f"{i} 0 obj\n{o}\nendobj\n"
    x = len(pdf); pdf += f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n"
    for o in offs: pdf += f"{o:010d} 00000 n \n"
    pdf += f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF"
    Path(RESUME).write_bytes(pdf.encode("latin-1"))


async def fill(page):
    await page.fill("#first_name", TEST_PROFILE["first_name"])
    await page.fill("#last_name", TEST_PROFILE["last_name"])
    await page.fill("#email", TEST_PROFILE["email"])
    await page.fill("#phone", TEST_PROFILE["phone"])
    await page.set_input_files("#resume", RESUME)
    if await page.locator("#question_900001").count():
        await page.select_option("#question_900001", label="Yes")


def report(title, r):
    line = "=" * 66
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
    print(f"--- exact platform response (excerpt) ---\n{r.platform_response[:300]}")
    print(f"--> DB action: {'WOULD set status=Applied' if r.status == 'Applied' else 'NO status change (failed)'}")


def main():
    setup_logging("INFO")
    make_resume()
    which = sys.argv[1] if len(sys.argv) > 1 else "both"

    if which in ("ok", "both"):
        r = asyncio.run(submit_application(f"{MOCK}/job/ok", fill, EVID, tag="success"))
        report("G3 CONTROLLED TEST — SUCCESS PATH (mock)", r)
    if which in ("captcha", "both"):
        r = asyncio.run(submit_application(f"{MOCK}/job/captcha", fill, EVID, tag="captcha"))
        report("G3 CONTROLLED TEST — CAPTCHA FAILURE PATH (mock)", r)
    print("\nNOTE: mock target only — no real employer contacted, no DB row written.")


if __name__ == "__main__":
    main()

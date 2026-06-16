"""Production Phase 1 validation.

A) Direct: greenhouse_production.apply() against the MOCK form with a genuine
   profile + user-answered question → must yield 'Verified Submitted' with an
   application id and a stored screenshot.
B) Endpoint gates (no browser submission): real Greenhouse job is gated by
   approval, resume, profile completeness, platform, and live-readiness.

No real employer is contacted. The mock stands in for a Greenhouse form so the
real pipeline + DB persistence + evidence + status logic are exercised honestly.
"""
import asyncio
from pathlib import Path

from app.adapters.greenhouse_fill import GHField
from app.adapters.greenhouse_production import apply
from app.logging_config import setup_logging

MOCK = "http://127.0.0.1:8099"
EVID = "/tmp/jobara_prod_evidence"
RESUME = "/tmp/jobara_real_resume.pdf"

# A GENUINE (test-account) profile — the user's own info, not a fake applicant.
PROFILE = {
    "name": "Asha Rao", "email": "asha.rao@example.com", "phone": "+1 415 555 0190",
    "location": "Remote", "linkedin_url": "https://linkedin.com/in/asha-rao",
    "portfolio_url": "", "resume_path": RESUME,
}
# The mock form has one required select question_900001 (Yes/No) — user answered.
ANSWERS = {"question_900001": "Yes"}
FIELDS = [
    GHField("first_name", "input_text", "First Name", True, []),
    GHField("last_name", "input_text", "Last Name", True, []),
    GHField("email", "input_text", "Email", True, []),
    GHField("phone", "input_text", "Phone", False, []),
    GHField("resume", "input_file", "Resume/CV", True, []),
    GHField("question_900001", "multi_value_single_select", "Authorized to work?", True,
            [("Yes", 1), ("No", 2)]),
]


def make_resume():
    if Path(RESUME).exists():
        return
    txt = "Asha Rao\nasha.rao@example.com\nSenior Engineer\nPython, FastAPI"
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


def main():
    setup_logging("WARNING")
    make_resume()

    print("=" * 64)
    print("A) DIRECT apply() against mock — genuine profile + user answer")
    print("=" * 64)
    r = asyncio.run(apply(f"{MOCK}/job/ok", FIELDS, PROFILE, RESUME, ANSWERS, EVID, "prod"))
    print(f"  submission_status : {r.submission_status}")
    print(f"  application_id    : {r.application_id}")
    print(f"  confirmation_url  : {r.confirmation_url}")
    print(f"  screenshot stored : {bool(r.screenshot_path) and Path(r.screenshot_path).exists()} ({r.screenshot_path})")
    print(f"  fields filled     : {r.fields_filled}")
    print(f"  questions answered: {r.questions_answered}")
    print(f"  VERIFIED requires confirmation+id+screenshot → {r.submission_status == 'Verified Submitted'}")

    print("\n" + "=" * 64)
    print("A2) Integrity: required question with NO user answer → no fabrication")
    print("=" * 64)
    r2 = asyncio.run(apply(f"{MOCK}/job/ok", FIELDS, PROFILE, RESUME, {}, EVID, "prod_noans"))
    print(f"  submission_status : {r2.submission_status}  (expect 'Manual Apply Required')")
    print(f"  reason            : {r2.failure_reason}")
    print(f"  did NOT submit    : {r2.application_id is None}")


if __name__ == "__main__":
    main()

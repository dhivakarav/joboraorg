"""Phase G2 test runner — fill (NO submit) 3 real Greenhouse jobs + report.

Usage: python -m scripts.fill_greenhouse [board] [jid1 jid2 jid3]
Defaults to discovering 3 stripe postings that have screening questions.

NEVER submits. NEVER writes to the DB. Captures screenshots.
"""
import asyncio
import sys
from pathlib import Path

import httpx

from app.adapters.greenhouse_fill import fill_form
from app.logging_config import setup_logging

SHOT_DIR = "/tmp/jobara_g2_shots"

TEST_PROFILE = {
    "first_name": "Priya",
    "last_name": "Menon",
    "email": "priya.menon@example.com",
    "phone": "+1 415 555 0142",
    "text_answer": "N/A (automated form-fill validation test)",
}


def make_resume_pdf(path: str):
    text = ["Priya Menon", "priya.menon@example.com", "+1 415 555 0142",
            "Senior Backend Engineer", "Skills: Python, FastAPI, PostgreSQL, AWS"]
    stream = "BT /F1 11 Tf 50 760 Td 13 TL " + " ".join(f"({l}) Tj T*" for l in text) + " ET"
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
    Path(path).write_bytes(pdf.encode("latin-1"))


def discover(board: str, n: int = 3):
    jobs = httpx.get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", timeout=20).json().get("jobs", [])
    out = []
    for j in jobs:
        jid = j["id"]
        try:
            d = httpx.get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{jid}?questions=true", timeout=15).json()
        except Exception:
            continue
        if len(d.get("questions", [])) >= 5:
            out.append(jid)
        if len(out) >= n:
            break
    return out


def main():
    setup_logging("INFO")
    resume = "/tmp/jobara_test_resume.pdf"
    make_resume_pdf(resume)

    args = sys.argv[1:]
    if len(args) >= 2:
        board, jids = args[0], [int(x) for x in args[1:]]
    else:
        board = args[0] if args else "stripe"
        jids = discover(board, 3)
    print(f"Testing board={board} jobs={jids}")

    reports = []
    for jid in jids:
        reports.append(asyncio.run(fill_form(board, jid, TEST_PROFILE, resume, SHOT_DIR)))

    line = "=" * 70
    for r in reports:
        print(f"\n{line}\nG2 VALIDATION REPORT — {r.title}  [{r.board}/{r.job_id}]\n{line}")
        print(f"Form URL        : {r.form_url}")
        print(f"Form loaded     : {r.form_loaded}")
        print(f"Resume uploaded : {r.resume_uploaded}")
        print(f"Fields filled   ({len(r.fields_filled)}): {', '.join(r.fields_filled)}")
        print(f"Questions answrd ({len(r.questions_answered)}): {', '.join(r.questions_answered)}")
        if r.skipped:
            print(f"Skipped         ({len(r.skipped)}): {', '.join(r.skipped)}")
        print(f"Missing required ({len(r.missing_required)}):")
        for m in r.missing_required:
            print(f"   - {m}")
        print(f"Validation errors ({len(r.validation_errors)}): {r.validation_errors}")
        print(f"Errors          ({len(r.errors)}): {r.errors}")
        print(f"Screenshots     ({len(r.screenshots)}):")
        for s in r.screenshots:
            print(f"   - {s}")

    print(f"\n{line}\nOVERALL")
    for r in reports:
        verdict = "ALL REQUIRED FILLED" if not r.missing_required and r.form_loaded else "GAPS"
        print(f"  {r.board}/{r.job_id}: loaded={r.form_loaded} resume={r.resume_uploaded} "
              f"filled={len(r.fields_filled)} answered={len(r.questions_answered)} "
              f"missing_required={len(r.missing_required)} → {verdict}")
    print(f"{line}\nNOTE: Submit was NOT clicked. No application recorded. DB untouched.\n{line}")


if __name__ == "__main__":
    main()

"""Run the Ashby form inspector (G0-G1) and print a test report.

Usage:
    python -m scripts.inspect_ashby <Board> <job_id>
    python -m scripts.inspect_ashby "https://jobs.ashbyhq.com/Ramp/<uuid>/application"

READ-ONLY: opens the real SPA form, detects fields, submits NOTHING, writes NO DB.
"""
import asyncio
import sys

from app.adapters.ashby_inspect import inspect, parse_ref
from app.logging_config import setup_logging


def main():
    setup_logging("INFO")
    args = sys.argv[1:]
    if len(args) == 1:
        ref = parse_ref(args[0])
        if not ref:
            print("Could not parse board/job_id from:", args[0]); sys.exit(1)
        board, jid = ref
    elif len(args) == 2:
        board, jid = args
    else:
        print(__doc__); sys.exit(1)

    report = asyncio.run(inspect(board, jid))

    line = "=" * 70
    print(f"\n{line}\nASHBY FORM INSPECTION REPORT (G0-G1, read-only)\n{line}")
    print(f"Posting       : {report.title or '(unknown)'}  [{report.board}/{report.job_id}]")
    print(f"Location      : {report.location or '-'}")
    print(f"Form URL      : {report.form_url}")
    print(f"Form reached  : {report.form_reached}")
    print(f"Has <form> el : {report.has_form_element}  (Ashby is a React SPA — expected False)")
    print(f"Field spec    : DOM-only (Ashby API exposes NO form spec)")

    print(f"\nCORE / SYSTEM FIELDS (detected in live SPA DOM):")
    for f in report.core_fields:
        req = "required" if f.required else "optional"
        print(f"  [OK ] {f.label:14} {f.type:8} {req:9} ({f.key})")

    print(f"\nRESUME UPLOAD:")
    print(f"  input detected  : {report.resume_input_detected}"
          + (f"  (via {report.resume_locator})" if report.resume_input_detected else ""))

    print(f"\nSCREENING QUESTIONS:")
    print(f"  text/textarea/select : {len(report.screening_questions)} "
          f"({sum(1 for q in report.screening_questions if q.required)} required)")
    for q in report.screening_questions:
        req = "required" if q.required else "optional"
        print(f"    [OK ] {q.type:9} {req:9} {q.key}")
    print(f"  yes/no button questions : {report.yesno_questions}  (rendered as <button>Yes/No</button>)")

    print(f"\nSUBMIT CONTROL : detected={report.submit_detected}")
    print(f"CAPTCHA        : present={report.captcha_present}"
          + (f"  kind={report.captcha_kind}" if report.captcha_present else ""))

    print(f"\nERRORS: {len(report.errors)}")
    for e in report.errors:
        print(f"  - {e}")

    req_q = sum(1 for q in report.screening_questions if q.required)
    print(f"\nSUMMARY: form_reached={report.form_reached} | core {len(report.core_fields)} | "
          f"resume {report.resume_input_detected} | text-questions {len(report.screening_questions)} "
          f"({req_q} req) | yes/no {report.yesno_questions} | submit {report.submit_detected} | "
          f"captcha {report.captcha_kind or 'none'} | errors {len(report.errors)}")
    print(f"{line}\nNOTE: No application was submitted. No database record was created/updated.\n{line}")


if __name__ == "__main__":
    main()

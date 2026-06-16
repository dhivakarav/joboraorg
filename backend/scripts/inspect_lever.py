"""Run the Lever form inspector (G0-G1) and print a test report.

Usage:
    python -m scripts.inspect_lever <company> <posting_id>
    python -m scripts.inspect_lever "https://jobs.lever.co/ro/<uuid>/apply"

READ-ONLY: opens the real form, detects fields, submits NOTHING, writes NO DB.
"""
import asyncio
import sys

from app.adapters.lever_inspect import inspect, parse_ref
from app.logging_config import setup_logging


def main():
    setup_logging("INFO")
    args = sys.argv[1:]
    if len(args) == 1:
        ref = parse_ref(args[0])
        if not ref:
            print("Could not parse company/posting_id from:", args[0]); sys.exit(1)
        company, pid = ref
    elif len(args) == 2:
        company, pid = args[0], args[1]
    else:
        print(__doc__); sys.exit(1)

    report = asyncio.run(inspect(company, pid))

    line = "=" * 70
    print(f"\n{line}\nLEVER FORM INSPECTION REPORT (G0-G1, read-only)\n{line}")
    print(f"Posting      : {report.title or '(unknown)'}  [{report.company}/{report.posting_id}]")
    print(f"Location     : {report.location or '-'}")
    print(f"Form URL     : {report.form_url}")
    print(f"Form reached : {report.form_reached}")
    print(f"Field spec   : DOM-only (Lever API exposes NO form spec)")

    print(f"\nCORE / SYSTEM FIELDS (detected in live DOM):")
    for f in report.core_fields:
        mark = "OK " if f.found_in_dom else "MISS"
        req = "required" if f.required else "optional"
        print(f"  [{mark}] {f.name:18} {f.type:12} {req:9} {('('+f.locator+')') if f.found_in_dom else ''}")

    print(f"\nRESUME UPLOAD:")
    print(f"  input detected  : {report.resume_input_detected}"
          + (f"  (via {report.resume_locator})" if report.resume_input_detected else ""))

    print(f"\nSCREENING QUESTIONS: {report.question_cards} custom-question card(s), "
          f"{len(report.question_fields)} input(s)")
    by_card = {}
    for q in report.question_fields:
        by_card.setdefault(q.card, []).append(q)
    for card, qs in by_card.items():
        req = any(q.required for q in qs)
        types = ", ".join(sorted({q.type for q in qs}))
        print(f"  card {card[:18]:18} | {len(qs):2} input(s) | types: {types:24} | {'required' if req else 'optional'}")

    print(f"\nSUBMIT CONTROL : detected={report.submit_detected}"
          + (f'  label="{report.submit_label}"' if report.submit_detected else ""))
    print(f"CAPTCHA        : present={report.captcha_present}"
          + (f"  kind={report.captcha_kind}" if report.captcha_present else ""))

    print(f"\nERRORS: {len(report.errors)}")
    for e in report.errors:
        print(f"  - {e}")

    core_found = sum(1 for f in report.core_fields if f.found_in_dom)
    req_q = sum(1 for q in report.question_fields if q.required)
    print(f"\nSUMMARY: form_reached={report.form_reached} | core {core_found}/{len(report.core_fields)} | "
          f"resume {report.resume_input_detected} | question-cards {report.question_cards} "
          f"({req_q} required inputs) | submit {report.submit_detected} | "
          f"captcha {report.captcha_kind or 'none'} | errors {len(report.errors)}")
    print(f"{line}\nNOTE: No application was submitted. No database record was created/updated.\n{line}")


if __name__ == "__main__":
    main()

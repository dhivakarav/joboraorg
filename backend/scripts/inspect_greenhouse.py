"""Run the Greenhouse form inspector (G0-G1) and print a test report.

Usage:
    python -m scripts.inspect_greenhouse <board> <job_id>
    python -m scripts.inspect_greenhouse "https://...gh_jid=7964697...&for=stripe"

READ-ONLY: opens the real form, detects fields, submits NOTHING, writes NO DB.
"""
import asyncio
import sys

from app.adapters.greenhouse_inspect import inspect, parse_ref
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
        board, jid = args[0], int(args[1])
    else:
        print(__doc__); sys.exit(1)

    report = asyncio.run(inspect(board, jid))

    line = "=" * 68
    print(f"\n{line}\nGREENHOUSE FORM INSPECTION REPORT (G0-G1, read-only)\n{line}")
    print(f"Job          : {report.title or '(unknown)'}  [{report.board}/{report.job_id}]")
    print(f"Location     : {report.location or '-'}")
    print(f"Form URL     : {report.form_url}")
    print(f"Form reached : {report.form_reached}   |   via iframe: {report.used_iframe}")

    print(f"\nCORE FIELDS (declared by Greenhouse API → detected in live DOM):")
    for f in report.core_fields:
        if f.type == "input_file":
            continue
        mark = "OK " if f.found_in_dom else "MISS"
        req = "required" if f.required else "optional"
        print(f"  [{mark}] {f.name:16} {f.type:12} {req:9} {('('+f.locator+')') if f.found_in_dom else ''}")

    print(f"\nRESUME UPLOAD:")
    print(f"  declared by API : {report.resume_field_declared}")
    print(f"  input detected  : {report.resume_input_detected}"
          + (f"  (via {report.resume_locator})" if report.resume_input_detected else ""))

    print(f"\nSCREENING QUESTIONS ({len(report.screening_questions)} fields declared):")
    for f in report.screening_questions:
        mark = "OK " if f.found_in_dom else "MISS"
        req = "required" if f.required else "optional"
        print(f"  [{mark}] {f.name:20} {f.type:26} {req:9} | {f.label[:38]}")

    print(f"\nERRORS: {len(report.errors)}")
    for e in report.errors:
        print(f"  - {e}")

    core_text = [f for f in report.core_fields if f.type != "input_file"]
    core_found = sum(1 for f in core_text if f.found_in_dom)
    q_found = sum(1 for f in report.screening_questions if f.found_in_dom)
    print(f"\nSUMMARY: form_reached={report.form_reached} | "
          f"core {core_found}/{len(core_text)} | resume {report.resume_input_detected} | "
          f"questions {q_found}/{len(report.screening_questions)} | errors {len(report.errors)}")
    print(f"{line}\nNOTE: No application was submitted. No database record was created/updated.\n{line}")


if __name__ == "__main__":
    main()

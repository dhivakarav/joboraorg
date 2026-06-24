"""Bug 3 regression: a successful auto-apply must capture confirmation evidence
(screenshot + application id + confirmation URL) and graduate the row from
"Submitted" to "Verified Submitted". The browser step is mocked; we exercise the
evidence-capture/extraction + the integrity-gated persistence."""
import io

from app.adapters.playwright_fill import _extract_app_id
from app.automation.engine import _store_evidence


class _App:
    """Stand-in for the Application row (the fields _store_evidence writes)."""
    def __init__(self):
        self.id = 123
        self.application_id = ""
        self.external_application_id = ""
        self.confirmation_url = ""
        self.submission_evidence = ""
        self.evidence_available = False
        self.submission_status = "Submitted"
        self.submitted_at = None


def test_extract_application_id_from_confirmation_text():
    assert _extract_app_id("Thank you! Application ID: GH-7F3K9 received.") == "GH-7F3K9"
    assert _extract_app_id("Confirmation number: ABC12345") == "ABC12345"
    assert _extract_app_id("Reference #99812 — application received") == "99812"
    # Must NOT mistake the filler word "number" (no digit) for an id.
    assert _extract_app_id("Your application number is shown below") == ""
    assert _extract_app_id("no id here") == ""


def test_complete_evidence_graduates_to_verified(tmp_path, monkeypatch):
    shot = tmp_path / "conf.png"
    shot.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    # storage.save_file is exercised for real (local storage) via a temp DB dir.
    app = _App()
    _store_evidence(app, {
        "application_id": "GH-ABC123",
        "confirmation_url": "https://boards.greenhouse.io/x/confirmation",
        "screenshot_path": str(shot),
        "platform_response": "Application submitted. Application ID: GH-ABC123",
    })
    assert app.application_id == "GH-ABC123"
    assert app.confirmation_url.endswith("/confirmation")
    assert app.evidence_available is True
    assert app.submission_status == "Verified Submitted"   # id + url + screenshot
    assert app.submitted_at is not None


def test_missing_screenshot_stays_submitted():
    app = _App()
    _store_evidence(app, {
        "application_id": "GH-ABC123",
        "confirmation_url": "https://boards.greenhouse.io/x/confirmation",
        "screenshot_path": "",          # no artifact → cannot verify
    })
    assert app.evidence_available is False
    assert app.submission_status == "Submitted"            # NOT verified without evidence


def test_missing_id_stays_submitted():
    app = _App()
    _store_evidence(app, {
        "application_id": "",            # no confirmation id → cannot verify
        "confirmation_url": "https://boards.greenhouse.io/x/confirmation",
        "screenshot_path": "",
    })
    assert app.submission_status == "Submitted"

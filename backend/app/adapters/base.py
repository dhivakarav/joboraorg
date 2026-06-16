"""Platform adapter architecture.

Each adapter encapsulates how Jobora interacts with one application platform:
  - whether it can prefill / auto-submit, or is manual-only
  - which screening questions to ask
  - how to map the user's profile onto the application form
  - (live, opt-in) how to actually drive the browser to submit

Adapters declare their capability honestly. Where automated submission is not
technically or legally possible (LinkedIn, Workday), ``manual_only`` is True and
the UI surfaces "Manual Apply Required".

The design is intentionally pluggable: adding a platform = adding one Adapter
subclass and registering it. This scales to many platforms and thousands of jobs
because adapters are stateless and selected per-job by ``matches()``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

LIVE_MODE = os.getenv("JOBORA_LIVE", "0") == "1"


@dataclass
class ScreeningQuestion:
    id: str
    label: str
    type: str = "text"            # text | select | boolean | number
    options: List[str] = field(default_factory=list)
    answer: str = ""             # prefilled suggestion
    required: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id, "label": self.label, "type": self.type,
            "options": self.options, "answer": self.answer, "required": self.required,
        }


# Standard screening questions most ATS forms ask. Prefilled from the profile.
def standard_questions(profile: dict) -> List[ScreeningQuestion]:
    exp = profile.get("experience", 0) or 0
    return [
        ScreeningQuestion("work_auth", "Are you authorized to work in the job's country?",
                          "boolean", answer="Yes", required=True),
        ScreeningQuestion("require_sponsorship", "Will you now or in the future require visa sponsorship?",
                          "boolean", answer="No"),
        ScreeningQuestion("experience_years", "Total years of relevant experience",
                          "number", answer=str(exp)),
        ScreeningQuestion("notice_period", "Notice period (days)", "number", answer="30"),
        ScreeningQuestion("expected_ctc", "Expected salary (INR / year)", "text", answer=""),
        ScreeningQuestion("relocate", "Are you willing to relocate?", "boolean", answer="Yes"),
    ]


@dataclass
class ApplicationPackage:
    platform: str
    auto_submit: bool
    manual_only: bool
    full_name: str
    email: str
    phone: str
    location: str
    linkedin_url: str
    portfolio_url: str
    resume_path: str
    cover_note: str
    questions: List[ScreeningQuestion]
    apply_url: str
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "auto_submit": self.auto_submit,
            "manual_only": self.manual_only,
            "fields": {
                "full_name": self.full_name,
                "email": self.email,
                "phone": self.phone,
                "location": self.location,
                "linkedin_url": self.linkedin_url,
                "portfolio_url": self.portfolio_url,
                "resume_attached": bool(self.resume_path),
            },
            "questions": [q.to_dict() for q in self.questions],
            "cover_note": self.cover_note,
            "apply_url": self.apply_url,
            "notes": self.notes,
        }


class Adapter:
    platform: str = "Generic"
    supports_prefill: bool = False
    supports_auto_submit: bool = False
    manual_only: bool = True
    # Substrings that identify a job belonging to this platform.
    match_hosts: tuple = ()
    match_sources: tuple = ()

    def matches(self, job: dict) -> bool:
        url = (job.get("apply_url") or "").lower()
        source = (job.get("source") or "").lower()
        if any(h in url for h in self.match_hosts):
            return True
        if any(s == source for s in self.match_sources):
            return True
        return False

    def screening_questions(self, profile: dict, job: dict) -> List[ScreeningQuestion]:
        return standard_questions(profile)

    def build_package(self, profile: dict, job: dict, resume_path: str) -> ApplicationPackage:
        note = (
            f"Hi, I'm excited to apply for the {job.get('title','')} role at "
            f"{job.get('company','')}. With {profile.get('experience',0)} years of "
            f"experience and skills in {', '.join(profile.get('skills', [])[:5])}, "
            f"I believe I'd be a strong fit."
        )
        return ApplicationPackage(
            platform=self.platform,
            auto_submit=self.supports_auto_submit,
            manual_only=self.manual_only,
            full_name=profile.get("name", ""),
            email=profile.get("email", ""),
            phone=profile.get("phone", ""),
            location=profile.get("location", ""),
            linkedin_url=profile.get("linkedin_url", ""),
            portfolio_url=profile.get("portfolio_url", ""),
            resume_path=resume_path,
            cover_note=note,
            questions=self.screening_questions(profile, job),
            apply_url=job.get("apply_url", ""),
            notes="" if not self.manual_only else
                  "Automated submission is not available for this platform — apply manually.",
        )

    async def submit(self, package: ApplicationPackage, answers: Dict[str, str]) -> dict:
        """Actually submit the application.

        Manual-only adapters never submit. Capable adapters submit only in
        LIVE_MODE; otherwise they return a 'prepared' result so the workflow can
        record the application without performing an unauthorised network action.
        """
        if self.manual_only or not self.supports_auto_submit:
            return {"submitted": False, "manual_required": True,
                    "message": "Manual Apply Required for this platform."}
        if not LIVE_MODE:
            return {"submitted": False, "manual_required": False, "prepared": True,
                    "message": "Application prepared and approved. Enable JOBORA_LIVE to "
                               "perform the real browser submission."}
        # LIVE_MODE: drive the real browser (platform-specific, see subclasses).
        return await self._live_submit(package, answers)

    async def _live_submit(self, package: ApplicationPackage, answers: Dict[str, str]) -> dict:
        raise NotImplementedError(f"{self.platform} live submission not implemented")

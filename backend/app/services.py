"""Shared application services used by both the API routes and the worker.

Kept separate to avoid circular imports between routers and the queue worker.
"""
from __future__ import annotations

import json
from pathlib import Path

import os
import tempfile

from sqlalchemy.orm import Session

from .models import JobFilter, Resume, User
from .security import decrypt_bytes
from .storage import storage


def materialize_resume(file_path: str) -> str:
    """Return a readable local PDF path for a stored (possibly encrypted) resume.

    Resumes are stored encrypted at rest (PII). We fetch the blob from the
    storage backend, decrypt it (legacy plaintext passes through), and write a
    transient temp file for tools like pdfplumber / Playwright upload.
    """
    if not file_path:
        return ""
    blob = storage.open_bytes(file_path)
    if blob is None:
        # Backward-compat: maybe an old absolute path on disk.
        return file_path if os.path.exists(file_path) else ""
    try:
        data = decrypt_bytes(blob)
    except Exception:
        # Undecryptable blob (e.g. CREDENTIAL_KEY rotated/lost, or corruption).
        # Degrade gracefully — treat as "no usable resume" so search/dashboard stay
        # up and the user is prompted to re-upload, rather than 500-ing the request.
        import logging
        logging.getLogger("jobara.services").warning(
            "resume blob could not be decrypted (key change/corruption); "
            "treating as missing: %s", file_path)
        return ""
    fd, tmp = tempfile.mkstemp(suffix=".pdf")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return tmp


def load_profile(db: Session, user: User) -> dict:
    """Assemble the scoring/apply profile from the resume + filters + account."""
    resume = db.query(Resume).filter_by(user_id=user.id).first()
    filt = db.query(JobFilter).filter_by(user_id=user.id).first()
    skills = json.loads(resume.parsed_skills) if resume and resume.parsed_skills else []
    resume_path = ""
    if resume and resume.file_path:
        resume_path = materialize_resume(resume.file_path)
    return {
        "name": (resume.parsed_name if resume else "") or user.full_name,
        "email": (resume.parsed_email if resume else "") or user.email,
        "phone": (resume.parsed_phone if resume else "") or user.phone,
        "location": (resume.parsed_location if resume else "") or "",
        "linkedin_url": resume.linkedin_url if resume else "",
        "portfolio_url": resume.portfolio_url if resume else "",
        "skills": skills,
        "experience": (resume.parsed_experience if resume else 0) or user.years_experience,
        "seeker_type": user.seeker_type or "",   # student | fresher | experienced
        "roles": json.loads(filt.roles) if filt and filt.roles else [],
        "keywords": json.loads(filt.keywords) if filt and filt.keywords else [],
        "locations": json.loads(filt.locations) if filt and filt.locations else [],
        "resume_path": resume_path,
    }


def profile_complete(profile: dict) -> tuple:
    """A genuine, submittable profile needs real identity + a real resume."""
    missing = [k for k in ("name", "email", "phone") if not (profile.get(k) or "").strip()]
    if not profile.get("resume_path") or not Path(profile["resume_path"]).exists():
        missing.append("resume")
    return (len(missing) == 0, missing)

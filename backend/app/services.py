"""Shared application services used by both the API routes and the worker.

Kept separate to avoid circular imports between routers and the queue worker.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from .models import JobFilter, Resume, User
from .security import decrypt_bytes
from .storage import storage

# Prefix used by tempfile on this OS — any path under here was created by us.
_TMP_DIR = tempfile.gettempdir()


def materialize_resume(file_path: str) -> str:
    """Return a readable local PDF path for a stored (possibly encrypted) resume.

    Resumes are stored encrypted at rest (PII). We fetch the blob from the
    storage backend, decrypt it (legacy plaintext passes through), and write a
    transient temp file for tools like pdfplumber / Playwright upload.

    IMPORTANT: the caller is responsible for deleting the returned temp file
    when it is no longer needed. Use cleanup_profile_resources() on the profile
    dict — it handles this automatically for files created through load_profile().
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
        # Undecryptable blob (key rotated/lost, or corruption).
        # Degrade gracefully so search/dashboard stay up and the user is
        # prompted to re-upload rather than getting a 500.
        import logging
        logging.getLogger("jobara.services").warning(
            "resume blob could not be decrypted (key change/corruption); "
            "treating as missing: %s", file_path)
        return ""
    fd, tmp = tempfile.mkstemp(suffix=".pdf")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return tmp


def cleanup_profile_resources(profile: dict) -> None:
    """Delete the temp resume file created by load_profile(), if any.

    Call this in a finally block at the end of every code path that called
    load_profile() so temp files are never leaked to disk. Safe to call
    multiple times — idempotent.

    Example::

        profile = load_profile(db, user)
        try:
            ... use profile ...
        finally:
            cleanup_profile_resources(profile)
    """
    tmp = profile.pop("_resume_tmp", None)
    if tmp:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def load_profile(db: Session, user: User, materialize: bool = True) -> dict:
    """Assemble the scoring/apply profile from the resume + filters + account.

    When ``materialize=True`` (the default), a temporary local PDF copy of the
    resume is created (decrypted from storage) and its path is stored under
    ``profile["resume_path"]``. The caller MUST call
    ``cleanup_profile_resources(profile)`` in a finally block to avoid leaking
    that temp file to disk.

    When ``materialize=False``, no temp file is created — ``resume_path`` is
    set to the empty string even if a resume is stored. Use this for code paths
    that only need the text fields (skills, keywords, scoring) without needing
    to read or upload the actual PDF, e.g. job search and dashboard stats.
    """
    resume = db.query(Resume).filter_by(user_id=user.id).first()
    filt = db.query(JobFilter).filter_by(user_id=user.id).first()
    skills = json.loads(resume.parsed_skills) if resume and resume.parsed_skills else []
    resume_path = ""
    if materialize and resume and resume.file_path:
        resume_path = materialize_resume(resume.file_path)
    profile = {
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
    # Tag the temp path so cleanup_profile_resources() knows what to delete.
    # Only paths inside the OS temp directory were created by us here.
    if resume_path and resume_path.startswith(_TMP_DIR):
        profile["_resume_tmp"] = resume_path
    return profile


def profile_complete(profile: dict) -> tuple:
    """A genuine, submittable profile needs real identity + a real resume."""
    missing = [k for k in ("name", "email", "phone") if not (profile.get(k) or "").strip()]
    if not profile.get("resume_path") or not Path(profile["resume_path"]).exists():
        missing.append("resume")
    return (len(missing) == 0, missing)

"""Resume upload, parsing, and edit routes."""
import json
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_approved_user
from ..models import Resume, User
from ..schemas import ResumeEditIn, ResumeOut
from ..security import encrypt_bytes, encrypt_value
from ..storage import storage
from ..utils.resume_parser import parse_resume

router = APIRouter(prefix="/api/resume", tags=["resume"])


@router.post("/upload", response_model=ResumeOut)
async def upload_resume(
    file: UploadFile,
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    if file.content_type not in ("application/pdf", "application/octet-stream") and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    contents = await file.read()
    if len(contents) > settings.MAX_RESUME_BYTES:
        raise HTTPException(status_code=400, detail="Resume exceeds 5MB limit")
    # Light magic-byte check (real PDFs start with %PDF).
    if not contents[:5].startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File does not look like a valid PDF")

    # Parse from a transient temp file, then store ENCRYPTED at rest (PII).
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        tf.write(contents)
        tmp_path = tf.name
    parsed = parse_resume(tmp_path)
    try:
        os.unlink(tmp_path)
    except OSError:
        pass

    key = f"resumes/{user.id}_{uuid.uuid4().hex}.pdf"
    blob = encrypt_bytes(contents) if settings.PII_ENCRYPTION else contents
    storage.save_bytes(key, blob)

    resume = db.query(Resume).filter_by(user_id=user.id).first()
    if resume:
        resume.file_path = key
    else:
        resume = Resume(user_id=user.id, file_path=key)
        db.add(resume)

    resume.parsed_name = parsed["parsed_name"] or user.full_name
    resume.parsed_email = parsed["parsed_email"] or user.email
    resume.parsed_phone = parsed["parsed_phone"] or user.phone
    resume.parsed_location = parsed["parsed_location"]
    resume.parsed_skills = json.dumps(parsed["parsed_skills"])
    resume.parsed_experience = parsed["parsed_experience"] or user.years_experience
    resume.parsed_education = json.dumps(parsed["parsed_education"])
    resume.linkedin_url = parsed["linkedin_url"]
    resume.portfolio_url = parsed["portfolio_url"]
    # Encrypt parsed full text (PII) at rest.
    raw = parsed.get("raw_text", "")
    resume.raw_text = encrypt_value(raw) if (settings.PII_ENCRYPTION and raw) else raw
    db.commit()
    db.refresh(resume)

    from .. import analytics
    analytics.capture(analytics.RESUME_UPLOADED, user.id,
                      {"skills": len(parsed.get("skills") or [])})

    return _to_out(resume)


@router.get("/parsed", response_model=ResumeOut)
def get_parsed(user: User = Depends(get_approved_user), db: Session = Depends(get_db)):
    resume = db.query(Resume).filter_by(user_id=user.id).first()
    if not resume:
        return ResumeOut(parsed_name="", parsed_email="", parsed_phone="",
                         parsed_skills=[], parsed_experience=0, has_resume=False)
    return _to_out(resume)


@router.put("/parsed", response_model=ResumeOut)
def edit_parsed(
    data: ResumeEditIn,
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    resume = db.query(Resume).filter_by(user_id=user.id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Upload a resume first")
    if data.parsed_name is not None:
        resume.parsed_name = data.parsed_name
    if data.parsed_email is not None:
        resume.parsed_email = data.parsed_email
    if data.parsed_phone is not None:
        resume.parsed_phone = data.parsed_phone
    if data.parsed_location is not None:
        resume.parsed_location = data.parsed_location
    if data.parsed_skills is not None:
        resume.parsed_skills = json.dumps(data.parsed_skills)
    if data.parsed_experience is not None:
        resume.parsed_experience = data.parsed_experience
    if data.parsed_education is not None:
        resume.parsed_education = json.dumps(data.parsed_education)
    if data.linkedin_url is not None:
        resume.linkedin_url = data.linkedin_url
    if data.portfolio_url is not None:
        resume.portfolio_url = data.portfolio_url
    db.commit()
    db.refresh(resume)
    return _to_out(resume)


def _to_out(resume: Resume) -> ResumeOut:
    return ResumeOut(
        parsed_name=resume.parsed_name,
        parsed_email=resume.parsed_email,
        parsed_phone=resume.parsed_phone,
        parsed_location=resume.parsed_location or "",
        parsed_skills=json.loads(resume.parsed_skills or "[]"),
        parsed_experience=resume.parsed_experience,
        parsed_education=json.loads(resume.parsed_education or "[]"),
        linkedin_url=resume.linkedin_url or "",
        portfolio_url=resume.portfolio_url or "",
        uploaded_at=resume.uploaded_at,
        has_resume=True,
    )

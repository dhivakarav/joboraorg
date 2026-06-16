"""SQLAlchemy ORM models."""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    phone = Column(String, default="")
    years_experience = Column(Integer, default=0)
    job_title = Column(String, default="")
    seeker_type = Column(String, default="")     # student | fresher | experienced (onboarding)
    plan = Column(String, default="free")         # free | pro  (subscription tier)
    plan_since = Column(DateTime, nullable=True)  # when the current plan started
    status = Column(String, default="pending")  # pending | approved | suspended
    is_admin = Column(Boolean, default=False)
    must_change_password = Column(Boolean, default=False)  # force reset on first login
    email_verified = Column(Boolean, default=False)        # H5: verified email
    email_verify_hash = Column(String, default="")         # H5: sha256 of verify token
    email_verify_expires = Column(DateTime, nullable=True)
    token_version = Column(Integer, default=0)             # H2: bump to revoke all tokens
    created_at = Column(DateTime, default=datetime.utcnow)

    resume = relationship("Resume", back_populates="user", uselist=False, cascade="all, delete-orphan")
    filters = relationship("JobFilter", back_populates="user", uselist=False, cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="user", cascade="all, delete-orphan")


class PasswordReset(Base):
    __tablename__ = "password_resets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String, index=True, nullable=False)  # sha256 of the raw token
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_path = Column(String, nullable=False)
    parsed_name = Column(String, default="")
    parsed_email = Column(String, default="")
    parsed_phone = Column(String, default="")
    parsed_location = Column(String, default="")
    parsed_skills = Column(Text, default="[]")       # JSON string
    parsed_experience = Column(Integer, default=0)
    parsed_education = Column(Text, default="[]")     # JSON list of {detail, year}
    linkedin_url = Column(String, default="")
    portfolio_url = Column(String, default="")
    raw_text = Column(Text, default="")               # extracted text, for AI analysis
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="resume")


class JobFilter(Base):
    __tablename__ = "job_filters"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    roles = Column(Text, default="[]")       # JSON
    locations = Column(Text, default="[]")   # JSON
    job_types = Column(Text, default="[]")   # JSON
    keywords = Column(Text, default="[]")    # JSON
    min_salary = Column(Integer, default=500)
    daily_limit = Column(Integer, default=20)

    user = relationship("User", back_populates="filters")


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # H4
    portal = Column(String, nullable=False)          # source label (e.g. "Greenhouse")
    source = Column(String, default="")              # provider the job came from
    platform = Column(String, default="")            # apply platform / adapter
    job_title = Column(String, default="")
    company = Column(String, default="")
    location = Column(String, default="")
    salary = Column(String, default="")              # original salary text
    salary_inr = Column(String, default="")          # normalised to INR
    deadline = Column(String, default="")
    apply_url = Column(Text, default="")             # real application URL
    verified = Column(Boolean, default=False)        # source-validated
    match_score = Column(Integer, default=0)         # 0-100 fit score
    manual_required = Column(Boolean, default=False) # auto-submit not possible
    job_url_hash = Column(String, index=True, default="")  # job fingerprint (dedupe)
    # Internal lifecycle hint (NOT shown raw to users — see display_status).
    # Saved | Tracked | Pending | (legacy: Applied/Submitted). Never displayed
    # directly; app/status.py derives the canonical, evidence-gated label.
    status = Column(String, default="Tracked")

    # --- Submission pipeline (system-managed) ---
    # Draft | Tracked | Manual Apply | Queued | Processing | Submitted |
    # Verified Submitted | Failed | CAPTCHA Required | Manual Apply Required
    submission_status = Column(String, default="Draft", index=True)
    application_id = Column(String, default="")            # canonical platform reference id
    external_application_id = Column(String, default="")   # legacy alias of application_id (kept in sync)
    confirmation_url = Column(Text, default="")            # URL of the confirmation page
    evidence_available = Column(Boolean, default=False)    # True iff a confirmation screenshot/HTML is stored
    submitted_at = Column(DateTime, nullable=True)         # when submission was attempted/confirmed
    submission_evidence = Column(Text, default="")         # JSON: {screenshot, html, response, reason}
    submission_attempts = Column(Integer, default=0)       # H1: retry counter
    submission_payload = Column(Text, default="")          # JSON: {answers, external_id, form_url} for the worker

    applied_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="applications")

    @property
    def evidence_complete(self) -> bool:
        from .status import evidence_complete
        return evidence_complete(self)

    @property
    def display_status(self) -> str:
        """Canonical, evidence-gated status — the ONLY status any UI should show."""
        from .status import display_status
        return display_status(self)

    __table_args__ = (
        Index("ix_applications_user_status", "user_id", "status"),       # H4 dashboard/activity
        Index("ix_applications_user_substatus", "user_id", "submission_status"),
    )


class BetaInvite(Base):
    """Closed-beta invite code. When BETA_INVITE_REQUIRED=1, registration
    requires an unused code. Single-use; bound to the email that redeems it."""
    __tablename__ = "beta_invites"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    note = Column(String, default="")              # who/what it's for
    used_by_email = Column(String, default="")     # email that redeemed it
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    @property
    def used(self) -> bool:
        return self.used_at is not None


class Feedback(Base):
    """Beta feedback + bug reports."""
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    kind = Column(String, default="feedback")      # feedback | bug
    message = Column(Text, nullable=False)
    page = Column(String, default="")              # where it was filed
    rating = Column(Integer, nullable=True)        # optional 1-5
    severity = Column(String, default="")          # bug: low | medium | high
    contact_email = Column(String, default="")
    status = Column(String, default="open", index=True)  # open | triaged | closed
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

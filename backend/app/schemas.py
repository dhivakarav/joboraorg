"""Pydantic request/response schemas."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr


# ----- Auth -----
class RegisterIn(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    phone: str = ""
    years_experience: int = 0
    job_title: str = ""
    invite_code: str = ""   # required only when BETA_INVITE_REQUIRED is enabled


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResendVerificationIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str
    new_password: str


class RefreshIn(BaseModel):
    refresh_token: str


class VerifyEmailIn(BaseModel):
    token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str = ""
    token_type: str = "bearer"
    is_admin: bool
    status: str
    must_change_password: bool = False
    email_verified: bool = True


class UserOut(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    phone: str
    years_experience: int
    job_title: str
    seeker_type: str = ""
    status: str
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ----- Profile -----
class ProfileUpdateIn(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    years_experience: Optional[int] = None
    job_title: Optional[str] = None
    seeker_type: Optional[str] = None   # student | fresher | experienced


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str


# ----- Resume -----
class ResumeOut(BaseModel):
    parsed_name: str
    parsed_email: str
    parsed_phone: str
    parsed_location: str = ""
    parsed_skills: List[str]
    parsed_experience: int
    parsed_education: List[dict] = []
    linkedin_url: str = ""
    portfolio_url: str = ""
    uploaded_at: Optional[datetime] = None
    has_resume: bool = True


class ResumeEditIn(BaseModel):
    parsed_name: Optional[str] = None
    parsed_email: Optional[str] = None
    parsed_phone: Optional[str] = None
    parsed_location: Optional[str] = None
    parsed_skills: Optional[List[str]] = None
    parsed_experience: Optional[int] = None
    parsed_education: Optional[List[dict]] = None
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None


# ----- Filters -----
class FiltersIn(BaseModel):
    roles: List[str] = []
    locations: List[str] = []
    job_types: List[str] = []
    keywords: List[str] = []
    min_salary: int = 500
    daily_limit: int = 20
    min_match_score: int = 50      # 0-100; hide/skip jobs below this resume match


class FiltersOut(FiltersIn):
    pass


# ----- Real jobs -----
class JobOut(BaseModel):
    fingerprint: str
    external_id: str = ""
    source: str
    source_domain: str = ""        # platform domain the apply URL lives on
    title: str
    company: str
    location: str
    salary: str = ""
    salary_inr: str = ""
    deadline: str = ""
    posted_at: str = ""
    remote: bool = False
    job_type: str = ""
    employment_type: str = ""      # internship | fresher | job
    duration: str = ""             # e.g. "3 months" (internships)
    apply_url: str
    description_snippet: str = ""
    verified: bool = False
    match_score: int = 0
    match_reasons: List[str] = []
    # Eligibility (can THIS early-career user realistically apply to THIS role?)
    eligibility_score: int = 0
    eligibility_tier: str = ""          # Great fit | Eligible | Stretch | Not eligible
    eligible: bool = True
    eligibility_reason: str = ""
    eligibility_reasons: List[str] = []
    early_signal: str = ""              # Internship | New Grad | Fresher Friendly | ""
    platform: str = ""
    auto_submit: bool = False
    manual_required: bool = True
    application_mode: str = "manual_link_provided"   # auto_applied | manual_link_provided
    auto_apply_supported: bool = False               # source is an auto-capable ATS
    applied: bool = False  # has this user already applied/saved it


class JobSearchOut(BaseModel):
    items: List[JobOut]
    total: int
    sources: List[dict]
    hidden_ineligible: int = 0  # roles hidden as not-eligible (senior/PhD/visa/3+ yrs)
    internships_only: bool = False   # whether the internships-&-new-grad hard filter is active
    filtered_generic: int = 0        # eligible-but-no-early-signal roles hidden by the hard filter
    filtered_low_match: int = 0      # jobs hidden below the min match-score threshold
    min_match: int = 0               # the match threshold applied this request
    internshala_coverage: dict = {}  # Internshala source analytics (total/internships/fresher/ai_ml/software)
    internshala_search: dict = {}    # "Search on Internshala" deep-link (India + intern/fresher contexts)


class ApplyIntentIn(BaseModel):
    """Payload sent when a user clicks Apply on a real job."""
    fingerprint: str
    source: str
    title: str
    company: str
    location: str = ""
    salary: str = ""
    salary_inr: str = ""
    deadline: str = ""
    apply_url: str
    verified: bool = False
    match_score: int = 0
    platform: str = ""
    manual_required: bool = True
    status: str = "Tracked"  # Saved | Tracked (Applied is coerced -> Tracked)


# ----- Apply workflow (prepare / submit) -----
class PrepareIn(BaseModel):
    fingerprint: str
    source: str
    title: str
    company: str
    location: str = ""
    salary: str = ""
    salary_inr: str = ""
    apply_url: str
    description_snippet: str = ""
    verified: bool = False
    remote: bool = False


class SubmitIn(BaseModel):
    job: PrepareIn
    package: dict           # the (possibly user-edited) field values
    answers: dict = {}      # screening question answers {id: value}
    approved: bool = False  # user must approve before we proceed


class StatusUpdateIn(BaseModel):
    status: str  # Applied | Submitted | Interview | Rejected | Offer | Pending


class GreenhouseApplyIn(BaseModel):
    """Explicit, user-triggered real Greenhouse application."""
    fingerprint: str
    external_id: str = ""
    source: str
    title: str
    company: str
    location: str = ""
    salary: str = ""
    salary_inr: str = ""
    apply_url: str
    verified: bool = False
    answers: dict = {}        # user-reviewed screening answers {field_name: value}
    approved: bool = False    # must be True — explicit confirmation


class InternshalaApplyIn(BaseModel):
    """Explicit, user-triggered LIVE Internshala application (Option B).

    Runs only with JOBORA_LIVE=1 + the user's stored Internshala credentials +
    a user-reviewed cover letter. `approved` must be True.
    """
    fingerprint: str
    source: str
    title: str
    company: str
    location: str = ""
    salary: str = ""
    salary_inr: str = ""
    apply_url: str
    verified: bool = False
    cover_letter: str = ""    # user-reviewed; we never write it for them
    answers: dict = {}        # any extra user-reviewed answers
    approved: bool = False    # must be True — explicit confirmation


class PlatformCredentialIn(BaseModel):
    """Store a user's own login for a platform (encrypted at rest)."""
    platform: str = "Internshala"
    username: str             # login email / username
    password: str


class EvidenceOut(BaseModel):
    application_id: int             # the DB row id
    display_status: str = "Draft"   # canonical, evidence-gated status
    submission_status: str
    reference_id: str = ""          # platform confirmation/reference id
    external_application_id: str = ""
    confirmation_url: str = ""
    evidence_available: bool = False
    submitted_at: Optional[datetime] = None
    has_screenshot: bool = False
    screenshot_url: str = ""        # short-lived signed URL (or S3 presigned)
    platform_response: str = ""
    failure_reason: str = ""


# ----- Applications -----
class ApplicationOut(BaseModel):
    id: int
    portal: str
    source: str = ""
    platform: str = ""
    job_title: str
    company: str
    location: str
    salary: str = ""
    salary_inr: str = ""
    deadline: str = ""
    apply_url: str = ""
    verified: bool = False
    match_score: int = 0
    manual_required: bool = False
    application_mode: str = "manual_link_provided"   # auto_applied | manual_link_provided
    # `status` is the raw internal lifecycle hint; clients MUST render
    # `display_status` instead (canonical, evidence-gated — never "Applied").
    status: str
    display_status: str = "Draft"
    submission_status: str = "Draft"
    # The raw user-set pipeline stage (or "") — the Stage dropdown renders this
    # directly so all 6 stages round-trip, independent of submission_status.
    pipeline_stage: str = ""
    application_id: str = ""
    external_application_id: str = ""
    confirmation_url: str = ""
    evidence_available: bool = False
    submitted_at: Optional[datetime] = None
    applied_at: datetime

    class Config:
        from_attributes = True


class PaginatedApplications(BaseModel):
    items: List[ApplicationOut]
    total: int
    page: int
    page_size: int


# ----- Admin -----
class AdminUserOut(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    status: str
    created_at: datetime
    application_count: int = 0

    class Config:
        from_attributes = True


class AdminUserDetails(BaseModel):
    user: UserOut
    has_resume: bool
    total_applications: int
    recent_activity: List[ApplicationOut]

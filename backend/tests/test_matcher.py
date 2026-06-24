"""Bug 2 regression: match scores must DIFFER across jobs with clearly different
skill requirements (the bug was every job showing ~32% because the job
description text wasn't reaching the matcher)."""
from app.automation.matcher import match_score, score_job

PROFILE = {
    "skills": ["Python", "Machine Learning", "PyTorch", "Kubernetes", "Docker"],
    "roles": ["Machine Learning Engineer", "Data Scientist"],
    "keywords": ["machine learning"],
    "experience": 0,
}

JOBS = [
    {"title": "Machine Learning Engineer",
     "description_snippet": "Build ML models in Python with PyTorch; deploy training pipelines."},
    {"title": "DevOps Engineer",
     "description_snippet": "Operate Kubernetes and Docker clusters; CI/CD and Terraform."},
    {"title": "iOS Developer",
     "description_snippet": "Ship native iOS apps in Swift and Objective-C with UIKit."},
    {"title": "Salesforce Administrator",
     "description_snippet": "Manage Salesforce CRM, Apex flows and CPQ configuration."},
    {"title": "Senior Accountant",
     "description_snippet": "Month-end close, revenue recognition and audit support."},
]


def test_match_scores_differ_across_distinct_roles():
    scores = [score_job(j, PROFILE)["score"] for j in JOBS]
    # Not all identical, and a healthy spread (the old bug produced one flat number).
    assert len(set(scores)) >= 4, f"scores too uniform: {scores}"
    assert max(scores) - min(scores) >= 25, f"insufficient spread: {scores}"


def test_relevant_role_outranks_irrelevant_one():
    ml = score_job(JOBS[0], PROFILE)["score"]            # ML Engineer (Python/PyTorch)
    acct = score_job(JOBS[4], PROFILE)["score"]          # Accountant (no overlap)
    devops = score_job(JOBS[1], PROFILE)["score"]        # DevOps (k8s/docker overlap)
    assert ml > devops > acct, f"ordering wrong: ml={ml} devops={devops} acct={acct}"


def test_empty_description_does_not_crash_and_uses_title():
    # Defensive: a job with no description must still score off the title, not
    # silently fall back to one constant placeholder for everything.
    a = score_job({"title": "Machine Learning Engineer", "description_snippet": ""}, PROFILE)["score"]
    b = score_job({"title": "Warehouse Associate", "description_snippet": ""}, PROFILE)["score"]
    assert a != b


def test_match_score_signature_direct():
    r = match_score(["Python", "ML"], "Machine Learning Engineer",
                    "python machine learning role", 0, ["ML Engineer"])
    assert 0 <= r["score"] <= 100 and r["reasons"]

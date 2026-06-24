"""Lever — AUTO-APPLY via public ATS API (assisted submit; hCaptcha-gated).

Discovery: app/jobs/providers/lever.py. Apply: assisted flow prefills the form;
the user completes the captcha + submit on the genuine Lever page. Treated as an
auto-apply-supported ATS for portal classification.
"""
from __future__ import annotations
from . import AUTO_APPLIED

NAME = "Lever"
DOMAIN = "lever.co"
AUTO_APPLY = True
DISCOVERY_API = "https://api.lever.co/v0/postings/{company}"


def application_mode() -> str:
    return AUTO_APPLIED

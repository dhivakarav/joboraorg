"""Anthropic Claude client wrapper for Jobora's AI features.

Centralises model choice, prompt caching, and the call surface so the feature
modules (resume intelligence, cover letters, career coach) stay small.

Prompt-caching strategy: every AI call shares the same stable system persona,
followed by the user's resume text. Both are marked with ``cache_control`` so
that repeated calls for the same user (ATS analysis → cover letter → coaching)
reuse the cached prefix instead of re-billing the resume every time. The
task-specific instruction is the only volatile part and lives in the user turn.

If ``ANTHROPIC_API_KEY`` is unset the wrapper reports ``available() == False`` and
callers fall back to the built-in heuristic engine.
"""
from __future__ import annotations

import json
from typing import Optional, Type

from ..config import settings

_PERSONA = (
    "You are Jobora's senior career strategist and technical recruiter. You give "
    "specific, honest, actionable advice grounded in how modern ATS systems and "
    "hiring managers actually screen candidates. You never invent facts about the "
    "candidate that aren't supported by their resume. Be concrete and concise."
)

_client = None
_init_done = False


def _get_client():
    global _client, _init_done
    if _init_done:
        return _client
    _init_done = True
    if not settings.ANTHROPIC_API_KEY:
        _client = None
        return None
    try:
        import anthropic
        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    except Exception:
        _client = None
    return _client


def available() -> bool:
    return _get_client() is not None


def _system_blocks(resume_text: str) -> list:
    """Stable persona + the user's resume, both cached as a reusable prefix."""
    blocks = [{"type": "text", "text": _PERSONA}]
    if resume_text:
        blocks.append({
            "type": "text",
            "text": "CANDIDATE RESUME (verbatim):\n\n" + resume_text,
            "cache_control": {"type": "ephemeral"},
        })
    else:
        blocks[0]["cache_control"] = {"type": "ephemeral"}
    return blocks


def generate_text(task: str, resume_text: str = "", max_tokens: int = 2048,
                  thinking: bool = False) -> Optional[str]:
    """Single-shot text generation. Returns None if AI is unavailable/errors."""
    client = _get_client()
    if client is None:
        return None
    try:
        kwargs = dict(
            model=settings.AI_MODEL,
            max_tokens=max_tokens,
            system=_system_blocks(resume_text),
            messages=[{"role": "user", "content": task}],
        )
        if thinking:
            kwargs["thinking"] = {"type": "adaptive"}
        resp = client.messages.create(**kwargs)
        return "".join(b.text for b in resp.content if b.type == "text").strip()
    except Exception as exc:
        print(f"[ai] generate_text failed: {exc}")
        return None


def generate_structured(task: str, schema: Type, resume_text: str = "",
                        max_tokens: int = 3072) -> Optional[object]:
    """Structured generation validated against a Pydantic model.

    Returns a validated instance, or None if AI is unavailable/errors.
    """
    client = _get_client()
    if client is None:
        return None
    try:
        resp = client.messages.parse(
            model=settings.AI_MODEL,
            max_tokens=max_tokens,
            system=_system_blocks(resume_text),
            messages=[{"role": "user", "content": task}],
            output_format=schema,
        )
        return resp.parsed_output
    except Exception as exc:
        print(f"[ai] generate_structured failed: {exc}")
        return None

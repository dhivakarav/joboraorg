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
    """True if ANY text-capable provider is configured (Anthropic or a free LLM)."""
    return _get_client() is not None or _any_free_llm_configured()


def _any_free_llm_configured() -> bool:
    return bool(
        settings.GROQ_API_KEY or settings.GEMINI_API_KEY
        or settings.OPENROUTER_API_KEY or settings.CEREBRAS_API_KEY
    )


# ── Free LLM providers (tried in order after Anthropic) ────────────────────────
# All via plain HTTP (httpx) so no extra SDKs are needed. Each returns the text
# on success or None on any failure, so generate_text() can fall through to the
# next provider and finally to the caller's heuristic fallback.

def _openai_compatible_chat(base_url: str, api_key: str, model: str,
                            system: str, task: str, max_tokens: int,
                            extra_headers: Optional[dict] = None) -> Optional[str]:
    """Groq / OpenRouter / Cerebras all speak the OpenAI /chat/completions API."""
    import httpx
    try:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        if extra_headers:
            headers.update(extra_headers)
        resp = httpx.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": task},
                ],
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        return (resp.json()["choices"][0]["message"]["content"] or "").strip() or None
    except Exception as exc:
        print(f"[ai] {base_url} failed: {exc}")
        return None


def _gemini_chat(api_key: str, model: str, system: str, task: str,
                 max_tokens: int) -> Optional[str]:
    """Google Gemini REST API (generateContent)."""
    import httpx
    try:
        resp = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": api_key},
            json={
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": task}]}],
                "generationConfig": {"maxOutputTokens": max_tokens},
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        cands = resp.json().get("candidates", [])
        if not cands:
            return None
        parts = cands[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        return text or None
    except Exception as exc:
        print(f"[ai] gemini failed: {exc}")
        return None


def _free_llm_generate(system: str, task: str, max_tokens: int) -> Optional[str]:
    """Try each configured free provider in order; return the first success."""
    if settings.GROQ_API_KEY:
        t = _openai_compatible_chat("https://api.groq.com/openai/v1",
                                    settings.GROQ_API_KEY, settings.GROQ_MODEL,
                                    system, task, max_tokens)
        if t:
            return t
    if settings.GEMINI_API_KEY:
        t = _gemini_chat(settings.GEMINI_API_KEY, settings.GEMINI_MODEL,
                         system, task, max_tokens)
        if t:
            return t
    if settings.OPENROUTER_API_KEY:
        t = _openai_compatible_chat("https://openrouter.ai/api/v1",
                                    settings.OPENROUTER_API_KEY, settings.OPENROUTER_MODEL,
                                    system, task, max_tokens,
                                    extra_headers={"HTTP-Referer": "https://jobora.app",
                                                   "X-Title": "Jobora"})
        if t:
            return t
    if settings.CEREBRAS_API_KEY:
        t = _openai_compatible_chat("https://api.cerebras.ai/v1",
                                    settings.CEREBRAS_API_KEY, settings.CEREBRAS_MODEL,
                                    system, task, max_tokens)
        if t:
            return t
    return None


def _plain_system(resume_text: str) -> str:
    """Flat system prompt for the free (OpenAI/Gemini) providers."""
    if resume_text:
        return _PERSONA + "\n\nCANDIDATE RESUME (verbatim):\n\n" + resume_text
    return _PERSONA


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
    """Single-shot text generation.

    Provider order: Anthropic Claude → Groq → Gemini → OpenRouter → Cerebras.
    Returns the first success, or None if no provider is configured/all fail
    (callers then use their built-in heuristic fallback).
    """
    client = _get_client()
    if client is not None:
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
            text = "".join(b.text for b in resp.content if b.type == "text").strip()
            if text:
                return text
        except Exception as exc:
            print(f"[ai] anthropic generate_text failed: {exc}")
            # fall through to free providers

    # Free-tier providers (no credit card) — first configured one that answers wins.
    return _free_llm_generate(_plain_system(resume_text), task, max_tokens)


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

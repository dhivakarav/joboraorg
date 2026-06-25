"""Application configuration.

Secrets are environment-only. There are NO secret values committed in this file.
In production (JOBORA_ENV=production) the app refuses to start unless JWT_SECRET
and CREDENTIAL_KEY are present and valid. In development, ephemeral keys are
generated per-process (with a loud warning) so local dev works without secrets —
those keys are NOT persisted and NOT safe for production.
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Minimal, dependency-free `.env` loader.

    Loads `KEY=VALUE` lines from a `.env` file (backend dir or repo root) into
    `os.environ` WITHOUT overriding variables already set in the real environment.
    Supports `#` comments (whole-line and inline) and quoted values. No-op if no
    `.env` exists. Needed because keyed providers (JSearch/Adzuna/…) read their
    keys via `os.getenv`, and nothing else loads the documented `.env`.
    """
    for candidate in (BASE_DIR / ".env", BASE_DIR.parent / ".env"):
        if not candidate.is_file():
            continue
        try:
            for raw in candidate.read_text().splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                if not key or key in os.environ:
                    continue   # real environment always wins
                val = val.strip()
                if len(val) >= 2 and val[0] in "\"'" and val[-1] == val[0]:
                    val = val[1:-1]                       # quoted literal
                else:
                    val = val.split(" #", 1)[0].rstrip()  # strip inline comment
                os.environ[key] = val
        except OSError:
            pass
        return   # first file found wins


_load_dotenv()

UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ENV = os.getenv("JOBORA_ENV", "development").lower()
IS_PROD = ENV == "production"

# Known-bad values that must never be accepted (e.g. an old committed default).
_BANNED_SECRETS = {
    "change-me-in-prod-super-secret-key-jobora",
    "emmG-v5ljuL_Y-1NMk8MDRKGvCxzHGCJzfp-NHf7-DQ=",
    "", "changeme", "secret", "change-me",
}


class ConfigError(RuntimeError):
    """Raised at startup when required secure configuration is missing/invalid."""


def _normalize_db_url(url: str) -> str:
    # Railway/Heroku/Render hand out legacy `postgres://`; SQLAlchemy 2.0 needs
    # `postgresql://`. Normalize so the same env var works on any platform.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


def _resolve_jwt_secret() -> str:
    val = os.getenv("JWT_SECRET", "")
    if val and val not in _BANNED_SECRETS:
        return val
    if IS_PROD:
        raise ConfigError(
            "JWT_SECRET is required in production and must not be a default/banned value. "
            "Generate one: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    import secrets
    print("[config] WARNING: JWT_SECRET not set — generating an EPHEMERAL dev secret. "
          "Tokens invalidate on restart. Do NOT use in production.", file=sys.stderr)
    return secrets.token_urlsafe(48)


def _resolve_credential_key() -> str:
    val = os.getenv("CREDENTIAL_KEY", "")
    from cryptography.fernet import Fernet
    if val and val not in _BANNED_SECRETS:
        try:
            Fernet(val.encode())  # validate it's a real Fernet key
            return val
        except Exception:
            raise ConfigError(
                "CREDENTIAL_KEY is not a valid Fernet key. Generate one: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
    if IS_PROD:
        raise ConfigError(
            "CREDENTIAL_KEY is required in production and must not be a default/banned value. "
            "Generate one: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    print("[config] WARNING: CREDENTIAL_KEY not set — generating an EPHEMERAL dev key. "
          "Stored portal credentials will NOT survive restart. Do NOT use in production.",
          file=sys.stderr)
    return Fernet.generate_key().decode()


class Settings:
    ENV = ENV
    IS_PROD = IS_PROD

    # Database
    DATABASE_URL: str = _normalize_db_url(
        os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'jobora.db'}")
    )

    # JWT — secret is env-only (see _resolve_jwt_secret); no committed default.
    JWT_SECRET: str = _resolve_jwt_secret()
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", str(60 * 24 * 7)))
    # H2: short-lived access token + long-lived refresh token (both revocable via
    # the per-user token_version).
    ACCESS_TOKEN_MINUTES: int = int(os.getenv("ACCESS_TOKEN_MINUTES", "60"))
    REFRESH_TOKEN_DAYS: int = int(os.getenv("REFRESH_TOKEN_DAYS", "7"))
    # Require email verification before login. ON by default; new signups must
    # verify their email. (Existing accounts were grandfathered to verified so
    # they aren't locked out — see the one-off grandfather step.)
    REQUIRE_EMAIL_VERIFICATION: bool = os.getenv("REQUIRE_EMAIL_VERIFICATION", "1") == "1"

    # Fernet key for encrypting portal credentials — env-only, validated.
    CREDENTIAL_KEY: str = _resolve_credential_key()

    # Admin bootstrap — env-only. If unset, NO admin is seeded (no default creds).
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")

    # ----- Rate limiting (Redis-backed via the cache layer) -----
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "1") == "1"
    RL_LOGIN_PER_MIN: int = int(os.getenv("RL_LOGIN_PER_MIN", "10"))      # per IP
    RL_REGISTER_PER_HOUR: int = int(os.getenv("RL_REGISTER_PER_HOUR", "10"))  # per IP
    RL_APPLY_PER_DAY: int = int(os.getenv("RL_APPLY_PER_DAY", "30"))      # per user
    RL_APPLY_BURST_PER_MIN: int = int(os.getenv("RL_APPLY_BURST_PER_MIN", "3"))  # per user
    RL_SEARCH_PER_MIN: int = int(os.getenv("RL_SEARCH_PER_MIN", "30"))    # per user

    # ----- Submission queue (H1) -----
    # Max concurrent browser-driven submissions across the worker.
    SUBMISSION_CONCURRENCY: int = int(os.getenv("SUBMISSION_CONCURRENCY", "2"))
    SUBMISSION_MAX_ATTEMPTS: int = int(os.getenv("SUBMISSION_MAX_ATTEMPTS", "3"))
    SUBMISSION_RETRY_DELAY: int = int(os.getenv("SUBMISSION_RETRY_DELAY", "10"))  # seconds
    # Run the in-process worker inside the API process (dev / single-node). In
    # production with REDIS_URL set, run a separate RQ worker instead.
    INPROCESS_WORKER: bool = os.getenv("INPROCESS_WORKER", "1") == "1"

    # ----- Billing / Razorpay (beta monetization) -----
    # NO test keys are shipped. Checkout/webhooks stay disabled until an operator
    # provides LIVE keys via env. Empty = billing inert (read-only plan info only).
    RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_WEBHOOK_SECRET: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

    # Uploads
    UPLOAD_DIR = UPLOAD_DIR
    MAX_RESUME_BYTES: int = 5 * 1024 * 1024  # 5MB

    # Password reset
    RESET_TOKEN_TTL_MINUTES: int = int(os.getenv("RESET_TOKEN_TTL_MINUTES", "60"))
    # With no SMTP configured, return the reset link in the API response so the
    # flow is usable in dev. Set EXPOSE_RESET_TOKEN=0 once real email is wired up.
    EXPOSE_RESET_TOKEN: bool = os.getenv("EXPOSE_RESET_TOKEN", "1") == "1"

    # Supported portals (legacy credential connections — kept for compatibility)
    PORTALS = ["LinkedIn", "Naukri", "Indeed", "Foundit", "Bayt", "JobStreet"]

    # ----- Cache (Redis with in-memory fallback) -----
    REDIS_URL: str = os.getenv("REDIS_URL", "")  # e.g. redis://localhost:6379/0

    # ----- Email / notifications (SMTP with console fallback) -----
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "Jobara <no-reply@jobara.app>")
    SMTP_TLS: bool = os.getenv("SMTP_TLS", "1") == "1"
    APP_BASE_URL: str = os.getenv("APP_BASE_URL", "http://localhost:5173")

    # ----- Real job aggregation -----
    JOB_CACHE_TTL: int = int(os.getenv("JOB_CACHE_TTL", "900"))        # 15 min
    PROVIDER_TIMEOUT: float = float(os.getenv("PROVIDER_TIMEOUT", "15"))
    PROVIDER_MIN_INTERVAL: float = float(os.getenv("PROVIDER_MIN_INTERVAL", "1.0"))
    # Hard wall-clock budget for a whole search across all providers. Slow/hanging
    # providers that don't finish in time are dropped from THIS search (graceful
    # degradation) so the request always returns well within client/proxy socket
    # timeouts — instead of hanging ~15s and getting the socket closed underneath us.
    SEARCH_DEADLINE_SECONDS: float = float(os.getenv("SEARCH_DEADLINE_SECONDS", "12"))
    # How big a raw pool each search pulls from the providers (before dedupe/filter/
    # display-trim). Decoupled from the UI display limit so we never leave free-tier
    # API volume on the table; providers still cap themselves at their pagination max.
    PROVIDER_FETCH_BUDGET: int = int(os.getenv("PROVIDER_FETCH_BUDGET", "200"))
    # Optional provider API keys (providers stay disabled until set).
    ADZUNA_APP_ID: str = os.getenv("ADZUNA_APP_ID", "")
    ADZUNA_APP_KEY: str = os.getenv("ADZUNA_APP_KEY", "")
    JOOBLE_API_KEY: str = os.getenv("JOOBLE_API_KEY", "")

    # ----- AI (Anthropic Claude) -----
    # If ANTHROPIC_API_KEY is unset, AI features fall back to a built-in
    # heuristic engine so the app still works end-to-end.
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    AI_MODEL: str = os.getenv("AI_MODEL", "claude-opus-4-8")

    # Logging / monitoring
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    APP_VERSION: str = os.getenv("APP_VERSION", "beta")
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")          # error tracking (gated)
    SENTRY_TRACES_SAMPLE_RATE: float = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0"))
    # PostHog product analytics (server-side capture; gated — no-op without key).
    POSTHOG_API_KEY: str = os.getenv("POSTHOG_API_KEY", "")
    POSTHOG_HOST: str = os.getenv("POSTHOG_HOST", "https://us.i.posthog.com")

    # Closed-beta gating: require an invite code at registration when enabled.
    BETA_INVITE_REQUIRED: bool = os.getenv("BETA_INVITE_REQUIRED", "0") == "1"

    # B2 — evidence: short-lived signed URLs for confirmation screenshots.
    EVIDENCE_URL_TTL: int = int(os.getenv("EVIDENCE_URL_TTL", "300"))   # 5 min
    # B2 — encrypt resume bytes + parsed PII at rest (uses CREDENTIAL_KEY).
    PII_ENCRYPTION: bool = os.getenv("PII_ENCRYPTION", "1") == "1"

    # CORS — comma-separated allowed origins. In production set CORS_ORIGINS to
    # your web app's URL(s), e.g. "https://app.jobara.com". Defaults cover local
    # dev. Same-origin deploys (nginx proxy) don't need this.
    CORS_ORIGINS = [
        o.strip() for o in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",") if o.strip()
    ]


settings = Settings()

"""Jobora FastAPI application entrypoint."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import settings
from .database import Base, SessionLocal, engine
from .logging_config import RequestLoggingMiddleware, request_id_ctx, setup_logging
from .models import User
from .routers import (
    admin,
    applications,
    apply,
    assisted,
    auth,
    dashboard,
    feedback,
    filters,
    jobs,
    profile,
    resume,
)
from .security import hash_password


def seed_admin():
    """Seed the admin account from environment ONLY.

    There are no default admin credentials. If ADMIN_EMAIL / ADMIN_PASSWORD are
    not set, no admin is created. A freshly-seeded admin must change its password
    on first login (must_change_password=True).
    """
    email = (settings.ADMIN_EMAIL or "").strip().lower()
    password = settings.ADMIN_PASSWORD or ""
    if not email or not password:
        import logging
        logging.getLogger("jobara").warning(
            "No admin seeded — set ADMIN_EMAIL and ADMIN_PASSWORD to bootstrap an admin.")
        return
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == email).first():
            db.add(User(
                full_name="Administrator",
                email=email,
                hashed_password=hash_password(password),
                status="approved",
                is_admin=True,
                must_change_password=True,
            ))
            db.commit()
    finally:
        db.close()


setup_logging(settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Local SQLite dev: create tables directly for zero-setup convenience.
    # Production (Postgres): schema is managed by Alembic migrations, applied by
    # the Docker entrypoint (`alembic upgrade head`) — don't create_all there.
    if engine.url.get_backend_name() == "sqlite":
        Base.metadata.create_all(bind=engine)
        from .database import ensure_sqlite_columns
        ensure_sqlite_columns()
    seed_admin()
    # Start the in-process submission worker (no-op if INPROCESS_WORKER=0 / using RQ).
    from .queue import start_worker
    start_worker()
    yield


def _init_sentry():
    """B2: error tracking. No-op unless SENTRY_DSN is set + sentry-sdk installed."""
    if not settings.SENTRY_DSN:
        return
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENV,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            send_default_pii=False,
        )
        logging.getLogger("jobara").info("Sentry initialized")
    except Exception as exc:
        logging.getLogger("jobara").warning(f"Sentry init failed: {exc}")


_init_sentry()

app = FastAPI(title="Jobora — Auto Job Applier", version="1.0.0", lifespan=lifespan)

_log = logging.getLogger("jobara.errors")


@app.exception_handler(StarletteHTTPException)
async def _http_exc_handler(request: Request, exc: StarletteHTTPException):
    # Pass through intended HTTP errors with a consistent envelope.
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "request_id": request_id_ctx.get()},
        headers=getattr(exc, "headers", None) or None,
    )


@app.exception_handler(RequestValidationError)
async def _validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": "Invalid request", "detail": exc.errors(),
                 "request_id": request_id_ctx.get()},
    )


@app.exception_handler(Exception)
async def _unhandled_handler(request: Request, exc: Exception):
    # Never leak internals/tracebacks. Log full detail server-side with request id.
    _log.exception("unhandled error", extra={"extra_fields": {"path": request.url.path}})
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "request_id": request_id_ctx.get()},
    )


app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# NOTE: payments/billing are OFF the active roadmap — the billing router is
# intentionally NOT registered. app/billing.py is parked (unused) but not deleted.
for r in (auth, resume, profile, filters, jobs, applications, apply, dashboard, admin, assisted, feedback):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/ready")
def ready():
    """Readiness probe: reports the status of every subsystem."""
    import os

    from sqlalchemy import text

    from .cache import cache

    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "database": {"ok": db_ok, "engine": engine.url.get_backend_name()},
        "cache": {"backend": cache.backend},
        "email": {"backend": "smtp" if settings.SMTP_HOST else "console"},
        "ai": {"enabled": bool(settings.ANTHROPIC_API_KEY)},
        "live_apply": os.getenv("JOBORA_LIVE", "0") == "1",
    }

"""Database engine, session, and base."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_sqlite_columns():
    """Idempotently add newly-introduced columns to an existing SQLite dev DB.

    `Base.metadata.create_all` creates missing tables but never alters existing
    ones, so a dev `jobora.db` created before a column was added would be missing
    it. Production uses Alembic; this is the zero-setup dev equivalent. Safe to
    run on every startup — it only adds columns that are absent.
    """
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    from sqlalchemy import inspect, text

    wanted = {
        "applications": {
            "application_id": "VARCHAR DEFAULT ''",
            "evidence_available": "BOOLEAN DEFAULT 0",
            "application_mode": "VARCHAR DEFAULT 'manual_link_provided'",
        },
        "users": {
            "plan": "VARCHAR DEFAULT 'free'",
            "plan_since": "DATETIME",
        },
        "job_filters": {
            "min_match_score": "INTEGER DEFAULT 50",
        },
    }
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, cols in wanted.items():
            if not insp.has_table(table):
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))

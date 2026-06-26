"""integrity: application_id + evidence_available, relabel Applied-without-evidence

Adds the canonical evidence columns and retires the misleading "Applied" label:
any row marked Applied/Submitted/Verified Submitted WITHOUT complete evidence is
relabelled to Tracked / Draft / unverified. A "Verified Submitted" row that lacks
evidence is downgraded to "Submitted".

Revision ID: a1b2c3d4e5f6
Revises: 71c6a7cbcb4e
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "71c6a7cbcb4e"
branch_labels = None
depends_on = None


def _has_column(bind, table, column):
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade():
    bind = op.get_bind()
    if not _has_column(bind, "applications", "application_id"):
        op.add_column("applications", sa.Column("application_id", sa.String(), server_default=""))
    if not _has_column(bind, "applications", "evidence_available"):
        op.add_column("applications", sa.Column("evidence_available", sa.Boolean(), server_default=sa.false()))

    # Backfill the canonical id from the legacy column where present.
    op.execute("""
        UPDATE applications
        SET application_id = COALESCE(NULLIF(application_id, ''), external_application_id)
        WHERE COALESCE(application_id, '') = ''
    """)

    # Evidence is "complete" only with id + confirmation_url + a stored artifact.
    # Mark evidence_available where the evidence JSON actually references a file.
    op.execute("""
        UPDATE applications
        SET evidence_available = TRUE
        WHERE (submission_evidence LIKE '%"screenshot"%'
            OR submission_evidence LIKE '%"screenshot_key"%'
            OR submission_evidence LIKE '%"html"%')
    """)

    # Downgrade any "Verified Submitted" that does not actually have full evidence.
    op.execute("""
        UPDATE applications
        SET submission_status = 'Submitted'
        WHERE submission_status = 'Verified Submitted'
          AND NOT (COALESCE(application_id,'') <> ''
                   AND COALESCE(confirmation_url,'') <> ''
                   AND evidence_available = TRUE)
    """)

    # Retire "Applied": any legacy Applied/Submitted lifecycle row WITHOUT a real
    # verified submission becomes Tracked / Draft / unverified.
    op.execute("""
        UPDATE applications
        SET status = 'Tracked',
            submission_status = 'Draft',
            evidence_available = FALSE
        WHERE status IN ('Applied', 'Submitted')
          AND NOT (submission_status = 'Verified Submitted'
                   AND COALESCE(application_id,'') <> ''
                   AND COALESCE(confirmation_url,'') <> ''
                   AND evidence_available = TRUE)
    """)


def downgrade():
    # Non-destructive: keep data, drop the added columns.
    bind = op.get_bind()
    if _has_column(bind, "applications", "evidence_available"):
        op.drop_column("applications", "evidence_available")
    if _has_column(bind, "applications", "application_id"):
        op.drop_column("applications", "application_id")

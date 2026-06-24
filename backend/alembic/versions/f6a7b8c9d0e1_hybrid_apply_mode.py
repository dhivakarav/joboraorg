"""hybrid apply model: application_mode + min_match_score

Adds:
  applications.application_mode  ('auto_applied' | 'manual_link_provided')
  job_filters.min_match_score    (0-100, default 50)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def _cols(bind, table):
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade():
    bind = op.get_bind()
    if "application_mode" not in _cols(bind, "applications"):
        op.add_column("applications", sa.Column(
            "application_mode", sa.String(), server_default="manual_link_provided"))
        op.create_index("ix_applications_application_mode", "applications", ["application_mode"])
    if "min_match_score" not in _cols(bind, "job_filters"):
        op.add_column("job_filters", sa.Column(
            "min_match_score", sa.Integer(), server_default="50"))


def downgrade():
    bind = op.get_bind()
    if "application_mode" in _cols(bind, "applications"):
        op.drop_index("ix_applications_application_mode", "applications")
        op.drop_column("applications", "application_mode")
    if "min_match_score" in _cols(bind, "job_filters"):
        op.drop_column("job_filters", "min_match_score")

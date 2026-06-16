"""cleanup: drop vestigial portal_credentials table

The "Job Portals" credential-connect feature was removed (its auto-apply
simulators were deleted; real apply is Track & Apply / Assisted Apply). This
drops the now-unused table.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def _has_table(bind, name):
    return name in sa.inspect(bind).get_table_names()


def upgrade():
    bind = op.get_bind()
    if _has_table(bind, "portal_credentials"):
        op.drop_table("portal_credentials")


def downgrade():
    bind = op.get_bind()
    if not _has_table(bind, "portal_credentials"):
        op.create_table(
            "portal_credentials",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
            sa.Column("portal_name", sa.String, nullable=False),
            sa.Column("encrypted_email", sa.Text, server_default=""),
            sa.Column("encrypted_password", sa.Text, server_default=""),
            sa.Column("is_active", sa.Boolean, server_default=sa.false()),
        )

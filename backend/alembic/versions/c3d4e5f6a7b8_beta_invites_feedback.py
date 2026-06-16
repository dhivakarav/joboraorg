"""beta: beta_invites + feedback tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def _has_table(bind, name):
    return name in sa.inspect(bind).get_table_names()


def upgrade():
    bind = op.get_bind()
    if not _has_table(bind, "beta_invites"):
        op.create_table(
            "beta_invites",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("code", sa.String, nullable=False, unique=True, index=True),
            sa.Column("note", sa.String, server_default=""),
            sa.Column("used_by_email", sa.String, server_default=""),
            sa.Column("used_at", sa.DateTime, nullable=True),
            sa.Column("created_at", sa.DateTime),
        )
    if not _has_table(bind, "feedback"):
        op.create_table(
            "feedback",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True, index=True),
            sa.Column("kind", sa.String, server_default="feedback"),
            sa.Column("message", sa.Text, nullable=False),
            sa.Column("page", sa.String, server_default=""),
            sa.Column("rating", sa.Integer, nullable=True),
            sa.Column("severity", sa.String, server_default=""),
            sa.Column("contact_email", sa.String, server_default=""),
            sa.Column("status", sa.String, server_default="open", index=True),
            sa.Column("created_at", sa.DateTime, index=True),
        )


def downgrade():
    bind = op.get_bind()
    if _has_table(bind, "feedback"):
        op.drop_table("feedback")
    if _has_table(bind, "beta_invites"):
        op.drop_table("beta_invites")

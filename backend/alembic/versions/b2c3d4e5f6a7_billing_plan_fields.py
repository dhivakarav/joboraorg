"""billing: users.plan + plan_since

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def _has_column(bind, table, column):
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade():
    bind = op.get_bind()
    if not _has_column(bind, "users", "plan"):
        op.add_column("users", sa.Column("plan", sa.String(), server_default="free"))
    if not _has_column(bind, "users", "plan_since"):
        op.add_column("users", sa.Column("plan_since", sa.DateTime(), nullable=True))


def downgrade():
    bind = op.get_bind()
    if _has_column(bind, "users", "plan_since"):
        op.drop_column("users", "plan_since")
    if _has_column(bind, "users", "plan"):
        op.drop_column("users", "plan")

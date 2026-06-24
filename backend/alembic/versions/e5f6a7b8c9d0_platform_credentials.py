"""recreate platform_credentials for Internshala live auto-submit (Option B)

Reintroduces a per-user, per-platform credential table (email + password stored
encrypted at rest via Fernet). Used only by the live auto-submission path, which
is itself gated behind JOBORA_LIVE=1 + explicit per-application approval.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-19
"""
from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def _has_table(bind, name):
    return name in sa.inspect(bind).get_table_names()


def upgrade():
    bind = op.get_bind()
    if _has_table(bind, "platform_credentials"):
        return
    op.create_table(
        "platform_credentials",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("platform", sa.String, nullable=False),
        sa.Column("encrypted_username", sa.Text, server_default=""),
        sa.Column("encrypted_password", sa.Text, server_default=""),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )
    op.create_index(
        "ix_platform_cred_user_platform",
        "platform_credentials", ["user_id", "platform"], unique=True,
    )
    op.create_index(
        "ix_platform_credentials_user_id", "platform_credentials", ["user_id"],
    )


def downgrade():
    bind = op.get_bind()
    if _has_table(bind, "platform_credentials"):
        op.drop_table("platform_credentials")

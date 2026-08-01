"""add persistent Telegram edit sessions

Revision ID: 20260801_02
Revises: 20260731_01
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260801_02"
down_revision: str | None = "20260731_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_edit_sessions",
        sa.Column("operator_id", sa.BigInteger(), nullable=False),
        sa.Column("email_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["email_id"],
            ["email_messages.id"],
            name=op.f("fk_telegram_edit_sessions_email_id_email_messages"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "operator_id",
            name=op.f("pk_telegram_edit_sessions"),
        ),
        sa.UniqueConstraint(
            "email_id",
            name=op.f("uq_telegram_edit_sessions_email_id"),
        ),
    )


def downgrade() -> None:
    op.drop_table("telegram_edit_sessions")

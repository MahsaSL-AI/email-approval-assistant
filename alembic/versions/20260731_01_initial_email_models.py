"""create initial email approval tables

Revision ID: 20260731_01
Revises:
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260731_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_messages",
        sa.Column("external_message_id", sa.String(length=998), nullable=False),
        sa.Column("sender", sa.String(length=320), nullable=False),
        sa.Column("recipient", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=998), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "received",
                "analyzed",
                "notified",
                "failed",
                name="email_processing_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="received",
            nullable=False,
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_messages")),
        sa.UniqueConstraint(
            "external_message_id", name=op.f("uq_email_messages_external_message_id")
        ),
    )
    op.create_index(
        "ix_email_messages_status_received_at",
        "email_messages",
        ["status", "received_at"],
        unique=False,
    )

    op.create_table(
        "email_analyses",
        sa.Column("email_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "sales",
                "support",
                "complaint",
                "payment",
                "logistics",
                "partnership",
                "spam",
                "other",
                name="email_category",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Enum(
                "low",
                "normal",
                "high",
                "urgent",
                name="email_priority",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("sentiment", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name=op.f("ck_email_analyses_confidence_range"),
        ),
        sa.ForeignKeyConstraint(
            ["email_id"],
            ["email_messages.id"],
            name=op.f("fk_email_analyses_email_id_email_messages"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_analyses")),
        sa.UniqueConstraint("email_id", name=op.f("uq_email_analyses_email_id")),
    )
    op.create_index(
        "ix_email_analyses_category_priority",
        "email_analyses",
        ["category", "priority"],
        unique=False,
    )

    op.create_table(
        "suggested_replies",
        sa.Column("email_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "editing",
                "approved",
                "rejected",
                "sent",
                "failed",
                name="reply_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("smtp_message_id", sa.String(length=998), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
            name=op.f("fk_suggested_replies_email_id_email_messages"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_suggested_replies")),
        sa.UniqueConstraint("email_id", name=op.f("uq_suggested_replies_email_id")),
        sa.UniqueConstraint(
            "smtp_message_id", name=op.f("uq_suggested_replies_smtp_message_id")
        ),
    )
    op.create_index(
        "ix_suggested_replies_status",
        "suggested_replies",
        ["status"],
        unique=False,
    )

    op.create_table(
        "processing_logs",
        sa.Column("email_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "level",
            sa.Enum(
                "info",
                "warning",
                "error",
                name="processing_log_level",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="info",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["email_id"],
            ["email_messages.id"],
            name=op.f("fk_processing_logs_email_id_email_messages"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_processing_logs")),
    )
    op.create_index(
        "ix_processing_logs_email_created",
        "processing_logs",
        ["email_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_processing_logs_email_created", table_name="processing_logs")
    op.drop_table("processing_logs")
    op.drop_index("ix_suggested_replies_status", table_name="suggested_replies")
    op.drop_table("suggested_replies")
    op.drop_index("ix_email_analyses_category_priority", table_name="email_analyses")
    op.drop_table("email_analyses")
    op.drop_index("ix_email_messages_status_received_at", table_name="email_messages")
    op.drop_table("email_messages")

"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

EMBEDDING_DIM = 768

# create_type=False: خودمان صراحتاً در upgrade() این typeها را می‌سازیم (checkfirst=True)،
# پس نباید بگذاریم op.create_table دوباره و خودکار همان CREATE TYPE را اجرا کند
# (وگرنه خطای DuplicateObject می‌گیرید — این باگ واقعی در تست اولیه پیدا و اصلاح شد).
item_status_enum = postgresql.ENUM(
    "pending", "duplicate", "rejected_auto", "pending_approval", "approved", "published", "rejected_by_admin",
    name="item_status",
    create_type=False,
)
content_type_enum = postgresql.ENUM(
    "news", "learn", "tool_discovery", "deep_dive", "reality_check", "hidden_gem", "fun",
    name="content_type",
    create_type=False,
)
llm_provider_enum = postgresql.ENUM("gemini", "groq", name="llm_provider", create_type=False)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    bind = op.get_bind()
    item_status_enum.create(bind, checkfirst=True)
    content_type_enum.create(bind, checkfirst=True)
    llm_provider_enum.create(bind, checkfirst=True)

    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(1024), nullable=False, unique=True),
        sa.Column("rating", sa.SmallInteger, nullable=False, server_default="3"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("is_blacklisted", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "raw_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("guid", sa.String(1024), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("duplicate_of_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("raw_items.id"), nullable=True),
        sa.Column("status", item_status_enum, nullable=False, server_default="pending"),
        sa.UniqueConstraint("source_id", "guid", name="uq_source_guid"),
    )
    op.create_index("ix_raw_items_fetched_at", "raw_items", ["fetched_at"])
    op.create_index("ix_raw_items_status", "raw_items", ["status"])
    # ایندکس تقریبی cosine (IVFFlat) روی embedding — بعد از پر شدن چند هزار رکورد اضافه کنید.
    # روی جدول خالی/کوچک، exact search (بدون ایندکس) هم به‌اندازه‌ی کافی سریع است:
    # op.execute("CREATE INDEX ix_raw_items_embedding ON raw_items USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")

    op.create_table(
        "evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("raw_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("raw_items.id"), nullable=False),
        sa.Column("llm_provider", llm_provider_enum, nullable=False),
        sa.Column("worth_posting", sa.Boolean, nullable=False),
        sa.Column("reject_reason", sa.Text, nullable=True),
        sa.Column("content_type", content_type_enum, nullable=True),
        sa.Column("score_educational", sa.SmallInteger, nullable=False),
        sa.Column("score_practical", sa.SmallInteger, nullable=False),
        sa.Column("score_freshness", sa.SmallInteger, nullable=False),
        sa.Column("score_interest", sa.SmallInteger, nullable=False),
        sa.Column("score_overall", sa.SmallInteger, nullable=False),
        sa.Column("hashtag", sa.String(32), nullable=True),
        sa.Column("rewritten_post", sa.Text, nullable=True),
        sa.Column("reasoning", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_evaluations_raw_item_id", "evaluations", ["raw_item_id"])

    op.create_table(
        "published_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "evaluation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evaluations.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("telegram_message_id", sa.BigInteger, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("published_posts")
    op.drop_table("evaluations")
    op.drop_index("ix_raw_items_status", table_name="raw_items")
    op.drop_index("ix_raw_items_fetched_at", table_name="raw_items")
    op.drop_table("raw_items")
    op.drop_table("sources")

    bind = op.get_bind()
    llm_provider_enum.drop(bind, checkfirst=True)
    content_type_enum.drop(bind, checkfirst=True)
    item_status_enum.drop(bind, checkfirst=True)

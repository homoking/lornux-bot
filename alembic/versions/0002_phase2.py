"""phase 2: source_type on sources, media_url on raw_items

Revision ID: 0002_phase2
Revises: 0001_initial
Create Date: 2026-08-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_phase2"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

source_type_enum = postgresql.ENUM("rss", "telegram_channel", name="source_type", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    source_type_enum.create(bind, checkfirst=True)

    op.add_column(
        "sources",
        sa.Column("source_type", source_type_enum, nullable=False, server_default="rss"),
    )
    op.add_column("raw_items", sa.Column("media_url", sa.String(1024), nullable=True))


def downgrade() -> None:
    op.drop_column("raw_items", "media_url")
    op.drop_column("sources", "source_type")

    bind = op.get_bind()
    source_type_enum.drop(bind, checkfirst=True)

"""
مدل‌های ORM.

جدول‌ها:
  - Source: منابع (RSS یا کانال تلگرام — نگاه کنید به SourceType)
  - RawItem: هر آیتم خام دریافتی از یک منبع
  - Evaluation: خروجی کامل LLM برای یک RawItem
  - PublishedPost: رکورد نهایی پستی که واقعاً در کانال منتشر شده
"""
import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

EMBEDDING_DIM = 768  # بعد بردار خروجی intfloat/multilingual-e5-base — اگر مدل embedding عوض شد، این را هم عوض کنید


def _pg_enum(enum_cls, name: str) -> Enum:
    """
    باگ واقعی که در تست پیدا شد: SQLAlchemy به‌طور پیش‌فرض هنگام ذخیره‌ی یک Python Enum
    از .name عضو استفاده می‌کند (مثلاً "PENDING")، نه .value ("pending") — درحالی‌که
    نوع ENUM ساخته‌شده در PostgreSQL (در alembic) فقط مقادیر lowercase را می‌شناسد.
    بدون values_callable، هر INSERT با خطای «invalid input value for enum» شکست می‌خورد.
    """
    return Enum(enum_cls, name=name, values_callable=lambda x: [e.value for e in x])


class ItemStatus(str, enum.Enum):
    PENDING = "pending"                    # تازه از منبع دریافت شده، هنوز پردازش نشده
    DUPLICATE = "duplicate"                # توسط dedup محلی تشخیص داده شد که تکراری است
    REJECTED_AUTO = "rejected_auto"        # LLM آن را worth_posting=false تشخیص داد یا زیر آستانه‌ی امتیاز بود
    PENDING_APPROVAL = "pending_approval"  # منتظر تصمیم ادمین در تلگرام
    APPROVED = "approved"                  # ادمین تأیید کرد، در صف انتشار
    PUBLISHED = "published"                # واقعاً در کانال منتشر شد
    REJECTED_BY_ADMIN = "rejected_by_admin"


class ContentType(str, enum.Enum):
    NEWS = "news"
    LEARN = "learn"
    TOOL_DISCOVERY = "tool_discovery"
    DEEP_DIVE = "deep_dive"
    REALITY_CHECK = "reality_check"
    HIDDEN_GEM = "hidden_gem"
    FUN = "fun"


class LLMProvider(str, enum.Enum):
    GEMINI = "gemini"
    GROQ = "groq"


class SourceType(str, enum.Enum):
    RSS = "rss"
    TELEGRAM_CHANNEL = "telegram_channel"


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    rating: Mapped[int] = mapped_column(SmallInteger, default=3)  # ۱ تا ۵، ادمین دستی تنظیم می‌کند
    source_type: Mapped[SourceType] = mapped_column(
        _pg_enum(SourceType, "source_type"), default=SourceType.RSS, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["RawItem"]] = relationship(back_populates="source")


class RawItem(Base):
    __tablename__ = "raw_items"
    __table_args__ = (UniqueConstraint("source_id", "guid", name="uq_source_guid"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), nullable=False)

    guid: Mapped[str] = mapped_column(String(1024), nullable=False)  # شناسه‌ی یکتای RSS entry (id یا link)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("raw_items.id"), nullable=True)
    media_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)  # از RSS enclosure یا og:image (Media Finder)

    status: Mapped[ItemStatus] = mapped_column(
        _pg_enum(ItemStatus, "item_status"), default=ItemStatus.PENDING, nullable=False
    )

    source: Mapped["Source"] = relationship(back_populates="items")
    evaluations: Mapped[list["Evaluation"]] = relationship(back_populates="raw_item", order_by="Evaluation.created_at")


class Evaluation(Base):
    """
    خروجی کامل یک فراخوانی LLM (طبق Master Prompt).
    عمداً هر evaluation یک رکورد جدید است، نه overwrite — چون هر بار که ادمین دکمه‌ی
    «بازنویسی» را بزند یک evaluation جدید ساخته می‌شود و تاریخچه برای دیباگ/بهبود پرامپت لازم است.
    """
    __tablename__ = "evaluations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("raw_items.id"), nullable=False)

    llm_provider: Mapped[LLMProvider] = mapped_column(_pg_enum(LLMProvider, "llm_provider"), nullable=False)

    worth_posting: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[ContentType | None] = mapped_column(_pg_enum(ContentType, "content_type"), nullable=True)

    score_educational: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    score_practical: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    score_freshness: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    score_interest: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    score_overall: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # همیشه در سرور دوباره محاسبه می‌شود

    hashtag: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rewritten_post: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    raw_item: Mapped["RawItem"] = relationship(back_populates="evaluations")


class PublishedPost(Base):
    __tablename__ = "published_posts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluations.id"), nullable=False, unique=True)
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    evaluation: Mapped["Evaluation"] = relationship()  # برای گزارش روزانه (digest.py) لازم است

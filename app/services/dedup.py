"""
تشخیص تکراری بودن و پیدا کردن پست‌های مرتبط با جستجوی نزدیک‌ترین همسایه در pgvector
(cosine distance).
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import ItemStatus, RawItem

DEDUP_LOOKBACK_DAYS = 7


async def find_duplicate(session: AsyncSession, embedding: list[float], exclude_item_id) -> RawItem | None:
    """
    نزدیک‌ترین آیتم قبلی را (از نظر embedding) برمی‌گرداند اگر شباهتش از آستانه بیشتر باشد؛
    در غیر این صورت None (یعنی آیتم جدید و منحصربه‌فرد است).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=DEDUP_LOOKBACK_DAYS)

    stmt = (
        select(RawItem, RawItem.embedding.cosine_distance(embedding).label("distance"))
        .where(RawItem.embedding.is_not(None))
        .where(RawItem.fetched_at >= cutoff)
        .where(RawItem.id != exclude_item_id)
        .order_by("distance")
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.first()
    if row is None:
        return None

    candidate, distance = row
    similarity = 1 - distance
    if similarity >= settings.dedup_similarity_threshold:
        return candidate
    return None


async def find_related_published(
    session: AsyncSession, embedding: list[float], exclude_item_id, limit: int = 2
) -> list[RawItem]:
    """
    Series Detector ساده: پست‌های منتشرشده‌ی قبلی که به این آیتم مرتبط‌اند (نه دقیقاً
    تکراری) را برمی‌گرداند. بازه‌ی شباهت عمداً بین related_threshold و dedup_threshold
    است — بالاتر از dedup یعنی تکراری واقعی (که جای دیگری هندل می‌شود)، پایین‌تر از
    related یعنی اصلاً مرتبط نیست.

    تست‌شده روی داده‌ی واقعی: فقط با پست‌های status=PUBLISHED مقایسه می‌کند — یک آیتم
    در انتظار تأیید که شباهت بالایی دارد ولی هنوز منتشر نشده، در این نتیجه ظاهر نمی‌شود.
    """
    stmt = (
        select(RawItem, RawItem.embedding.cosine_distance(embedding).label("distance"))
        .where(RawItem.embedding.is_not(None))
        .where(RawItem.status == ItemStatus.PUBLISHED)
        .where(RawItem.id != exclude_item_id)
        .order_by("distance")
        .limit(limit * 3)  # چند تا بیشتر می‌گیریم چون بعضی‌ها بعد از فیلتر threshold حذف می‌شوند
    )
    result = await session.execute(stmt)
    rows = result.all()

    related: list[RawItem] = []
    for candidate, distance in rows:
        similarity = 1 - distance
        if settings.related_similarity_threshold <= similarity < settings.dedup_similarity_threshold:
            related.append(candidate)
        if len(related) >= limit:
            break
    return related

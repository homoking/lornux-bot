"""
اجرا: python -m scripts.seed_sources

منابع اولیه‌ی RSS برای فاز ۱ (بدون کانال‌های تلگرام — طبق تصمیم فاز ۱).
لیست را با ذوق و منابع مدنظر خودتان ویرایش کنید؛ این فقط نقطه‌ی شروع است.
"""
import asyncio

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.logging import logger
from app.db.models import Source
from app.db.session import AsyncSessionLocal

# نکته: همه‌ی این URLها را قبل از استفاده‌ی واقعی خودتان چک کنید که فید معتبر و در دسترس است.
INITIAL_SOURCES: list[dict] = [
    {"name": "Hacker News (Front Page)", "url": "https://news.ycombinator.com/rss", "rating": 4},
    {"name": "GitHub Blog", "url": "https://github.blog/feed/", "rating": 5},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "rating": 3},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "rating": 3},
    {"name": "OpenAI Blog", "url": "https://openai.com/blog/rss.xml", "rating": 5},
]


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        for src in INITIAL_SOURCES:
            stmt = pg_insert(Source).values(**src).on_conflict_do_nothing(index_elements=["url"])
            await session.execute(stmt)
        await session.commit()
    logger.info(f"{len(INITIAL_SOURCES)} منبع بررسی/اضافه شد (تکراری‌ها نادیده گرفته شدند).")


if __name__ == "__main__":
    asyncio.run(seed())

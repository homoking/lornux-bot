"""
جمع‌آوری آیتم از فیدهای RSS. عمداً از httpx برای fetch استفاده می‌کنیم (نه اجازه دادن به
feedparser که خودش URL را بگیرد) چون timeout و user-agent را کنترل‌پذیر می‌کند.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser
import httpx

from app.core.logging import logger

USER_AGENT = "LornuxBot/1.0 (+https://t.me/lornux)"
FETCH_TIMEOUT_SECONDS = 15


@dataclass
class FeedEntry:
    guid: str
    title: str
    body: str
    url: str
    published_at: datetime | None
    image_url_hint: str | None = None  # از media:content/enclosure — رایگان چون در همان RSS بوده


def _extract_image_hint(entry) -> str | None:
    """اگر خود فید یک تصویر معرفی کرده باشد (رایج در فیدهای خبری)، همان را بردار —
    این کاملاً رایگان است چون داده از قبل در response موجود بوده، نیازی به fetch جدا نیست."""
    for media in (entry.get("media_content") or []):
        url = media.get("url")
        if url:
            return url

    for thumb in (entry.get("media_thumbnail") or []):
        url = thumb.get("url")
        if url:
            return url

    for enc in (entry.get("enclosures") or []):
        enc_type = enc.get("type", "")
        url = enc.get("href") or enc.get("url")
        if url and enc_type.startswith("image"):
            return url

    return None


async def fetch_feed_entries(feed_url: str) -> list[FeedEntry]:
    try:
        async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT}) as client:
            response = await client.get(feed_url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning(f"دریافت feed شکست خورد: {feed_url} — {exc}")
        return []

    parsed = feedparser.parse(response.content)
    if parsed.bozo and not parsed.entries:
        logger.warning(f"feed غیرقابل‌پارس: {feed_url} — {parsed.bozo_exception}")
        return []

    entries: list[FeedEntry] = []
    for entry in parsed.entries:
        guid = entry.get("id") or entry.get("link")
        if not guid:
            continue

        title = entry.get("title", "").strip()
        # اکثر فیدها summary یا content دارند؛ هرکدام موجود بود استفاده می‌کنیم
        body = ""
        if "content" in entry and entry["content"]:
            body = entry["content"][0].get("value", "")
        elif "summary" in entry:
            body = entry.get("summary", "")
        body = body.strip()

        url = entry.get("link", "")
        if not title or not body or not url:
            continue  # آیتم ناقص را نادیده بگیر — بهتر از پاس دادن داده‌ی ناقص به LLM

        published_at = None
        if getattr(entry, "published_parsed", None):
            published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

        entries.append(FeedEntry(
            guid=guid, title=title, body=body, url=url, published_at=published_at,
            image_url_hint=_extract_image_hint(entry),
        ))

    return entries

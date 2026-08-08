"""
Media Finder — پیدا کردن خودکار یک تصویر مناسب برای هر پست، کاملاً رایگان
(بدون API پولی، بدون تولید تصویر با AI).

استراتژی (به ترتیب اولویت):
  ۱) اگر RSS entry خودش یک تصویر (enclosure یا media:content) داده باشد، همان استفاده شود.
  ۲) در غیر این صورت، صفحه‌ی مقاله (item.url) واکشی و og:image آن استخراج شود.

تصمیم معماری: عمداً از BeautifulSoup استفاده نشده — یک regex ساده برای og:image کافی
است و یک وابستگی سنگین اضافه نمی‌کند. اگر در آینده نیاز به parsing پیچیده‌تر HTML شد
(مثلاً چند candidate تصویر)، این تصمیم را بازنگری کنید.

فراخوانی این تابع هزینه دارد (یک HTTP request اضافه)، پس فقط برای آیتم‌هایی که واقعاً
قرار است به ادمین نمایش داده شوند (worth_posting=true) صدا زده می‌شود، نه برای همه‌ی
آیتم‌های خام — این تصمیم در pipeline.py اعمال شده.
"""
import re

import httpx

from app.core.logging import logger

FETCH_TIMEOUT_SECONDS = 10
MAX_HTML_BYTES = 300_000  # فقط ابتدای صفحه را می‌خوانیم — og:image معمولاً در <head> است
USER_AGENT = "LornuxBot/1.0 (+https://t.me/lornux)"

_OG_IMAGE_PATTERNS = [
    re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', re.IGNORECASE),
]


def _looks_like_image_url(url: str) -> bool:
    return url.startswith(("http://", "https://")) and any(
        url.lower().split("?")[0].endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")
    )


async def find_og_image(article_url: str) -> str | None:
    """صفحه‌ی مقاله را واکشی و og:image آن را برمی‌گرداند. اگر پیدا نشد یا fetch شکست خورد، None."""
    try:
        async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT}) as client:
            async with client.stream("GET", article_url) as response:
                response.raise_for_status()
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= MAX_HTML_BYTES:
                        break
                html = b"".join(chunks).decode(errors="ignore")
    except httpx.HTTPError as exc:
        logger.warning(f"media_finder: fetch صفحه شکست خورد ({article_url}): {exc}")
        return None

    for pattern in _OG_IMAGE_PATTERNS:
        match = pattern.search(html)
        if match:
            return match.group(1)
    return None


async def resolve_media_url(article_url: str, rss_image_url: str | None) -> str | None:
    """نقطه‌ی ورود اصلی. اول تصویر RSS را چک می‌کند، بعد og:image را واکشی می‌کند."""
    if rss_image_url and _looks_like_image_url(rss_image_url):
        return rss_image_url

    return await find_og_image(article_url)

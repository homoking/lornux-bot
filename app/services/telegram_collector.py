"""
جمع‌آوری پیام از کانال‌های تلگرام دیگر با MTProto (Telethon) — یک اکانت کاربری واقعی،
نه Bot API.

⚠️ هشدار ریسک واقعی (قبل از فعال کردن حتماً بخوانید):
- این با Bot API فرق دارد: از یک اکانت شخصی/کاربری تلگرام استفاده می‌کند تا به کانال‌های
  دیگر (که بات شما در آن‌ها ادمین نیست) دسترسی پیدا کند.
- استفاده‌ی خودکار و مکرر از یک اکانت کاربری برای این کار می‌تواند با سیستم‌های ضد اسپم
  تلگرام تداخل داشته باشد و در موارد نادر به محدودیت یا تعلیق اکانت منجر شود.
- توصیه‌ی جدی: از یک شماره‌ی تلفن جداگانه (نه اکانت اصلی شخصی‌تان) استفاده کنید،
  فرکانس poll را پایین نگه دارید (پیش‌فرض پروژه: هر ۲۰ دقیقه)، و این قابلیت را فقط
  با آگاهی کامل فعال کنید (پیش‌فرض پروژه: MTPROTO_ENABLED=false).

راه‌اندازی (یک‌بار، خارج از این فایل، به‌صورت محلی نه در Docker):
  ۱. از https://my.telegram.org یک api_id و api_hash بگیرید.
  ۲. scripts/telegram_login.py را اجرا کنید تا session_string تولید شود.
  ۳. api_id، api_hash، session_string را در .env بگذارید و MTPROTO_ENABLED=true کنید.

⚠️ صداقت فنی: این ماژول در sandbox من قابل تست end-to-end نیست — نیاز به اکانت واقعی
تلگرام و دسترسی شبکه به api.telegram.org دارد که در sandbox من مجاز نیست. فقط از نظر
import/syntax و منطق dispatch بررسی شده. قبل از استفاده‌ی واقعی حتماً روی سیستم خودتان
تست کنید، و امضای دقیق متدهای Telethon را با مستندات فعلی (https://docs.telethon.dev)
تطبیق دهید.
"""
from datetime import timezone
from functools import lru_cache

from app.core.logging import logger
from app.services.rss_collector import FeedEntry

MESSAGES_PER_POLL = 20  # محدود نگه داشتن حجم درخواست — کاهش ریسک flood-wait


@lru_cache(maxsize=1)
def _get_client():
    """
    Telethon عمداً اینجا (نه در بالای فایل) import می‌شود تا اگر MTPROTO_ENABLED=false
    باشد، اصلاً نیازی به نصب telethon برای کسانی که از این فیچر استفاده نمی‌کنند نباشد.
    """
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    from app.config import settings

    if not (settings.telegram_api_id and settings.telegram_api_hash and settings.telegram_session_string):
        raise RuntimeError(
            "MTPROTO_ENABLED=true است اما TELEGRAM_API_ID/API_HASH/SESSION_STRING در .env تنظیم نشده‌اند."
        )

    return TelegramClient(
        StringSession(settings.telegram_session_string),
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )


async def fetch_channel_entries(pseudo_url: str) -> list[FeedEntry]:
    """pseudo_url به‌شکل 'tg://<channel_username>' است (نگاه کنید به source_admin.py)."""
    channel_username = pseudo_url.removeprefix("tg://")

    try:
        client = _get_client()
    except RuntimeError as exc:
        logger.error(f"telegram_collector: {exc}")
        return []

    entries: list[FeedEntry] = []
    try:
        async with client:
            channel = await client.get_entity(channel_username)
            async for message in client.iter_messages(channel, limit=MESSAGES_PER_POLL):
                if not message.text:
                    continue  # پیام بدون متن (فقط عکس/استیکر تنها) را رد کن

                published_at = message.date.astimezone(timezone.utc) if message.date else None
                entries.append(FeedEntry(
                    guid=f"tg:{channel_username}:{message.id}",
                    title=message.text.split("\n", 1)[0][:200],
                    body=message.text,
                    url=f"https://t.me/{channel_username}/{message.id}",
                    published_at=published_at,
                    image_url_hint=None,  # دانلود مستقیم عکس تلگرام فعلاً پشتیبانی نمی‌شود
                ))
    except Exception as exc:  # noqa: BLE001 — از FloodWaitError تا خطای شبکه؛ نباید کل poll را متوقف کند
        logger.error(f"telegram_collector: خطا در خواندن کانال {channel_username}: {exc}")
        return []

    return entries

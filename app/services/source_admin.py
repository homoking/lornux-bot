"""
منطق مدیریت منابع — از handler های بات جدا شده تا بدون نیاز به شبیه‌سازی تلگرام
قابل تست باشد. هر تابع خطاهای قابل‌فهم (ValueError / LookupError) می‌دهد که handler
مستقیماً به‌عنوان پیام خطا به ادمین نشان می‌دهد.
"""
from urllib.parse import urlparse

from sqlalchemy import String, cast, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Source, SourceType

SHORT_ID_LEN = 8


def short_id(source: Source) -> str:
    return str(source.id)[:SHORT_ID_LEN]


def _validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"لینک نامعتبر است: {url} (باید با http:// یا https:// شروع شود)")
    return url


def _validate_rating(rating: int) -> int:
    if not (1 <= rating <= 5):
        raise ValueError("امتیاز باید عددی بین ۱ تا ۵ باشد")
    return rating


async def add_source(session: AsyncSession, url: str, name: str | None = None, rating: int = 3) -> Source:
    url = _validate_url(url)
    rating = _validate_rating(rating)
    if not name:
        name = urlparse(url).netloc  # اگر اسم داده نشد، از دامنه استفاده کن

    source = Source(name=name, url=url, rating=rating, source_type=SourceType.RSS)
    # از SAVEPOINT (begin_nested) استفاده می‌کنیم، نه session.rollback() ساده — چون
    # rollback() کل session را برمی‌گرداند و هر تغییر دیگری که در همین session (قبل از
    # commit) انجام شده را هم پاک می‌کند. این باگ واقعی در تست پیدا شد: بعد از رد شدن یک
    # URL تکراری، منبع قبلاً اضافه‌شده هم ناپدید می‌شد. با begin_nested فقط همین insert
    # ناموفق rollback می‌شود.
    try:
        async with session.begin_nested():
            session.add(source)
            await session.flush()
    except IntegrityError as exc:
        raise ValueError(f"این منبع قبلاً اضافه شده: {url}") from exc
    return source


async def add_telegram_channel_source(
    session: AsyncSession, channel_username: str, name: str | None = None, rating: int = 3
) -> Source:
    """
    اضافه کردن یک کانال تلگرام به‌عنوان منبع (نیازمند MTPROTO_ENABLED=true در .env).
    channel_username بدون @ ذخیره می‌شود؛ در ستون url به‌شکل شبه‌URL 'tg://<username>' نگه‌داری می‌شود
    تا سازگار با unique constraint موجود روی url بماند (بدون نیاز به تغییر schema).
    """
    channel_username = channel_username.lstrip("@").strip()
    if not channel_username:
        raise ValueError("نام کاربری کانال نمی‌تواند خالی باشد")
    rating = _validate_rating(rating)

    pseudo_url = f"tg://{channel_username}"
    source = Source(
        name=name or channel_username, url=pseudo_url, rating=rating, source_type=SourceType.TELEGRAM_CHANNEL,
    )
    try:
        async with session.begin_nested():
            session.add(source)
            await session.flush()
    except IntegrityError as exc:
        raise ValueError(f"این کانال قبلاً اضافه شده: {channel_username}") from exc
    return source


async def list_sources(session: AsyncSession) -> list[Source]:
    stmt = select(Source).order_by(Source.created_at)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def resolve_source(session: AsyncSession, short: str) -> Source:
    short = short.strip().lower()
    if len(short) < 4:
        raise LookupError("شناسه باید حداقل ۴ کاراکتر باشد (برای جلوگیری از ابهام)")

    stmt = select(Source).where(cast(Source.id, String).ilike(f"{short}%"))
    result = await session.execute(stmt)
    matches = list(result.scalars().all())

    if not matches:
        raise LookupError(f"منبعی با شناسه‌ی «{short}» پیدا نشد")
    if len(matches) > 1:
        raise LookupError(f"شناسه‌ی «{short}» بین چند منبع مشترک است — شناسه‌ی دقیق‌تری بدهید")
    return matches[0]


async def set_active(session: AsyncSession, short: str, active: bool) -> Source:
    source = await resolve_source(session, short)
    source.is_active = active
    await session.flush()
    return source


async def set_blacklisted(session: AsyncSession, short: str, blacklisted: bool) -> Source:
    source = await resolve_source(session, short)
    source.is_blacklisted = blacklisted
    await session.flush()
    return source


async def set_rating(session: AsyncSession, short: str, rating: int) -> Source:
    rating = _validate_rating(rating)
    source = await resolve_source(session, short)
    source.rating = rating
    await session.flush()
    return source

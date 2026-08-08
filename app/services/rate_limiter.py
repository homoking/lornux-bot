"""
Rate limiter ساده مبتنی بر Redis (fixed-window counter) — برای رعایت سقف RPM/RPD
free tier هر LLM provider. این حیاتی است چون بدون آن، اولین burst از آیتم‌های صف‌شده
بلافاصله با خطای 429 مواجه می‌شود.

طراحی عمداً ساده نگه داشته شده (fixed window، نه sliding/token-bucket دقیق) چون برای
این حجم (چند ده call در روز) کافی است و پیچیدگی اضافه توجیه ندارد.
"""
from datetime import datetime, timezone

from redis.asyncio import Redis

from app.services.llm.base import LLMRateLimitExceeded


class RedisRateLimiter:
    def __init__(self, redis: Redis, provider: str, rpm_limit: int, rpd_limit: int) -> None:
        self._redis = redis
        self._provider = provider
        self._rpm_limit = rpm_limit
        self._rpd_limit = rpd_limit

    async def acquire(self) -> None:
        """
        اگر ظرفیت باقی مانده باشد، شمارنده را افزایش می‌دهد و برمی‌گردد.
        در غیر این صورت LLMRateLimitExceeded raise می‌کند (caller باید provider دیگری
        امتحان کند یا task را با تأخیر retry کند).
        """
        now = datetime.now(timezone.utc)
        minute_key = f"ratelimit:{self._provider}:rpm:{now.strftime('%Y%m%d%H%M')}"
        day_key = f"ratelimit:{self._provider}:rpd:{now.strftime('%Y%m%d')}"

        rpm_count = await self._redis.incr(minute_key)
        if rpm_count == 1:
            await self._redis.expire(minute_key, 90)  # کمی بیشتر از ۶۰ ثانیه برای اطمینان

        rpd_count = await self._redis.incr(day_key)
        if rpd_count == 1:
            await self._redis.expire(day_key, 60 * 60 * 26)  # کمی بیشتر از ۲۴ ساعت

        if rpm_count > self._rpm_limit or rpd_count > self._rpd_limit:
            # شمارنده را برنمی‌گردانیم عمداً؛ چون افزایش قبلاً ثبت شده و درست است که در آن
            # window شمرده شود، حتی اگر همین call رد شود (جلوگیری از race condition پیچیده‌تر).
            raise LLMRateLimitExceeded(
                f"{self._provider}: rpm={rpm_count}/{self._rpm_limit} rpd={rpd_count}/{self._rpd_limit}"
            )

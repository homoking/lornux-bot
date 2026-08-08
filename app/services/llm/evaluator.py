"""
Orchestrator: اول Gemini را امتحان می‌کند، اگر quota پر بود یا خطای پایدار داد، به Groq
سوییچ می‌کند. این تنها جایی است که بقیه‌ی کد (Celery task) باید با آن کار کند —
جزئیات هر provider را نمی‌بیند.
"""
from redis.asyncio import Redis

from app.config import settings
from app.core.logging import logger
from app.schemas.content import LornuxEvaluation
from app.services.llm.base import LLMRateLimitExceeded, LLMResponseError
from app.services.llm.gemini_client import GeminiClient
from app.services.llm.groq_client import GroqClient
from app.services.llm.prompt import build_user_prompt
from app.services.rate_limiter import RedisRateLimiter


class AllProvidersFailedError(Exception):
    """هم Gemini و هم Groq شکست خوردند — این آیتم فعلاً باید pending بماند برای retry بعدی."""


class LornuxEvaluator:
    def __init__(self, redis: Redis) -> None:
        rate_limiter = RedisRateLimiter(
            redis=redis,
            provider="gemini",
            rpm_limit=settings.gemini_rpm_limit,
            rpd_limit=settings.gemini_rpd_limit,
        )
        self._gemini = GeminiClient(rate_limiter=rate_limiter)
        self._groq = GroqClient()

    async def evaluate_item(
        self,
        source_name: str,
        source_url: str,
        published_at: str,
        source_rating: int,
        title: str,
        body: str,
    ) -> tuple[LornuxEvaluation, str]:
        """برمی‌گرداند: (evaluation, provider_name_used)"""
        user_prompt = build_user_prompt(source_name, source_url, published_at, source_rating, title, body)

        try:
            evaluation = await self._gemini.evaluate(user_prompt)
            return evaluation, self._gemini.provider_name
        except LLMRateLimitExceeded as exc:
            logger.warning(f"Gemini rate limit پر شد، سوییچ به Groq — {exc}")
        except LLMResponseError as exc:
            logger.warning(f"Gemini خطای پایدار داد، سوییچ به Groq — {exc}")

        try:
            evaluation = await self._groq.evaluate(user_prompt)
            return evaluation, self._groq.provider_name
        except (LLMRateLimitExceeded, LLMResponseError) as exc:
            logger.error(f"Groq هم شکست خورد — {exc}")
            raise AllProvidersFailedError(str(exc)) from exc

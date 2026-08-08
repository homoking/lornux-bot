"""Interface مشترک برای همه‌ی LLM providerها تا evaluator بدون دانستن جزئیات هرکدام کار کند."""
from abc import ABC, abstractmethod

from app.schemas.content import LornuxEvaluation


class LLMRateLimitExceeded(Exception):
    """وقتی quota (RPM یا RPD) پر شده — evaluator باید provider بعدی را امتحان کند."""


class LLMResponseError(Exception):
    """خروجی مدل قابل parse/validate نبود (بعد از retryهای داخلی)."""


class BaseLLMClient(ABC):
    provider_name: str

    @abstractmethod
    async def evaluate(self, user_prompt: str) -> LornuxEvaluation:
        """
        یک آیتم را ارزیابی می‌کند و LornuxEvaluation معتبر برمی‌گرداند.
        در صورت پر بودن quota: LLMRateLimitExceeded
        در صورت خطای پایدار parse/validate بعد از retry: LLMResponseError
        """
        raise NotImplementedError

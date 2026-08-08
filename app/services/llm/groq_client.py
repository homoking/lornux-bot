"""
کلاینت Groq — provider دوم (fallback) وقتی Gemini quota تمام شده یا خطا داده.

⚠️ Groq فقط "json_object" mode را تضمین می‌کند (خروجی JSON معتبر است، اما بر خلاف Gemini
schema دقیق را enforce نمی‌کند) — به همین دلیل اعتبارسنجی با Pydantic اینجا حیاتی‌تر است.
همچنین کیفیت فارسیِ مدل‌های Llama معمولاً از Gemini ضعیف‌تر است؛ توصیه می‌شود بعد از چند
هفته استفاده‌ی واقعی، خروجی این provider را جداگانه از نظر کیفیت متن فارسی ارزیابی کنید.
"""
import json

from groq import AsyncGroq
from pydantic import ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings
from app.core.logging import logger
from app.schemas.content import LornuxEvaluation
from app.services.llm.base import BaseLLMClient, LLMResponseError
from app.services.llm.prompt import FEW_SHOT_EXAMPLES, SYSTEM_PROMPT


class GroqClient(BaseLLMClient):
    provider_name = "groq"

    def __init__(self) -> None:
        self._client = AsyncGroq(api_key=settings.groq_api_key)
        self._messages_base = self._build_messages()

    def _build_messages(self) -> list[dict]:
        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for example in FEW_SHOT_EXAMPLES:
            messages.append({"role": "user", "content": example["user"]})
            messages.append({"role": "assistant", "content": example["model"]})
        return messages

    @retry(
        retry=retry_if_exception_type((json.JSONDecodeError, ValidationError)),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    async def _call_model(self, user_prompt: str) -> LornuxEvaluation:
        messages = self._messages_base + [{"role": "user", "content": user_prompt}]

        response = await self._client.chat.completions.create(
            model=settings.groq_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.6,
            max_tokens=2000,
        )

        raw_text = response.choices[0].message.content
        data = json.loads(raw_text)
        return LornuxEvaluation.model_validate(data)

    async def evaluate(self, user_prompt: str) -> LornuxEvaluation:
        # توجه: عمداً rate limiter مشابه Gemini اینجا نگذاشتیم — Groq معمولاً فقط به‌عنوان
        # fallback با حجم کم فراخوانی می‌شود. اگر حجم استفاده از آن زیاد شد، همان الگوی
        # RedisRateLimiter را اینجا هم اضافه کنید.
        try:
            return await self._call_model(user_prompt)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.error(f"Groq: خروجی نامعتبر بعد از retry — {exc}")
            raise LLMResponseError(str(exc)) from exc

"""
کلاینت Gemini (google-genai SDK — یکپارچه، جایگزین SDK قدیمی‌تر google-generativeai).

⚠️ نکته‌ی صداقت فنی: SDKهای گوگل به‌سرعت تغییر می‌کنند. امضای دقیق متدها/پارامترها را
قبل از اجرای واقعی با مستندات فعلی (https://ai.google.dev/gemini-api/docs) تطبیق دهید.
منطق کلی (system_instruction + few-shot history + response_schema برای JSON structured
output) درست است، اما نام دقیق پارامترها ممکن است در نسخه‌ی نصب‌شده‌ی شما کمی فرق کند.
"""
import json

from google import genai
from google.genai import types
from pydantic import ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings
from app.core.logging import logger
from app.schemas.content import LornuxEvaluation
from app.services.llm.base import BaseLLMClient, LLMResponseError
from app.services.llm.prompt import FEW_SHOT_EXAMPLES, SYSTEM_PROMPT
from app.services.rate_limiter import RedisRateLimiter


class GeminiClient(BaseLLMClient):
    provider_name = "gemini"

    def __init__(self, rate_limiter: RedisRateLimiter) -> None:
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._rate_limiter = rate_limiter
        self._history = self._build_history()

    def _build_history(self) -> list[types.Content]:
        history: list[types.Content] = []
        for example in FEW_SHOT_EXAMPLES:
            history.append(types.Content(role="user", parts=[types.Part(text=example["user"])]))
            history.append(types.Content(role="model", parts=[types.Part(text=example["model"])]))
        return history

    @retry(
        retry=retry_if_exception_type((json.JSONDecodeError, ValidationError)),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    async def _call_model(self, user_prompt: str) -> LornuxEvaluation:
        contents = self._history + [types.Content(role="user", parts=[types.Part(text=user_prompt)])]

        response = await self._client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.6,
                max_output_tokens=2000,
            ),
        )

        raw_text = response.text
        data = json.loads(raw_text)
        return LornuxEvaluation.model_validate(data)

    async def evaluate(self, user_prompt: str) -> LornuxEvaluation:
        # rate limit را قبل از هر تلاش (حتی retry داخلی) اعمال می‌کنیم تا واقعاً از سقف رد نشویم
        await self._rate_limiter.acquire()
        try:
            return await self._call_model(user_prompt)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.error(f"Gemini: خروجی نامعتبر بعد از retry — {exc}")
            raise LLMResponseError(str(exc)) from exc

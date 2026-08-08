"""
Schema خروجی LLM — دقیقاً منطبق با JSON schema تعریف‌شده در lornux_master_prompt.md
هم برای response_schema گوگل/Groq استفاده می‌شود، هم برای اعتبارسنجی خروجی بعد از parse.
"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ALLOWED_HASHTAGS = {
    "#AI", "#Programming", "#Python", "#Backend", "#Frontend",
    "#DevOps", "#CyberSecurity", "#Linux", "#Gaming", "#GameDev",
    "#Hardware", "#GPU", "#CPU", "#Cloud", "#Database",
    "#OpenSource", "#Startup", "#Tool", "#Tutorial",
}

ContentTypeLiteral = Literal[
    "news", "learn", "tool_discovery", "deep_dive", "reality_check", "hidden_gem", "fun"
]


class ScoreBreakdown(BaseModel):
    educational_value: int = Field(ge=0, le=100)
    practical_value: int = Field(ge=0, le=100)
    freshness: int = Field(ge=0, le=100)
    interest: int = Field(ge=0, le=100)
    # عمداً بدون محدودیت: اگر مدل عدد اشتباهی برگرداند (مثلاً >100)، نباید کل خروجی reject شود —
    # همین فیلد قرار است در model_post_init بازمحاسبه و جایگزین شود (باگی که در تست واقعی پیدا شد:
    # بدون این تغییر، overall=999 از طرف مدل قبل از رسیدن به لایه‌ی اصلاح، کل خروجی را reject می‌کرد).
    overall: int

    def recompute_overall(self) -> int:
        """
        قانون دفاعی: به overall محاسبه‌شده‌ی خود مدل اعتماد نمی‌کنیم چون LLMها گاهی
        در محاسبات عددی ساده خطا می‌کنند. این مقدار همیشه در سرور بازمحاسبه و جایگزین می‌شود.
        وزن‌ها دقیقاً مطابق rubric تعریف‌شده در master prompt است.
        """
        return round(
            self.educational_value * 0.35
            + self.practical_value * 0.30
            + self.freshness * 0.15
            + self.interest * 0.20
        )


class LornuxEvaluation(BaseModel):
    worth_posting: bool
    reject_reason: str | None = None
    content_type: ContentTypeLiteral | None = None
    score: ScoreBreakdown
    hashtag: str | None = None
    rewritten_post: str | None = None
    reasoning: str

    @field_validator("hashtag")
    @classmethod
    def hashtag_must_be_allowed(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_HASHTAGS:
            raise ValueError(f"هشتگ '{v}' در لیست مجاز نیست")
        return v

    def model_post_init(self, __context) -> None:
        # همیشه overall را با فرمول سرور بازنویسی کن (لایه‌ی دفاعی در برابر خطای محاسباتی مدل)
        object.__setattr__(self.score, "overall", self.score.recompute_overall())

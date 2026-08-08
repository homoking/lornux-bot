"""
تنظیمات مرکزی پروژه — همه‌ی مقادیر از Environment Variables خوانده می‌شوند.
هیچ مقدار حساس (API key، توکن) نباید hardcode شود.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Database ---
    database_url: str
    database_url_sync: str

    # --- Redis / Celery ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Telegram ---
    telegram_bot_token: str
    telegram_admin_chat_id: int
    telegram_channel_id: str

    # --- LLM providers ---
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"
    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"

    # --- Rate limiting (این اعداد را با AI Studio خودتان چک کنید؛ Google بدون اطلاع قبلی تغییرشان می‌دهد) ---
    gemini_rpm_limit: int = 15
    gemini_rpd_limit: int = 1500

    # --- Pipeline tuning ---
    embedding_model_name: str = "intfloat/multilingual-e5-base"
    dedup_similarity_threshold: float = 0.92
    related_similarity_threshold: float = 0.80  # بین این و dedup یعنی «مرتبط»، نه «تکراری» (Series Detector)
    score_worth_posting_threshold: int = 65
    poll_interval_minutes: int = 20
    digest_hour_utc: int = 20  # ساعت ارسال گزارش روزانه (UTC) به ادمین

    # --- Media Finder (فاز ۲) ---
    media_enabled: bool = True  # اگر False شود، هیچ تلاشی برای پیدا کردن عکس نمی‌شود (فقط متن)

    # --- Telegram Channel Collection via MTProto (فاز ۲، اختیاری و پیش‌فرض خاموش) ---
    # ریسک واقعی دارد: استفاده از اکانت شخصی برای خواندن کانال‌های دیگر می‌تواند با
    # محدودیت‌های ضدِ اسپم تلگرام تداخل داشته باشد. فقط با آگاهی کامل فعال کنید
    # (نگاه کنید به README و app/services/telegram_collector.py).
    mtproto_enabled: bool = False
    telegram_api_id: int | None = None
    telegram_api_hash: str | None = None
    telegram_session_string: str | None = None

    # --- Branding ---
    channel_signature: str = "🚀 Lornux | Technology, AI & Future"

    # --- Admin API (فاز آخر) ---
    admin_api_key: str  # اجباری، بدون پیش‌فرض — یک secret واقعی است


settings = Settings()

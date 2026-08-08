"""
نمونه‌ی مرکزی Bot و Dispatcher — هم توسط entrypoint اصلی بات (polling) و هم توسط
Celery task ها (برای فرستادن پیام تأیید به ادمین) استفاده می‌شود.
"""
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import settings

bot = Bot(
    token=settings.telegram_bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()

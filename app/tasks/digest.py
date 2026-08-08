"""تسک Celery برای ارسال گزارش روزانه به ادمین (نه به کانال — نگاه کنید به services/digest.py)."""
import asyncio

from app.config import settings
from app.core.logging import logger
from app.db.session import AsyncSessionLocal
from app.services.digest import build_daily_digest_text
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.digest.daily_digest_task")
def daily_digest_task() -> None:
    asyncio.run(_send_daily_digest())


async def _send_daily_digest() -> None:
    async with AsyncSessionLocal() as session:
        text = await build_daily_digest_text(session)

    if text is None:
        logger.info("daily_digest: امروز هیچ پستی منتشر نشده، گزارشی فرستاده نمی‌شود")
        return

    from app.bot.bot import bot

    await bot.send_message(chat_id=settings.telegram_admin_chat_id, text=text)
    logger.info("daily_digest: گزارش روزانه فرستاده شد")

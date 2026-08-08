"""Entrypoint بات (long polling). اجرا: python -m app.bot.main"""
import asyncio

from app.bot.bot import bot, dp
from app.bot.handlers.approval import router as approval_router
from app.bot.handlers.sources import router as sources_router
from app.core.logging import logger


async def main() -> None:
    dp.include_router(sources_router)
    dp.include_router(approval_router)
    logger.info("Lornux bot در حال شروع (long polling)...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

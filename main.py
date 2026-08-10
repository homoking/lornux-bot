import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, ErrorEvent
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNotFound,
)

from config import BOT_TOKEN, TARGET_CHANNEL_ID
from database.connection import init_db
from middlewares.auth import AdminAuthMiddleware
from handlers import admin_panel, review, channel_events
from scraper.task import scraper_loop


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


async def setup_bot_commands(bot: Bot):
    commands = [
        BotCommand(
            command="start",
            description="🚀 باز کردن پنل مدیریت",
        )
    ]

    try:
        await bot.set_my_commands(commands)
    except TelegramAPIError as exc:
        logger.warning(
            "Could not set Telegram bot commands: %s",
            exc,
        )


async def validate_target_channel(bot: Bot):
    if not TARGET_CHANNEL_ID:
        logger.error(
            "TARGET_CHANNEL_ID is missing or invalid."
        )
        return False

    try:
        me = await bot.get_me()

        chat = await bot.get_chat(
            TARGET_CHANNEL_ID
        )

        member = await bot.get_chat_member(
            TARGET_CHANNEL_ID,
            me.id,
        )

        can_post = getattr(
            member,
            "can_post_messages",
            None,
        )

        logger.info(
            "Target channel found: %s (%s)",
            getattr(chat, "title", "unknown"),
            TARGET_CHANNEL_ID,
        )

        logger.info(
            "Bot channel status: %s | can_post_messages=%s",
            member.status,
            can_post,
        )

        if can_post is False:
            logger.error(
                "Bot is in the target channel but cannot post messages."
            )
            return False

        return True

    except (
        TelegramNotFound,
        TelegramForbiddenError,
        TelegramBadRequest,
    ) as exc:
        logger.error(
            "Target channel validation failed for %s: %s",
            TARGET_CHANNEL_ID,
            exc,
        )
        return False

    except TelegramAPIError as exc:
        logger.warning(
            "Telegram API error while validating target channel: %s",
            exc,
        )
        return False

    except Exception:
        logger.exception(
            "Unexpected error while validating target channel."
        )
        return False


async def main():
    # Database
    await init_db()

    # Bot
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        ),
    )

    dp = Dispatcher()

    # Global fallback error handler
    @dp.error()
    async def global_error_handler(event: ErrorEvent):
        exc = event.exception

        logger.error(
            "Unhandled update exception: %s",
            exc,
            exc_info=(
                type(exc),
                exc,
                exc.__traceback__,
            ),
        )

        return True

    # Middleware
    dp.message.middleware(
        AdminAuthMiddleware()
    )

    dp.callback_query.middleware(
        AdminAuthMiddleware()
    )

    # Routers
    dp.include_router(
        admin_panel.router
    )

    dp.include_router(
        review.router
    )

    dp.include_router(
        channel_events.router
    )

    # Telegram commands
    await setup_bot_commands(bot)

    # Validate publishing channel
    channel_ok = await validate_target_channel(bot)

    if channel_ok:
        logger.info(
            "Target channel validation successful."
        )
    else:
        logger.warning(
            "Bot will continue running, but publishing "
            "may fail until target channel configuration "
            "or permissions are fixed."
        )

    # Background scraper
    asyncio.create_task(
        scraper_loop(bot),
        name="scraper-loop",
    )

    logger.info("Bot is starting...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except (KeyboardInterrupt, SystemExit):
        logger.info(
            "Bot stopped successfully."
        )

    except Exception:
        logger.exception(
            "Fatal application error."
        )
        raise
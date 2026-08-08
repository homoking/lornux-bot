import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from config import BOT_TOKEN
from database.connection import init_db
from middlewares.auth import AdminAuthMiddleware
from handlers import admin_panel, review, channel_events
from scraper.task import scraper_loop

# Basic logging config
logging.basicConfig(level=logging.INFO)

async def setup_bot_commands(bot: Bot):
    """Sets the native Telegram commands menu."""
    commands = [
        BotCommand(command="start", description="🚀 باز کردن پنل مدیریت")
    ]
    await bot.set_my_commands(commands)

async def main():
    # 1. Init Database
    await init_db()
    
    # 2. Init Bot & Dispatcher
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    # 3. Register Middleware
    dp.message.middleware(AdminAuthMiddleware())
    dp.callback_query.middleware(AdminAuthMiddleware())
    
    # 4. Include Routers
    dp.include_router(admin_panel.router)
    dp.include_router(review.router)
    dp.include_router(channel_events.router)
    
    # 5. Setup native commands
    await setup_bot_commands(bot)
    
    # 6. Start the background scraper task safely
    asyncio.create_task(scraper_loop(bot))
    
    # 7. Start Polling
    logging.info("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped successfully.")
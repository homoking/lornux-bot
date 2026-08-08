"""
فرمت نهایی پست برای انتشار در کانال + ثبت رکورد PublishedPost.
هشتگ و امضا عمداً اینجا اضافه می‌شوند، نه در خروجی LLM — طبق تصمیم معماری در master prompt.
از send_text_or_photo استفاده می‌کند تا اگر عکس موجود بود همراه پست منتشر شود
(با مدیریت درست محدودیت caption تلگرام).
"""
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.sending import send_text_or_photo
from app.config import settings
from app.db.models import Evaluation, PublishedPost


def format_post_for_publish(evaluation: Evaluation) -> str:
    return f"{evaluation.hashtag}\n\n{evaluation.rewritten_post}\n\n{settings.channel_signature}"


async def publish_evaluation(session: AsyncSession, bot: Bot, evaluation: Evaluation) -> PublishedPost:
    text = format_post_for_publish(evaluation)
    media_url = evaluation.raw_item.media_url if evaluation.raw_item else None

    message = await send_text_or_photo(bot, chat_id=settings.telegram_channel_id, text=text, media_url=media_url)

    published = PublishedPost(evaluation_id=evaluation.id, telegram_message_id=message.message_id)
    session.add(published)
    await session.flush()
    return published

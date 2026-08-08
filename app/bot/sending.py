"""
ارسال پیام متن یا عکس+متن به تلگرام.

نکته‌ی مهم (باگ رایج): محدودیت caption عکس در تلگرام فقط ۱۰۲۴ کاراکتر است (نه ۴۰۹۶
مثل پیام متنی معمولی). اگر مستقیم متن کامل پست را caption عکس بگذاریم، برای پست‌های
بلندتر خطای BadRequest می‌گیریم. اینجا این حالت را مدیریت می‌کنیم: اگر متن جا شود همراه
عکس با caption فرستاده می‌شود؛ اگر جا نشود، اول متن کامل (با دکمه‌ها) و بعد عکس جدا
(بدون دکمه، فقط برای نمایش) فرستاده می‌شود.
"""
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, Message

TELEGRAM_CAPTION_LIMIT = 1024


async def send_text_or_photo(
    bot: Bot,
    chat_id,
    text: str,
    media_url: str | None = None,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message:
    if media_url and len(text) <= TELEGRAM_CAPTION_LIMIT:
        try:
            return await bot.send_photo(chat_id=chat_id, photo=media_url, caption=text, reply_markup=reply_markup)
        except Exception:
            # عکس ممکن است broken link باشد یا تلگرام نتواند دانلودش کند — به حالت
            # متن‌تنها برگرد تا کل پیام از دست نرود
            pass

    message = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

    if media_url and len(text) > TELEGRAM_CAPTION_LIMIT:
        try:
            await bot.send_photo(chat_id=chat_id, photo=media_url)
        except Exception:
            pass  # نمایش عکس صرفاً یک بونوس است؛ نباید کل جریان را خراب کند

    return message

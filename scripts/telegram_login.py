"""
اجرای یک‌باره و محلی (روی سیستم خودتان، نه در Docker/سرور) برای تولید TELEGRAM_SESSION_STRING.

قبل از اجرا:
  ۱. از https://my.telegram.org یک api_id و api_hash بگیرید.
  ۲. pip install telethon

اجرا: python scripts/telegram_login.py
شماره‌تلفن، کد تأیید ارسالی به تلگرام، و (در صورت فعال بودن 2FA) رمز عبورتان پرسیده می‌شود.
خروجی نهایی را کپی و در .env به‌عنوان TELEGRAM_SESSION_STRING بگذارید.

⚠️ این session_string معادل دسترسی کامل به اکانت تلگرام شماست — هرگز آن را commit
نکنید، جایی به‌اشتراک نگذارید، یا در کد hardcode نکنید.

⚠️ این اسکریپت در sandbox من قابل اجرا/تست نیست (نیاز به تعامل واقعی با API تلگرام و
شماره‌ی واقعی دارد). بر اساس الگوی مستندشده‌ی Telethon نوشته شده؛ قبل از اعتماد کامل
به آن، امضای دقیق را با https://docs.telethon.dev تطبیق دهید.
"""
import asyncio

from telethon import TelegramClient
from telethon.sessions import StringSession


async def main() -> None:
    api_id = int(input("API ID (از my.telegram.org): ").strip())
    api_hash = input("API Hash: ").strip()

    async with TelegramClient(StringSession(), api_id, api_hash) as client:
        session_string = client.session.save()
        print("\n=== این خط را در .env به‌عنوان TELEGRAM_SESSION_STRING بگذارید ===\n")
        print(session_string)
        print("\n====================================================================\n")


if __name__ == "__main__":
    asyncio.run(main())

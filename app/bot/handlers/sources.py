"""
دستورات مدیریت منابع برای ادمین:
  /addsource <url> [name...]        - افزودن منبع RSS
  /addchannel <username> [name...]  - افزودن کانال تلگرام (نیاز به MTPROTO_ENABLED=true)
  /sources                          - نمایش لیست منابع
  /enable <short_id>                - فعال کردن منبع
  /disable <short_id>               - غیرفعال کردن (بدون حذف — poll_sources آن را نادیده می‌گیرد)
  /blacklist <short_id>             - قرار دادن در لیست سیاه
  /unblacklist <short_id>           - خارج کردن از لیست سیاه
  /rating <short_id> <1-5>          - تنظیم امتیاز اعتبار منبع

نکته: short_id همان ۸ کاراکتر اول UUID منبع است (نمایش‌داده‌شده در /sources).
"""
from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.services.source_admin import (
    add_source,
    add_telegram_channel_source,
    list_sources,
    set_active,
    set_blacklisted,
    set_rating,
    short_id,
)

router = Router()
router.message.filter(F.from_user.id == settings.telegram_admin_chat_id)


def _status_icon(source) -> str:
    if source.is_blacklisted:
        return "🚫"
    return "✅" if source.is_active else "⏸"


def _type_icon(source) -> str:
    return "📡" if source.source_type.value == "telegram_channel" else "📰"


@router.message(Command("addsource"))
async def cmd_add_source(message: Message, command: CommandObject) -> None:
    if not command.args:
        await message.reply("فرمت درست: /addsource <url> [نام دلخواه]")
        return

    parts = command.args.split(maxsplit=1)
    url = parts[0]
    name = parts[1] if len(parts) > 1 else None

    async with AsyncSessionLocal() as session:
        try:
            source = await add_source(session, url=url, name=name)
        except ValueError as exc:
            await message.reply(f"⚠️ {exc}")
            return
        await session.commit()

    await message.reply(f"✅ منبع RSS اضافه شد\nشناسه: <code>{short_id(source)}</code>\nنام: {source.name}\nامتیاز: {source.rating}")


@router.message(Command("addchannel"))
async def cmd_add_channel(message: Message, command: CommandObject) -> None:
    if not settings.mtproto_enabled:
        await message.reply(
            "⚠️ جمع‌آوری از کانال‌های تلگرام غیرفعال است.\n"
            "برای فعال‌سازی: MTPROTO_ENABLED=true در .env + راه‌اندازی session "
            "(نگاه کنید به scripts/telegram_login.py و README).\n\n"
            "⚠️ این قابلیت ریسک واقعی دارد — قبل از فعال کردن حتماً README را بخوانید."
        )
        return

    if not command.args:
        await message.reply("فرمت درست: /addchannel <username> [نام دلخواه]")
        return

    parts = command.args.split(maxsplit=1)
    channel_username = parts[0]
    name = parts[1] if len(parts) > 1 else None

    async with AsyncSessionLocal() as session:
        try:
            source = await add_telegram_channel_source(session, channel_username=channel_username, name=name)
        except ValueError as exc:
            await message.reply(f"⚠️ {exc}")
            return
        await session.commit()

    await message.reply(f"✅ کانال تلگرام اضافه شد\nشناسه: <code>{short_id(source)}</code>\nنام: {source.name}")


@router.message(Command("sources"))
async def cmd_list_sources(message: Message) -> None:
    async with AsyncSessionLocal() as session:
        sources = await list_sources(session)

    if not sources:
        await message.reply("هنوز هیچ منبعی اضافه نشده. با /addsource یا /addchannel شروع کنید.")
        return

    lines = ["📚 <b>لیست منابع</b>\n"]
    for s in sources:
        lines.append(f"{_status_icon(s)}{_type_icon(s)} <code>{short_id(s)}</code> — {s.name} (امتیاز {s.rating})")
    await message.reply("\n".join(lines))


async def _resolve_and_apply(message: Message, command: CommandObject, action, success_template: str) -> None:
    if not command.args:
        await message.reply("لطفاً شناسه‌ی منبع را هم بدهید (از /sources بگیرید)")
        return

    short = command.args.strip().split()[0]
    async with AsyncSessionLocal() as session:
        try:
            source = await action(session, short)
        except LookupError as exc:
            await message.reply(f"⚠️ {exc}")
            return
        await session.commit()
        await message.reply(success_template.format(name=source.name))


@router.message(Command("enable"))
async def cmd_enable(message: Message, command: CommandObject) -> None:
    await _resolve_and_apply(message, command, lambda s, sid: set_active(s, sid, True), "✅ «{name}» فعال شد")


@router.message(Command("disable"))
async def cmd_disable(message: Message, command: CommandObject) -> None:
    await _resolve_and_apply(message, command, lambda s, sid: set_active(s, sid, False), "⏸ «{name}» غیرفعال شد")


@router.message(Command("blacklist"))
async def cmd_blacklist(message: Message, command: CommandObject) -> None:
    await _resolve_and_apply(message, command, lambda s, sid: set_blacklisted(s, sid, True), "🚫 «{name}» بلک‌لیست شد")


@router.message(Command("unblacklist"))
async def cmd_unblacklist(message: Message, command: CommandObject) -> None:
    await _resolve_and_apply(message, command, lambda s, sid: set_blacklisted(s, sid, False), "✅ «{name}» از بلک‌لیست خارج شد")


@router.message(Command("rating"))
async def cmd_rating(message: Message, command: CommandObject) -> None:
    if not command.args:
        await message.reply("فرمت درست: /rating <short_id> <1-5>")
        return

    parts = command.args.split()
    if len(parts) != 2:
        await message.reply("فرمت درست: /rating <short_id> <1-5>")
        return

    short, rating_str = parts
    try:
        rating = int(rating_str)
    except ValueError:
        await message.reply("امتیاز باید عدد باشد (۱ تا ۵)")
        return

    async with AsyncSessionLocal() as session:
        try:
            source = await set_rating(session, short, rating)
        except (ValueError, LookupError) as exc:
            await message.reply(f"⚠️ {exc}")
            return
        await session.commit()
        await message.reply(f"✅ امتیاز «{source.name}» به {rating} تغییر کرد")

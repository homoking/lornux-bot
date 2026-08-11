import logging

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramNotFound,
    TelegramRetryAfter,
)

from messages import MSG
from keyboards.builders import (
    review_kb,
    hashtag_selector_kb,
    reject_confirm_kb,
)
from database import crud
from config import TARGET_CHANNEL_ID
from utils.states import BotStates


logger = logging.getLogger(__name__)
router = Router()

async def clean_pending_posts(
    bot: Bot,
    internal_id: str,
    exclude_admin: int = None,
):
    pendings = await crud.get_and_delete_pending_posts(
        internal_id,
        exclude_admin_id=exclude_admin,
    )

    for p in pendings:
        try:
            await bot.delete_message(
                chat_id=p["admin_id"],
                message_id=p["message_id"],
            )

        except (TelegramBadRequest, TelegramNotFound):
            # پیام قبلاً حذف شده یا دیگر وجود ندارد.
            logger.info(
                "Pending message already unavailable. admin_id=%s message_id=%s",
                p["admin_id"],
                p["message_id"],
            )

        except TelegramForbiddenError:
            logger.warning(
                "Cannot delete pending message for admin %s: bot has no access.",
                p["admin_id"],
            )

        except TelegramAPIError as exc:
            logger.warning(
                "Telegram error while deleting pending message. "
                "admin_id=%s error=%s",
                p["admin_id"],
                exc,
            )

        except Exception:
            logger.exception(
                "Unexpected error while deleting pending message. admin_id=%s",
                p["admin_id"],
            )

def extract_review_payload(message: Message):
    """
    Extract clean post content and reusable Telegram media IDs
    before deleting the moderation message.
    """

    content = (
        message.html_text
        or message.caption
        or ""
    )

    # Header منبع/لینک/واترمارک از محتوای واقعی جدا می‌شود.
    parts = content.split(
        "\n\n",
        1,
    )

    clean_content = (
        parts[1]
        if len(parts) > 1
        else content
    )

    media_type = None
    media_file_id = None

    if message.photo:
        media_type = "photo"
        media_file_id = message.photo[-1].file_id

    elif message.video:
        media_type = "video"
        media_file_id = message.video.file_id

    return (
        clean_content,
        media_type,
        media_file_id,
    )

@router.callback_query(F.data.startswith("reject_"))
async def reject_post(
    callback: CallbackQuery,
):
    """
    First step of rejecting a post.

    Nothing is deleted here.
    Only the inline keyboard of the same message
    is changed to a confirmation menu.
    """

    internal_id = callback.data.removeprefix("reject_")

    try:
        await callback.message.edit_reply_markup(
            reply_markup=reject_confirm_kb(
                internal_id
            )
        )

        await callback.answer(
            "برای رد کردن پست، حذف نهایی را تایید کنید."
        )

    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            logger.warning(
                "Could not show reject confirmation. "
                "internal_id=%s error=%s",
                internal_id,
                exc,
            )

    except TelegramAPIError as exc:
        logger.warning(
            "Telegram error while showing reject confirmation. "
            "internal_id=%s error=%s",
            internal_id,
            exc,
        )


@router.callback_query(
    F.data.startswith("cancel_reject_")
)
async def cancel_reject_post(
    callback: CallbackQuery,
):
    """
    Cancel rejection and restore the original moderation buttons.
    """

    internal_id = callback.data.removeprefix(
        "cancel_reject_"
    )

    try:
        await callback.message.edit_reply_markup(
            reply_markup=review_kb(
                internal_id
            )
        )

        await callback.answer(
            "رد کردن پست لغو شد."
        )

    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            logger.warning(
                "Could not restore review keyboard. "
                "internal_id=%s error=%s",
                internal_id,
                exc,
            )

    except TelegramAPIError as exc:
        logger.warning(
            "Telegram error while restoring review keyboard. "
            "internal_id=%s error=%s",
            internal_id,
            exc,
        )


@router.callback_query(
    F.data.startswith("confirm_reject_")
)
async def confirm_reject_post(
    callback: CallbackQuery,
    bot: Bot,
):
    """
    Actually reject the post after explicit confirmation.
    """

    internal_id = callback.data.removeprefix(
        "confirm_reject_"
    )

    try:
        # اول callback را جواب می‌دهیم.
        await callback.answer(
            "❌ پست رد شد."
        )

    except TelegramAPIError:
        pass

    try:
        await crud.log_action(
            "REJECTED",
            callback.from_user.id,
            "unknown",
        )

        # حالا نسخه پست از چت تمام Adminها
        # شامل Admin فعلی حذف می‌شود.
        await clean_pending_posts(
            bot,
            internal_id,
        )

        logger.info(
            "Post rejected. internal_id=%s admin_id=%s",
            internal_id,
            callback.from_user.id,
        )

    except Exception:
        logger.exception(
            "Unexpected error while rejecting post. "
            "internal_id=%s admin_id=%s",
            internal_id,
            callback.from_user.id,
        )

@router.callback_query(F.data.startswith("approve_"))
async def approve_post(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
):
    internal_id = callback.data.removeprefix(
        "approve_"
    )

    # اطلاعات پست را قبل از ادامه workflow
    # برای مرحله انتشار نهایی ذخیره می‌کنیم.
    (
        original_content,
        media_type,
        media_file_id,
    ) = extract_review_payload(
        callback.message
    )

    tags = await crud.get_hashtags()

    await state.update_data(
        selected_tags=[],
        internal_id=internal_id,
        original_content=original_content,
        media_type=media_type,
        media_file_id=media_file_id,
        edited_text=None,
        publishing=False,
    )

    try:
        await crud.log_action(
            "APPROVED",
            callback.from_user.id,
            "unknown",
        )

    except Exception:
        logger.exception(
            "Could not log APPROVED action. "
            "internal_id=%s admin_id=%s",
            internal_id,
            callback.from_user.id,
        )

    # نسخه پست را از چت سایر Adminها حذف می‌کنیم،
    # ولی پیام Admin فعلی باقی می‌ماند.
    await clean_pending_posts(
        bot,
        internal_id,
        exclude_admin=callback.from_user.id,
    )

    try:
        # نکته اصلی:
        # پیام جدید نمی‌فرستیم.
        # فقط keyboard همین پست را به selector هشتگ تبدیل می‌کنیم.
        await callback.message.edit_reply_markup(
            reply_markup=hashtag_selector_kb(
                internal_id,
                tags,
                [],
            )
        )

        await callback.answer(
            "✅ تایید شد؛ هشتگ‌ها را انتخاب کنید."
        )

    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            logger.debug(
                "Hashtag selector is already visible. "
                "internal_id=%s",
                internal_id,
            )

            try:
                await callback.answer()
            except TelegramAPIError:
                pass

        else:
            logger.warning(
                "Could not show hashtag selector. "
                "internal_id=%s error=%s",
                internal_id,
                exc,
            )

            try:
                await callback.answer(
                    "نمایش هشتگ‌ها با خطا مواجه شد.",
                    show_alert=True,
                )
            except TelegramAPIError:
                pass

    except TelegramAPIError as exc:
        logger.warning(
            "Telegram error while opening hashtag selector. "
            "internal_id=%s error=%s",
            internal_id,
            exc,
        )

        try:
            await callback.answer(
                "خطای تلگرام هنگام نمایش هشتگ‌ها.",
                show_alert=True,
            )
        except TelegramAPIError:
            pass

    except Exception:
        logger.exception(
            "Unexpected error while opening hashtag selector. "
            "internal_id=%s",
            internal_id,
        )

        try:
            await callback.answer(
                "خطای غیرمنتظره هنگام تایید پست.",
                show_alert=True,
            )
        except TelegramAPIError:
            pass

# ==================== ✏️ بخش اضافه شده: مدیریت ویرایش ====================
@router.callback_query(F.data.startswith("edit_"))
async def edit_post_prompt(callback: CallbackQuery, bot: Bot, state: FSMContext):
    internal_id = callback.data.split("_")[1]
    
    # ۱. پیام را از پی‌وی سایر ادمین‌ها پاک کن
    await clean_pending_posts(bot, internal_id, exclude_admin=callback.from_user.id)
    
    # ۲. آیدی پیام اصلی (اسکرپ شده) را ذخیره می‌کنیم تا عکس/ویدیوی آن گم نشود
    await state.update_data(internal_id=internal_id, orig_msg_id=callback.message.message_id)
    
    # ۳. درخواست متن جدید از ادمین
    await callback.message.reply(MSG["edit_prompt"])
    await state.set_state(BotStates.waiting_for_edit)

@router.message(BotStates.waiting_for_edit)
async def receive_edited_text(message: Message, state: FSMContext, bot: Bot):
    new_text = message.html_text
    data = await state.get_data()
    internal_id = data.get("internal_id")
    orig_msg_id = data.get("orig_msg_id")
    
    await crud.log_action("EDITED", message.from_user.id, "unknown")
    tags = await crud.get_hashtags()
    
    # ۴. متن جدیدِ ادمین را در State ذخیره می‌کنیم
    await state.update_data(selected_tags=[], edited_text=new_text)
    
    # ۵. کیبورد هشتگ‌ها را دقیقاً روی همون پیامی که مدیا داشت ریپلای می‌کنیم
    await bot.send_message(
        chat_id=message.chat.id,
        text=MSG["select_hashtags"],
        reply_to_message_id=orig_msg_id,
        reply_markup=hashtag_selector_kb(internal_id, tags, [])
    )
    await state.set_state(None) # خروج از حالت انتظار برای متن
# =========================================================================

@router.callback_query(F.data.startswith("toggle_"))
async def toggle_hashtag(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_", 2)

    if len(parts) < 3:
        await callback.answer(
            "درخواست نامعتبر است.",
            show_alert=True,
        )
        return

    internal_id = parts[1]
    tag = parts[2]

    data = await state.get_data()
    selected = list(data.get("selected_tags", []))

    if tag in selected:
        selected.remove(tag)
    else:
        selected.append(tag)

    await state.update_data(selected_tags=selected)

    tags = await crud.get_hashtags()
    new_markup = hashtag_selector_kb(
        internal_id,
        tags,
        selected,
    )

    try:
        await callback.message.edit_reply_markup(
            reply_markup=new_markup
        )

    except TelegramBadRequest as exc:
        # کلیک‌های سریع یا callback تکراری ممکن است markup یکسان تولید کنند.
        if "message is not modified" in str(exc).lower():
            logger.debug(
                "Hashtag keyboard was already up to date."
            )
        else:
            logger.warning(
                "Could not update hashtag keyboard: %s",
                exc,
            )

    except TelegramAPIError as exc:
        logger.warning(
            "Telegram error while updating hashtag keyboard: %s",
            exc,
        )

    except Exception:
        logger.exception(
            "Unexpected error while updating hashtag keyboard."
        )

    finally:
        try:
            await callback.answer()
        except TelegramAPIError:
            pass

@router.callback_query(F.data.startswith("send_"))
async def final_send_post(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
):
    data = await state.get_data()

    # جلوگیری از چند بار زدن دکمه انتشار
    if data.get("publishing"):
        try:
            await callback.answer(
                "پست در حال انتشار است...",
                show_alert=True,
            )
        except TelegramAPIError:
            pass
        return

    await state.update_data(publishing=True)

    selected_tags = data.get("selected_tags", [])
    edited_text = data.get("edited_text")

    media_type = data.get("media_type")
    media_file_id = data.get("media_file_id")
    stored_content = data.get("original_content")

    # برای مسیر Edit قدیمی همچنان fallback داریم.
    original_msg = callback.message.reply_to_message

    if edited_text:
        clean_content = edited_text

    elif stored_content is not None:
        clean_content = stored_content

    elif original_msg:
        content = (
            original_msg.html_text
            or original_msg.caption
            or ""
        )

        parts = content.split(
            "\n\n",
            1,
        )

        clean_content = (
            parts[1]
            if len(parts) > 1
            else content
        )

    else:
        logger.warning(
            "Publish failed because post content was not found. "
            "user_id=%s",
            callback.from_user.id,
        )

        await state.update_data(
            publishing=False
        )

        try:
            await callback.answer(
                "اطلاعات پست پیدا نشد. لطفاً دوباره تلاش کنید.",
                show_alert=True,
            )
        except TelegramAPIError:
            pass

        return

    footer = await crud.get_footer()
    tags_str = " ".join(selected_tags)

    final_text = clean_content

    if tags_str:
        final_text += f"\n\n{tags_str}"

    if footer:
        final_text += f"\n\n{footer}"

    try:
        # -----------------------------
        # انتشار در کانال
        # -----------------------------
        if media_type == "photo" and media_file_id:
            await bot.send_photo(
                chat_id=TARGET_CHANNEL_ID,
                photo=media_file_id,
                caption=final_text,
                parse_mode="HTML",
            )

        elif media_type == "video" and media_file_id:
            await bot.send_video(
                chat_id=TARGET_CHANNEL_ID,
                video=media_file_id,
                caption=final_text,
                parse_mode="HTML",
            )

        # fallback برای workflow قدیمی Edit
        elif original_msg and not original_msg.text:
            await bot.copy_message(
                chat_id=TARGET_CHANNEL_ID,
                from_chat_id=original_msg.chat.id,
                message_id=original_msg.message_id,
                caption=final_text,
                parse_mode="HTML",
                reply_markup=None,
            )

        else:
            await bot.send_message(
                chat_id=TARGET_CHANNEL_ID,
                text=final_text,
                parse_mode="HTML",
            )

    except TelegramRetryAfter as exc:
        logger.warning(
            "Telegram rate limit while publishing. retry_after=%s",
            exc.retry_after,
        )

        await state.update_data(publishing=False)

        try:
            await callback.answer(
                f"محدودیت موقت تلگرام. {exc.retry_after} ثانیه بعد دوباره امتحان کنید.",
                show_alert=True,
            )
        except TelegramAPIError:
            pass

        return

    except TelegramForbiddenError as exc:
        logger.error(
            "Bot has no permission to publish to channel %s: %s",
            TARGET_CHANNEL_ID,
            exc,
        )

        await state.update_data(publishing=False)

        try:
            await callback.answer(
                "ربات دسترسی ارسال پست در کانال مقصد را ندارد.",
                show_alert=True,
            )
        except TelegramAPIError:
            pass

        return

    except TelegramNotFound as exc:
        logger.error(
            "Target channel %s was not found: %s",
            TARGET_CHANNEL_ID,
            exc,
        )

        await state.update_data(publishing=False)

        try:
            await callback.answer(
                "کانال مقصد پیدا نشد.",
                show_alert=True,
            )
        except TelegramAPIError:
            pass

        return

    except TelegramBadRequest as exc:
        logger.error(
            "Telegram rejected publication to channel %s: %s",
            TARGET_CHANNEL_ID,
            exc,
        )

        await state.update_data(publishing=False)

        try:
            await callback.answer(
                "تلگرام پست را قبول نکرد. متن، مدیا یا تنظیمات کانال را بررسی کنید.",
                show_alert=True,
            )
        except TelegramAPIError:
            pass

        return

    except TelegramNetworkError as exc:
        logger.warning(
            "Telegram network error while publishing: %s",
            exc,
        )

        await state.update_data(publishing=False)

        try:
            await callback.answer(
                "ارتباط با تلگرام برقرار نشد. دوباره امتحان کنید.",
                show_alert=True,
            )
        except TelegramAPIError:
            pass

        return

    except TelegramAPIError as exc:
        logger.error(
            "Telegram API error while publishing: %s",
            exc,
        )

        await state.update_data(publishing=False)

        try:
            await callback.answer(
                "هنگام ارتباط با تلگرام خطایی رخ داد.",
                show_alert=True,
            )
        except TelegramAPIError:
            pass

        return

    except Exception:
        logger.exception(
            "Unexpected error while publishing post."
        )

        await state.update_data(publishing=False)

        try:
            await callback.answer(
                "خطای غیرمنتظره هنگام انتشار پست.",
                show_alert=True,
            )
        except TelegramAPIError:
            pass

        return

    # -----------------------------
    # انتشار موفق
    # -----------------------------
    logger.info(
        "Post published successfully. channel_id=%s admin_id=%s",
        TARGET_CHANNEL_ID,
        callback.from_user.id,
    )

    internal_id = data.get("internal_id")

    try:
        await callback.answer(
            "✅ پست با موفقیت منتشر شد."
        )
    except TelegramAPIError:
        pass

    if internal_id:
        await clean_pending_posts(
            bot,
            internal_id,
        )


    await state.clear()
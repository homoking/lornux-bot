"""
Handlerهای دکمه‌های تأیید/رد/بازنویسی. فقط ادمین (TELEGRAM_ADMIN_CHAT_ID) اجازه‌ی
استفاده از این دکمه‌ها را دارد.

نکته‌ی فاز ۲: چون پیام‌ها ممکن است حالا عکس+caption باشند (نه فقط متن ساده)، ویرایش
پیام بعد از تصمیم باید بین حالت متنی و حالت عکسی تشخیص بدهد (edit_caption در برابر
edit_text) — تلگرام این دو را جدا می‌داند و استفاده‌ی اشتباه خطای BadRequest می‌دهد.
"""
import uuid

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.bot.keyboards import approval_keyboard
from app.bot.preview import build_admin_preview_text
from app.bot.sending import send_text_or_photo
from app.config import settings
from app.core.logging import logger
from app.core.redis_client import get_redis
from app.db.models import Evaluation, ItemStatus, LLMProvider, RawItem
from app.db.session import AsyncSessionLocal
from app.services.llm.evaluator import AllProvidersFailedError, LornuxEvaluator
from app.services.publisher import publish_evaluation

router = Router()
router.callback_query.filter(F.from_user.id == settings.telegram_admin_chat_id)


async def _load_evaluation(session, evaluation_id: uuid.UUID) -> Evaluation | None:
    stmt = (
        select(Evaluation)
        .where(Evaluation.id == evaluation_id)
        .options(selectinload(Evaluation.raw_item).selectinload(RawItem.source))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _mark_decided(callback: CallbackQuery, suffix: str) -> None:
    """پیام تصمیم‌گیری‌شده را ویرایش می‌کند — چه متنی باشد چه عکس‌دار."""
    try:
        if callback.message.photo:
            new_caption = (callback.message.caption or "") + suffix
            await callback.message.edit_caption(caption=new_caption[:1024], reply_markup=None)
        else:
            await callback.message.edit_text(callback.message.html_text + suffix, reply_markup=None)
    except Exception as exc:  # noqa: BLE001 — ویرایش پیام صرفاً cosmetic است؛ نباید کل جریان را خراب کند
        logger.warning(f"ویرایش پیام بعد از تصمیم شکست خورد (بی‌اهمیت): {exc}")


@router.callback_query(F.data.startswith("approve:"))
async def on_approve(callback: CallbackQuery) -> None:
    evaluation_id = uuid.UUID(callback.data.split(":", 1)[1])
    async with AsyncSessionLocal() as session:
        evaluation = await _load_evaluation(session, evaluation_id)
        if evaluation is None:
            await callback.answer("این پیشنهاد دیگر معتبر نیست.", show_alert=True)
            return

        await publish_evaluation(session, callback.bot, evaluation)
        evaluation.raw_item.status = ItemStatus.PUBLISHED
        await session.commit()

    await _mark_decided(callback, "\n\n✅ منتشر شد")
    await callback.answer("منتشر شد ✅")


@router.callback_query(F.data.startswith("reject:"))
async def on_reject(callback: CallbackQuery) -> None:
    evaluation_id = uuid.UUID(callback.data.split(":", 1)[1])
    async with AsyncSessionLocal() as session:
        evaluation = await _load_evaluation(session, evaluation_id)
        if evaluation is None:
            await callback.answer("این پیشنهاد دیگر معتبر نیست.", show_alert=True)
            return

        evaluation.raw_item.status = ItemStatus.REJECTED_BY_ADMIN
        await session.commit()

    await _mark_decided(callback, "\n\n❌ رد شد")
    await callback.answer("رد شد")


@router.callback_query(F.data.startswith("rewrite:"))
async def on_rewrite(callback: CallbackQuery) -> None:
    evaluation_id = uuid.UUID(callback.data.split(":", 1)[1])
    await callback.answer("در حال بازنویسی مجدد...")

    async with AsyncSessionLocal() as session:
        old_evaluation = await _load_evaluation(session, evaluation_id)
        if old_evaluation is None:
            return

        raw_item = old_evaluation.raw_item
        source = raw_item.source

        evaluator = LornuxEvaluator(redis=get_redis())
        try:
            result, provider = await evaluator.evaluate_item(
                source_name=source.name,
                source_url=source.url,
                published_at=(raw_item.published_at or raw_item.fetched_at).isoformat(),
                source_rating=source.rating,
                title=raw_item.title,
                body=raw_item.body,
            )
        except AllProvidersFailedError as exc:
            logger.error(f"بازنویسی مجدد شکست خورد برای {raw_item.id}: {exc}")
            await callback.message.reply("⚠️ بازنویسی مجدد با خطا مواجه شد. لطفاً دوباره امتحان کنید.")
            return

        new_evaluation = Evaluation(
            raw_item_id=raw_item.id,
            llm_provider=LLMProvider(provider),
            worth_posting=result.worth_posting,
            reject_reason=result.reject_reason,
            content_type=result.content_type,
            score_educational=result.score.educational_value,
            score_practical=result.score.practical_value,
            score_freshness=result.score.freshness,
            score_interest=result.score.interest,
            score_overall=result.score.overall,
            hashtag=result.hashtag,
            rewritten_post=result.rewritten_post,
            reasoning=result.reasoning,
        )
        session.add(new_evaluation)
        await session.flush()
        new_evaluation.raw_item = raw_item

        preview_text = build_admin_preview_text(new_evaluation, raw_item)
        await session.commit()

    # پیام جدید فرستاده می‌شود (نه edit) چون ممکن است حالت عکس/متن قبلی و جدید فرق کند
    await send_text_or_photo(
        callback.bot, chat_id=callback.from_user.id, text=preview_text,
        media_url=raw_item.media_url, reply_markup=approval_keyboard(new_evaluation.id),
    )

"""
تسک‌های اصلی pipeline:
  1) poll_sources_task  — با celery beat هر POLL_INTERVAL_MINUTES دقیقه اجرا می‌شود
  2) process_item_task  — embedding → dedup → LLM evaluate → (Media Finder + Related) → تأیید ادمین

منابع بر اساس source_type دیسپچ می‌شوند: RSS (فعلاً پیاده‌سازی‌شده) یا کانال تلگرام
(نیازمند MTPROTO_ENABLED=true؛ در services/telegram_collector.py).
"""
import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.logging import logger
from app.core.redis_client import get_redis
from app.db.models import Evaluation, ItemStatus, LLMProvider, RawItem, Source, SourceType
from app.db.session import AsyncSessionLocal
from app.services.dedup import find_duplicate, find_related_published
from app.services.embedding import embed_text
from app.services.llm.evaluator import AllProvidersFailedError, LornuxEvaluator
from app.services.media_finder import find_og_image
from app.services.rss_collector import fetch_feed_entries
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.pipeline.poll_sources_task")
def poll_sources_task() -> None:
    asyncio.run(_poll_sources())


async def _poll_sources() -> None:
    new_item_ids: list[uuid.UUID] = []

    async with AsyncSessionLocal() as session:
        stmt = select(Source).where(Source.is_active.is_(True), Source.is_blacklisted.is_(False))
        result = await session.execute(stmt)
        sources = result.scalars().all()

        for source in sources:
            if source.source_type == SourceType.TELEGRAM_CHANNEL:
                entries = await _fetch_telegram_entries(source)
            else:
                entries = await fetch_feed_entries(source.url)

            for entry in entries:
                item = RawItem(
                    source_id=source.id,
                    guid=entry.guid,
                    title=entry.title,
                    body=entry.body,
                    url=entry.url,
                    published_at=entry.published_at,
                    media_url=entry.image_url_hint,  # اگر خود منبع تصویر داده بود، رایگان ذخیره می‌شود
                    status=ItemStatus.PENDING,
                )
                session.add(item)
                try:
                    # flush به‌ازای هر آیتم تا unique constraint (source_id, guid) بلافاصله چک شود
                    # و یک آیتم تکراری کل batch را rollback نکند
                    await session.flush()
                except IntegrityError:
                    await session.rollback()
                    continue
                new_item_ids.append(item.id)

        await session.commit()

    logger.info(f"poll_sources: {len(new_item_ids)} آیتم جدید دریافت شد")
    for item_id in new_item_ids:
        process_item_task.delay(str(item_id))


async def _fetch_telegram_entries(source: Source) -> list:
    """
    جمع‌آوری از کانال تلگرام دیگر (MTProto/Telethon). اگر MTPROTO_ENABLED=false باشد
    (پیش‌فرض)، این منبع بی‌صدا نادیده گرفته می‌شود — نه کرش می‌کند، نه لاگ اسپم می‌کند
    بیش‌ازحد (هر بار یک warning).
    """
    if not settings.mtproto_enabled:
        logger.warning(f"منبع تلگرامی «{source.name}» نادیده گرفته شد چون MTPROTO_ENABLED=false است")
        return []

    from app.services.telegram_collector import fetch_channel_entries

    return await fetch_channel_entries(source.url)


@celery_app.task(
    name="app.tasks.pipeline.process_item_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def process_item_task(self, item_id: str) -> None:
    try:
        asyncio.run(_process_item(uuid.UUID(item_id)))
    except Exception as exc:  # noqa: BLE001 — عمداً broad: هر خطای پیش‌بینی‌نشده باید retry شود
        logger.error(f"process_item شکست خورد برای {item_id}: {exc}")
        raise self.retry(exc=exc)


async def _process_item(item_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        stmt = select(RawItem).where(RawItem.id == item_id).options(selectinload(RawItem.source))
        result = await session.execute(stmt)
        item = result.scalar_one_or_none()
        if item is None:
            logger.warning(f"process_item: آیتم {item_id} پیدا نشد")
            return

        # ۱) Embedding محلی (رایگان، بدون API call)
        embedding = embed_text(f"{item.title}\n{item.body}")
        item.embedding = embedding
        await session.flush()

        # ۲) بررسی تکراری بودن (قبل از رسیدن به LLM — صرفه‌جویی در quota)
        duplicate = await find_duplicate(session, embedding, exclude_item_id=item.id)
        if duplicate is not None:
            item.status = ItemStatus.DUPLICATE
            item.duplicate_of_id = duplicate.id
            await session.commit()
            logger.info(f"آیتم {item.id} تکراری با {duplicate.id} تشخیص داده شد")
            return

        # ۳) ارزیابی ترکیبی LLM (Gemini اصلی، Groq fallback)
        evaluator = LornuxEvaluator(redis=get_redis())
        try:
            result, provider = await evaluator.evaluate_item(
                source_name=item.source.name,
                source_url=item.source.url,
                published_at=(item.published_at or item.fetched_at).isoformat(),
                source_rating=item.source.rating,
                title=item.title,
                body=item.body,
            )
        except AllProvidersFailedError:
            # هر دو provider شکست خوردند — rollback و اجازه بده Celery retry کند (آیتم pending می‌ماند)
            await session.rollback()
            raise

        evaluation = Evaluation(
            raw_item_id=item.id,
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
        session.add(evaluation)

        if result.worth_posting and result.score.overall >= settings.score_worth_posting_threshold:
            item.status = ItemStatus.PENDING_APPROVAL
        else:
            item.status = ItemStatus.REJECTED_AUTO

        await session.flush()
        evaluation.raw_item = item  # از query اضافه برای preview جلوگیری می‌کند

        related_items = []
        if item.status == ItemStatus.PENDING_APPROVAL:
            # ۴) Media Finder — فقط حالا (نه برای همه‌ی آیتم‌های خام) تا هزینه‌ی HTTP کم شود
            if settings.media_enabled and not item.media_url:
                item.media_url = await find_og_image(item.url)
                await session.flush()

            # ۵) Series Detector — پست‌های مرتبط قبلی
            related_items = await find_related_published(session, embedding, exclude_item_id=item.id)

            await _send_for_approval(evaluation, item, related_items)

        await session.commit()


async def _send_for_approval(evaluation: Evaluation, item: RawItem, related_items: list) -> None:
    # import محلی عمداً است: از circular import بین pipeline و bot جلوگیری می‌کند
    from app.bot.bot import bot
    from app.bot.keyboards import approval_keyboard
    from app.bot.preview import build_admin_preview_text
    from app.bot.sending import send_text_or_photo

    text = build_admin_preview_text(evaluation, item, related_items)
    await send_text_or_photo(
        bot, chat_id=settings.telegram_admin_chat_id, text=text,
        media_url=item.media_url, reply_markup=approval_keyboard(evaluation.id),
    )

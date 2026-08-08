"""
ساخت گزارش روزانه (Daily Digest / Content Balance) از پست‌های منتشرشده‌ی ۲۴ ساعت گذشته.

تصمیم معماری: این گزارش فقط برای ادمین فرستاده می‌شود (نه مستقیم در کانال) — چون
محتوایش خلاصه‌ای از پست‌های از قبل تأییدشده است و نیازی به تأیید مجدد ندارد، اما
انتشار خودکار هر محتوایی در کانال بدون هیچ نظارتی با فلسفه‌ی Admin Approval پروژه
همخوانی ندارد. اگر بعداً خواستید مستقیم در کانال منتشر شود، همین متن را با
publisher.py وصل کنید.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import Evaluation, PublishedPost


async def build_daily_digest_text(session) -> str | None:
    """اگر امروز هیچ پستی منتشر نشده باشد None برمی‌گرداند (نباید پیام خالی فرستاد)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    stmt = (
        select(PublishedPost)
        .join(Evaluation, PublishedPost.evaluation_id == Evaluation.id)
        .where(PublishedPost.published_at >= cutoff)
        .options(selectinload(PublishedPost.evaluation))
        .order_by(PublishedPost.published_at)
    )
    result = await session.execute(stmt)
    published = list(result.scalars().all())

    if not published:
        return None

    evaluations = [p.evaluation for p in published]
    content_type_counts = Counter(e.content_type.value for e in evaluations if e.content_type)
    hashtag_counts = Counter(e.hashtag for e in evaluations if e.hashtag)
    avg_score = round(sum(e.score_overall for e in evaluations) / len(evaluations))

    top_items = sorted(evaluations, key=lambda e: e.score_overall, reverse=True)[:5]

    lines = [
        "📊 <b>گزارش روزانه‌ی Lornux</b>\n",
        f"تعداد پست منتشرشده: <b>{len(published)}</b>",
        f"میانگین امتیاز: <b>{avg_score}/100</b>\n",
    ]

    if content_type_counts:
        total = sum(content_type_counts.values())
        breakdown = ", ".join(
            f"{ct} {round(100 * count / total)}٪" for ct, count in content_type_counts.most_common()
        )
        lines.append(f"ترکیب محتوا: {breakdown}")

    if hashtag_counts:
        top_tags = ", ".join(f"{tag} ({count})" for tag, count in hashtag_counts.most_common(5))
        lines.append(f"پرتکرارترین هشتگ‌ها: {top_tags}\n")

    lines.append("🏆 <b>برترین پست‌های امروز:</b>")
    for e in top_items:
        title_line = (e.rewritten_post or "").split("\n", 1)[0][:60]
        lines.append(f"  • ({e.score_overall}) {title_line}")

    return "\n".join(lines)

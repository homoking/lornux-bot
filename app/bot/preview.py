"""ساخت متن پیش‌نمایشی که برای ادمین فرستاده می‌شود (شامل امتیازها، برای تصمیم‌گیری سریع)."""
from app.db.models import Evaluation, RawItem


def build_admin_preview_text(evaluation: Evaluation, raw_item: RawItem, related_items: list[RawItem] | None = None) -> str:
    s = evaluation.score_overall
    text = (
        f"📝 <b>پست پیشنهادی جدید</b>\n\n"
        f"امتیاز کلی: <b>{s}/100</b>  "
        f"(آموزشی {evaluation.score_educational} | عملی {evaluation.score_practical} | "
        f"تازگی {evaluation.score_freshness} | جذابیت {evaluation.score_interest})\n"
        f"نوع محتوا: {evaluation.content_type.value if evaluation.content_type else '-'}\n"
        f"هشتگ: {evaluation.hashtag or '-'}\n"
        f"منبع: {raw_item.source.name}\n"
        f"مدل استفاده‌شده: {evaluation.llm_provider.value}\n"
        f"—\n\n"
        f"{evaluation.rewritten_post}\n\n"
        f"—\n<i>دلیل مدل: {evaluation.reasoning}</i>"
    )

    if related_items:
        text += "\n\n🔗 <b>مرتبط با پست‌های قبلی:</b>\n"
        for r in related_items:
            title_line = r.title[:60]
            text += f"  • {title_line}\n"

    return text

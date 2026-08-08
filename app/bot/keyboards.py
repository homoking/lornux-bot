from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def approval_keyboard(evaluation_id) -> InlineKeyboardMarkup:
    eid = str(evaluation_id)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ انتشار", callback_data=f"approve:{eid}"),
                InlineKeyboardButton(text="❌ رد", callback_data=f"reject:{eid}"),
            ],
            [
                InlineKeyboardButton(text="🔄 بازنویسی مجدد", callback_data=f"rewrite:{eid}"),
            ],
        ]
    )

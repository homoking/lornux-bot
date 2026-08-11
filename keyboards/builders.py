from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup
from messages import MSG

def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=MSG["btn_channels"], callback_data="menu_channels")
    builder.button(text=MSG["btn_hashtags"], callback_data="menu_hashtags")
    builder.button(text=MSG["btn_admins"], callback_data="menu_admins")
    builder.button(text=MSG["btn_footer"], callback_data="menu_footer")
    builder.button(text=MSG["btn_stats"], callback_data="menu_stats")
    builder.adjust(1, 2, 2)
    return builder.as_markup()

def channels_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=MSG["btn_add_channel"], callback_data="ch_add")
    builder.button(text=MSG["btn_list_channels"], callback_data="ch_list")
    builder.button(text=MSG["btn_remove_channel"], callback_data="ch_remove")
    builder.button(text=MSG["btn_back"], callback_data="menu_main")
    builder.adjust(1, 2, 1)
    return builder.as_markup()

def remove_channel_kb(channels: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ch in channels:
        builder.button(text=f"❌ {ch['username']}", callback_data=f"del_ch_{ch['username']}")
    builder.button(text=MSG["btn_back"], callback_data="menu_channels")
    builder.adjust(1)
    return builder.as_markup()

def back_kb(target: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=MSG["btn_back"], callback_data=target)
    return builder.as_markup()

def review_kb(internal_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=MSG["btn_approve"], callback_data=f"approve_{internal_id}")
    builder.button(text=MSG["btn_reject"], callback_data=f"reject_{internal_id}")
    builder.button(text=MSG["btn_edit"], callback_data=f"edit_{internal_id}")
    builder.adjust(2, 1)
    return builder.as_markup()

def reject_confirm_kb(internal_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.button(
        text=MSG["btn_confirm_reject"],
        callback_data=f"confirm_reject_{internal_id}",
    )

    builder.button(
        text=MSG["btn_cancel_reject"],
        callback_data=f"cancel_reject_{internal_id}",
    )

    builder.adjust(1, 1)

    return builder.as_markup()

def hashtag_selector_kb(internal_id: str, tags: list, selected: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for tag in tags:
        mark = "✅" if tag in selected else "❌"
        builder.button(text=f"{mark} {tag}", callback_data=f"toggle_{internal_id}_{tag}")
    builder.button(text=MSG["btn_final_send"], callback_data=f"send_{internal_id}")
    builder.adjust(2) 
    return builder.as_markup()

def hashtags_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=MSG["btn_add_hashtag"], callback_data="ht_add")
    builder.button(text=MSG["btn_list_hashtags"], callback_data="ht_list")
    builder.button(text=MSG["btn_remove_hashtag"], callback_data="ht_remove")
    builder.button(text=MSG["btn_back"], callback_data="menu_main")
    builder.adjust(1, 2, 1)
    return builder.as_markup()

def remove_hashtag_kb(tags: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for tag in tags:
        builder.button(text=f"❌ {tag}", callback_data=f"del_ht_{tag}")
    builder.button(text=MSG["btn_back"], callback_data="menu_hashtags")
    builder.adjust(2) # دو ستونه برای هشتگ‌ها
    return builder.as_markup()

def admins_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=MSG["btn_add_admin"], callback_data="ad_add")
    builder.button(text=MSG["btn_list_admins"], callback_data="ad_list")
    builder.button(text=MSG["btn_remove_admin"], callback_data="ad_remove")
    builder.button(text=MSG["btn_back"], callback_data="menu_main")
    builder.adjust(1, 2, 1)
    return builder.as_markup()

def remove_admin_kb(admins: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for admin_id in admins:
        builder.button(text=f"❌ {admin_id}", callback_data=f"del_ad_{admin_id}")
    builder.button(text=MSG["btn_back"], callback_data="menu_admins")
    builder.adjust(1)
    return builder.as_markup()
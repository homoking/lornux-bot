from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from messages import MSG
from keyboards import builders
from utils.states import BotStates
from database import crud

router = Router()

@router.message(F.text == "/start")
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(MSG["welcome"], reply_markup=builders.main_menu_kb())

@router.callback_query(F.data == "menu_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(MSG["welcome"], reply_markup=builders.main_menu_kb())

# ================= مدیریت فوتر =================
@router.callback_query(F.data == "menu_footer")
async def menu_footer(callback: CallbackQuery, state: FSMContext):
    footer = await crud.get_footer()
    text = MSG["current_footer"].format(footer=footer if footer else "ندارد")
    await callback.message.edit_text(text, reply_markup=builders.back_kb("menu_main"))
    await state.set_state(BotStates.waiting_for_footer)

@router.message(BotStates.waiting_for_footer)
async def set_new_footer(message: Message, state: FSMContext):
    await crud.set_footer(message.html_text)
    await message.answer(MSG["footer_updated"], reply_markup=builders.back_kb("menu_main"))
    await state.clear()

# ================= مدیریت کانال‌ها =================
@router.callback_query(F.data == "menu_channels")
async def menu_channels(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(MSG["menu_channels_text"], reply_markup=builders.channels_menu_kb())

@router.callback_query(F.data == "ch_add")
async def ch_add_btn(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(MSG["ask_channel_username"], reply_markup=builders.back_kb("menu_channels"))
    await state.set_state(BotStates.waiting_for_channel)

@router.message(BotStates.waiting_for_channel)
async def save_new_channel(message: Message, state: FSMContext):
    username = message.text.replace("https://t.me/", "").replace("@", "").strip()
    success = await crud.add_channel(username)
    if success:
        await message.answer(MSG["channel_added"].format(username=username), reply_markup=builders.back_kb("menu_channels"))
    else:
        await message.answer(MSG["channel_exists"], reply_markup=builders.back_kb("menu_channels"))
    await state.clear()

@router.callback_query(F.data == "ch_list")
async def ch_list_btn(callback: CallbackQuery):
    channels = await crud.get_all_channels()
    if not channels:
        await callback.message.edit_text(MSG["empty_list"], reply_markup=builders.back_kb("menu_channels"))
        return
    ch_list = "\n".join([f"🔸 @{c['username']}" for c in channels])
    await callback.message.edit_text(MSG["channel_list"].format(list=ch_list), reply_markup=builders.back_kb("menu_channels"))

@router.callback_query(F.data == "ch_remove")
async def ch_remove_btn(callback: CallbackQuery):
    channels = await crud.get_all_channels()
    if not channels:
        await callback.message.edit_text(MSG["empty_list"], reply_markup=builders.back_kb("menu_channels"))
        return
    await callback.message.edit_text(MSG["channel_remove_prompt"], reply_markup=builders.remove_channel_kb(channels))

@router.callback_query(F.data.startswith("del_ch_"))
async def del_ch_action(callback: CallbackQuery, state: FSMContext):
    username = callback.data.split("del_ch_")[1]
    await crud.remove_channel(username)
    await callback.answer(MSG["channel_removed"], show_alert=True)
    await menu_channels(callback, state)

# ================= مدیریت هشتگ‌ها =================
@router.callback_query(F.data == "menu_hashtags")
async def menu_hashtags(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(MSG["menu_hashtags_text"], reply_markup=builders.hashtags_menu_kb())

@router.callback_query(F.data == "ht_add")
async def ht_add_btn(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(MSG["ask_hashtag"], reply_markup=builders.back_kb("menu_hashtags"))
    await state.set_state(BotStates.waiting_for_hashtag)

@router.message(BotStates.waiting_for_hashtag)
async def save_new_hashtag(message: Message, state: FSMContext):
    tag = message.text.strip()
    success = await crud.add_hashtag(tag)
    if success:
        await message.answer(MSG["hashtag_added"], reply_markup=builders.back_kb("menu_hashtags"))
    else:
        await message.answer(MSG["hashtag_exists"], reply_markup=builders.back_kb("menu_hashtags"))
    await state.clear()

@router.callback_query(F.data == "ht_list")
async def ht_list_btn(callback: CallbackQuery):
    tags = await crud.get_hashtags()
    if not tags:
        await callback.message.edit_text(MSG["empty_list"], reply_markup=builders.back_kb("menu_hashtags"))
        return
    tags_str = "\n".join([f"🔹 {t}" for t in tags])
    await callback.message.edit_text(MSG["hashtag_list"].format(list=tags_str), reply_markup=builders.back_kb("menu_hashtags"))

@router.callback_query(F.data == "ht_remove")
async def ht_remove_btn(callback: CallbackQuery):
    tags = await crud.get_hashtags()
    if not tags:
        await callback.message.edit_text(MSG["empty_list"], reply_markup=builders.back_kb("menu_hashtags"))
        return
    await callback.message.edit_text(MSG["hashtag_remove_prompt"], reply_markup=builders.remove_hashtag_kb(tags))

@router.callback_query(F.data.startswith("del_ht_"))
async def del_ht_action(callback: CallbackQuery, state: FSMContext):
    tag = callback.data.split("del_ht_")[1]
    await crud.remove_hashtag(tag)
    await callback.answer(MSG["hashtag_removed"], show_alert=True)
    await menu_hashtags(callback, state)

# ================= مدیریت ادمین‌ها =================
@router.callback_query(F.data == "menu_admins")
async def menu_admins(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(MSG["menu_admins_text"], reply_markup=builders.admins_menu_kb())

@router.callback_query(F.data == "ad_add")
async def ad_add_btn(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(MSG["ask_admin_id"], reply_markup=builders.back_kb("menu_admins"))
    await state.set_state(BotStates.waiting_for_admin)

@router.message(BotStates.waiting_for_admin)
async def save_new_admin(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer(MSG["admin_invalid"], reply_markup=builders.back_kb("menu_admins"))
        return
        
    user_id = int(message.text)
    success = await crud.add_admin(user_id)
    if success:
        await message.answer(MSG["admin_added"], reply_markup=builders.back_kb("menu_admins"))
    else:
        await message.answer(MSG["admin_exists"], reply_markup=builders.back_kb("menu_admins"))
    await state.clear()

@router.callback_query(F.data == "ad_list")
async def ad_list_btn(callback: CallbackQuery):
    admins = await crud.get_all_admins()
    if not admins:
        await callback.message.edit_text(MSG["empty_list"], reply_markup=builders.back_kb("menu_admins"))
        return
    admin_str = "\n".join([f"👤 `{a}`" for a in admins])
    await callback.message.edit_text(MSG["admin_list"].format(list=admin_str), reply_markup=builders.back_kb("menu_admins"))

@router.callback_query(F.data == "ad_remove")
async def ad_remove_btn(callback: CallbackQuery):
    admins = await crud.get_all_admins()
    if not admins:
        await callback.message.edit_text(MSG["empty_list"], reply_markup=builders.back_kb("menu_admins"))
        return
    await callback.message.edit_text(MSG["admin_remove_prompt"], reply_markup=builders.remove_admin_kb(admins))

@router.callback_query(F.data.startswith("del_ad_"))
async def del_ad_action(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("del_ad_")[1])
    await crud.remove_admin(user_id)
    await callback.answer(MSG["admin_removed"], show_alert=True)
    await menu_admins(callback, state)

# ================= آمار و گزارش‌ها =================
@router.callback_query(F.data == "menu_stats")
async def menu_stats(callback: CallbackQuery):
    stats = await crud.get_stats_data()
    
    ch_str = "\n".join([f"🔸 @{row[0]}: {row[1]} پست" for row in stats["ch_stats"]]) or "داده‌ای ثبت نشده"
    ad_str = "\n".join([f"🔹 ادمین `{row[0]}`: {row[1]} بررسی" for row in stats["ad_stats"]]) or "داده‌ای ثبت نشده"
    
    final_text = MSG["stats_report"].format(
        total_scraped=stats["scraped"],
        total_approved=stats["approved"],
        total_rejected=stats["rejected"],
        channel_stats=ch_str,
        admin_stats=ad_str
    )
    
    await callback.message.edit_text(final_text, reply_markup=builders.back_kb("menu_main"))
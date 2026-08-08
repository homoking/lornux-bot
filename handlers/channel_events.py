from aiogram import Router, F
from aiogram.types import Message
from config import TARGET_CHANNEL_ID
from database import crud

router = Router()

@router.channel_post(F.chat.id == TARGET_CHANNEL_ID)
async def auto_footer_handler(message: Message):
    """
    Monitors target channel. If a human admin posts manually, 
    appends the footer automatically.
    """
    footer = await crud.get_footer()
    if not footer:
        return
        
    # Avoid infinite loop if footer is already appended
    current_text = message.html_text or ""
    if footer in current_text:
        return
        
    new_text = f"{current_text}\n\n{footer}"
    
    try:
        if message.text:
            await message.edit_text(new_text, parse_mode="HTML")
        elif message.caption:
            await message.edit_caption(caption=new_text, parse_mode="HTML")
    except Exception as e:
        # Fails silently if message has no text/caption or lacks edit rights
        pass
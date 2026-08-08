from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from typing import Callable, Dict, Any, Awaitable
from config import OWNER_IDS
from database.crud import get_all_admins
from messages import MSG

class AdminAuthMiddleware(BaseMiddleware):
    """
    Middleware to restrict bot usage to Owners and registered Admins only.
    Silently drops updates from unauthorized users.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            
        if user_id:
            admins = await get_all_admins()
            if user_id not in OWNER_IDS and user_id not in admins:
                # Optional: Uncomment below to notify unauthorized users, or keep silent.
                # if isinstance(event, Message):
                #     await event.answer(MSG["not_authorized"])
                return # Drop the update completely
                
        return await handler(event, data)
from aiogram.fsm.state import StatesGroup, State

class BotStates(StatesGroup):
    waiting_for_footer = State()
    waiting_for_channel = State()
    waiting_for_hashtag = State()
    waiting_for_admin = State()
    waiting_for_edit = State()
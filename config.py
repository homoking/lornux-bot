import os
from typing import List
from dotenv import load_dotenv

# لود کردن متغیرهای محیطی از فایل .env
load_dotenv()

# Read env variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID", 0))

# Parse owner IDs safely
_owners_str = os.getenv("OWNER_IDS", "")
OWNER_IDS: List[int] = [int(x.strip()) for x in _owners_str.split(",") if x.strip().isdigit()]

DB_PATH = "bot_database.sqlite"
SCRAPE_INTERVAL = 60 # seconds
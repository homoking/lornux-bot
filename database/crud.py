import aiosqlite
from config import DB_PATH
from typing import List, Optional, Dict

async def get_all_admins() -> List[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM admins") as cursor:
            return [row[0] for row in await cursor.fetchall()]

# ================= توابع مدیریت کانال‌ها =================
async def get_all_channels() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id, username, last_post_id FROM channels") as cursor:
            return [dict(row) for row in await cursor.fetchall()]

async def add_channel(username: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("INSERT INTO channels (username) VALUES (?)", (username,))
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False # کانال از قبل وجود دارد

async def remove_channel(username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM channels WHERE username = ?", (username,))
        await db.commit()

async def update_channel_last_id(channel_id: int, last_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE channels SET last_post_id = ? WHERE id = ?", (last_id, channel_id))
        await db.commit()

# ================= توابع تنظیمات و لاگ =================
async def log_action(event_type: str, admin_id: int, source_channel: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO action_logs (event_type, admin_id, source_channel) VALUES (?, ?, ?)",
            (event_type, admin_id, source_channel)
        )
        await db.commit()

async def get_footer() -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key='footer'") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else ""

async def set_footer(text: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES ('footer', ?) ON CONFLICT(key) DO UPDATE SET value=?",
            (text, text)
        )
        await db.commit()

async def add_pending_post(internal_id: str, admin_id: int, msg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO pending_posts (internal_post_id, admin_id, telegram_message_id) VALUES (?, ?, ?)",
            (internal_id, admin_id, msg_id)
        )
        await db.commit()

async def get_and_delete_pending_posts(internal_id: str, exclude_admin_id: Optional[int] = None) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        query = "SELECT admin_id, telegram_message_id FROM pending_posts WHERE internal_post_id=?"
        params = [internal_id]
        if exclude_admin_id:
            query += " AND admin_id != ?"
            params.append(exclude_admin_id)
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        await db.execute("DELETE FROM pending_posts WHERE internal_post_id=?", (internal_id,))
        await db.commit()
        return [{"admin_id": r[0], "message_id": r[1]} for r in rows]

async def get_hashtags() -> List[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT tag FROM hashtags") as cursor:
            return [row[0] for row in await cursor.fetchall()]

# ================= توابع مدیریت هشتگ‌ها =================
async def add_hashtag(tag: str) -> bool:
    if not tag.startswith("#"):
        tag = f"#{tag}"
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("INSERT INTO hashtags (tag) VALUES (?)", (tag,))
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

async def remove_hashtag(tag: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM hashtags WHERE tag = ?", (tag,))
        await db.commit()

# ================= توابع مدیریت ادمین‌ها =================
async def add_admin(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("INSERT INTO admins (user_id) VALUES (?)", (user_id,))
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

async def remove_admin(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        await db.commit()

# ================= توابع آمار و گزارش‌ها =================
async def get_stats_data() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        # 1. گرفتن تعداد کل اکشن‌ها
        async with db.execute("SELECT event_type, COUNT(*) FROM action_logs GROUP BY event_type") as cursor:
            event_counts = {row[0]: row[1] for row in await cursor.fetchall()}

        # 2. آمار به تفکیک کانال
        async with db.execute("SELECT source_channel, COUNT(*) FROM action_logs WHERE event_type='SCRAPED' GROUP BY source_channel") as cursor:
            ch_stats = await cursor.fetchall()

        # 3. آمار به تفکیک ادمین
        async with db.execute("SELECT admin_id, COUNT(*) FROM action_logs WHERE event_type IN ('APPROVED', 'REJECTED') GROUP BY admin_id") as cursor:
            ad_stats = await cursor.fetchall()

        return {
            "scraped": event_counts.get("SCRAPED", 0),
            "approved": event_counts.get("APPROVED", 0),
            "rejected": event_counts.get("REJECTED", 0),
            "ch_stats": ch_stats,
            "ad_stats": ad_stats
        }
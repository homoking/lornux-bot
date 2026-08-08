import asyncio
import aiohttp
from bs4 import BeautifulSoup
import uuid
import re
from aiogram import Bot
from aiogram.types import BufferedInputFile
from config import SCRAPE_INTERVAL, OWNER_IDS
from database import crud
from messages import MSG
from keyboards.builders import review_kb

def extract_html_tags(text_div):
    """حفظ فرمت‌هایی مثل بولد و لینک بر اساس نمونه کد شما"""
    if not text_div: return ""
    for br in text_div.find_all("br"): br.replace_with("\n")
    allowed_tags = ['b', 'strong', 'i', 'em', 'u', 's', 'strike', 'del', 'a', 'code', 'pre']
    for tag in text_div.find_all(True):
        if tag.name not in allowed_tags:
            tag.unwrap()
        elif tag.name == 'a':
            href = tag.get('href', '')
            tag.attrs = {'href': href} if href else {}
        else:
            tag.attrs = {}
    return "".join(str(item) for item in text_div.contents).strip()

async def fetch_channel_posts(session: aiohttp.ClientSession, username: str, last_id: int):
    """استخراج پست‌های جدید به همراه مدیا"""
    url = f"https://t.me/s/{username}"
    try:
        async with session.get(url, timeout=15) as response:
            if response.status != 200: return []
            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")
            messages = soup.find_all("div", class_="tgme_widget_message")
            
            posts = []
            for msg in messages:
                post_id_str = msg.get("data-post", "")
                if not post_id_str: continue
                    
                post_num = int(post_id_str.split("/")[-1])
                if post_num <= last_id: continue 
                    
                text_div = msg.find("div", class_="tgme_widget_message_text")
                text = extract_html_tags(text_div)
                
                # استخراج عکس و ویدیو (Media)
                video_tag = msg.find('video')
                photo_tag = msg.find('a', class_='tgme_widget_message_photo_wrap')

                file_url, file_type = None, None
                if video_tag and video_tag.has_attr('src'):
                    file_url, file_type = video_tag['src'], 'video'
                elif photo_tag and photo_tag.has_attr('style'):
                    url_match = re.search(r"background-image:url\('(.*?)'\)", photo_tag['style'])
                    if url_match:
                        file_url, file_type = url_match.group(1), 'photo'
                
                posts.append({
                    "id": post_num,
                    "text": text,
                    "link": f"https://t.me/{username}/{post_num}",
                    "file_url": file_url,
                    "file_type": file_type
                })
            return posts
    except Exception as e:
        print(f"Scraper error for {username}: {e}")
        return []

async def scraper_loop(bot: Bot):
    while True:
        try:
            channels = await crud.get_all_channels()
            admins = await crud.get_all_admins()
            all_receivers = list(set(admins + OWNER_IDS))

            async with aiohttp.ClientSession() as session:
                for channel in channels:
                    posts = await fetch_channel_posts(session, channel["username"], channel["last_post_id"])
                    
                    # اگر پستی پیدا نشد، برو سراغ کانال بعدی
                    if not posts:
                        continue
                    
                    # 🔴 [بخش جدید ضد اسپم] 🔴
                    # اگر کانال تازه اضافه شده و آیدی پست‌هایش صفر است:
                    if channel["last_post_id"] == 0:
                        # بالاترین آیدی فعلی را پیدا کن
                        highest_id = max(post["id"] for post in posts)
                        # فقط دیتابیس را آپدیت کن تا نقطه شروع ثبت شود
                        await crud.update_channel_last_id(channel["id"], highest_id)
                        # بدون ارسال پیام، برو سراغ کانال بعدی
                        continue 
                        
                    highest_id = channel["last_post_id"]
                    for post in posts:
                        if post["id"] > highest_id: highest_id = post["id"]
                        
                        internal_id = str(uuid.uuid4())[:8]
                        header = MSG["source_header"].format(username=channel["username"], link=post["link"])
                        final_caption = f"{header}{post['text']}"
                        
                        media_bytes = None
                        if post["file_url"]:
                            async with session.get(post["file_url"]) as resp:
                                if resp.status == 200:
                                    media_bytes = await resp.read()

                        for admin_id in all_receivers:
                            try:
                                sent_msg = None
                                kb = review_kb(internal_id)
                                
                                if media_bytes and post["file_type"] == 'video':
                                    file_obj = BufferedInputFile(media_bytes, filename="video.mp4")
                                    sent_msg = await bot.send_video(admin_id, video=file_obj, caption=final_caption, reply_markup=kb, parse_mode="HTML")
                                elif media_bytes and post["file_type"] == 'photo':
                                    file_obj = BufferedInputFile(media_bytes, filename="photo.jpg")
                                    sent_msg = await bot.send_photo(admin_id, photo=file_obj, caption=final_caption, reply_markup=kb, parse_mode="HTML")
                                else:
                                    sent_msg = await bot.send_message(admin_id, final_caption, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
                                
                                await crud.add_pending_post(internal_id, admin_id, sent_msg.message_id)
                            except Exception:
                                pass 
                        
                        await crud.log_action("SCRAPED", 0, channel["username"])
                    
                    if highest_id > channel["last_post_id"]:
                        await crud.update_channel_last_id(channel["id"], highest_id)
                        
        except Exception as e:
            print(f"Loop error: {e}")
            
        await asyncio.sleep(SCRAPE_INTERVAL)
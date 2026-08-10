import asyncio
import logging
import aiohttp
from bs4 import BeautifulSoup
import uuid
import re
from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from aiogram.types import BufferedInputFile
from config import SCRAPE_INTERVAL, OWNER_IDS
from database import crud
from messages import MSG
from keyboards.builders import review_kb

logger = logging.getLogger(__name__)

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

def remove_source_watermark(html_text: str, username: str):
    """
    Detect and remove source-channel watermark lines.

    Detects:
    - @username
    - t.me/username
    - https://t.me/username
    - telegram.me/username
    - source-channel links hidden inside <a href="...">
    - bare username in short footer-like lines near the end

    Returns:
        (cleaned_html, watermark_detected)
    """

    if not html_text:
        return "", False

    username = username.strip().lstrip("@")

    if not username:
        return html_text, False

    escaped_username = re.escape(username)

    strong_patterns = [
        re.compile(
            rf"(?<![\w])@{escaped_username}\b",
            re.IGNORECASE,
        ),
        re.compile(
            rf"(?:https?://)?(?:www\.)?"
            rf"(?:t\.me|telegram\.me)/(?:s/)?"
            rf"{escaped_username}\b(?:/\d+)?/?",
            re.IGNORECASE,
        ),
        re.compile(
            rf"tg://resolve\?domain={escaped_username}\b",
            re.IGNORECASE,
        ),
    ]

    bare_username_pattern = re.compile(
        rf"(?<![\w@]){escaped_username}(?![\w])",
        re.IGNORECASE,
    )

    lines = html_text.splitlines()

    # چهار خط آخر معمولاً محل footer/watermark هستند.
    nonempty_indices = [
        index
        for index, line in enumerate(lines)
        if BeautifulSoup(
            line,
            "html.parser",
        ).get_text(" ", strip=True)
    ]

    footer_indices = set(nonempty_indices[-4:])

    cleaned_lines = []
    detected = False

    for index, line in enumerate(lines):
        fragment = BeautifulSoup(
            line,
            "html.parser",
        )

        visible_text = fragment.get_text(
            " ",
            strip=True,
        )

        hrefs = [
            tag.get("href", "")
            for tag in fragment.find_all("a")
            if tag.get("href")
        ]

        # @username یا لینک مستقیم/مخفی کانال
        strong_hit = any(
            pattern.search(visible_text)
            or any(
                pattern.search(href)
                for href in hrefs
            )
            for pattern in strong_patterns
        )

        # username بدون @ را فقط در footerهای کوتاه تشخیص بده
        bare_footer_hit = (
            index in footer_indices
            and bool(
                bare_username_pattern.search(
                    visible_text
                )
            )
            and len(visible_text) <= 80
            and len(visible_text.split()) <= 8
        )

        if strong_hit or bare_footer_hit:
            detected = True
            continue

        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)

    # فاصله‌های اضافی بعد از حذف footer
    cleaned = re.sub(
        r"\n{3,}",
        "\n\n",
        cleaned,
    ).strip()

    # اگر حذف یک خط باعث نامتوازن‌شدن HTML شده باشد،
    # BeautifulSoup آن را repair می‌کند.
    repaired = BeautifulSoup(
        cleaned,
        "html.parser",
    )

    cleaned = "".join(
        str(item)
        for item in repaired.contents
    ).strip()

    return cleaned, detected

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
    except asyncio.TimeoutError:
        logger.warning(
            "Scraper timeout for channel @%s",
            username,
        )
        return []

    except aiohttp.ClientError as exc:
        logger.warning(
            "HTTP error while scraping @%s: %r",
            username,
            exc,
        )
        return []

    except (ValueError, TypeError) as exc:
        logger.warning(
            "Invalid scraped data for @%s: %r",
            username,
            exc,
        )
        return []

    except Exception:
        logger.exception(
            "Unexpected scraper error for @%s",
            username,
        )
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

                        clean_text, watermark_detected = remove_source_watermark(
                            post["text"],
                            channel["username"],
                        )

                        if watermark_detected:
                            watermark_status = "🧹 واترمارک شناسایی شد"
                        else:
                            watermark_status = "ℹ️ واترمارک شناسایی نشد"

                        header = MSG["source_header"].format(
                            username=channel["username"],
                            link=post["link"],
                            watermark_status=watermark_status,
                        )

                        final_caption = f"{header}{clean_text}"
                        
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
                            except TelegramRetryAfter as exc:
                                logger.warning(
                                    "Rate limited while sending scraped post to admin %s. "
                                    "retry_after=%s",
                                    admin_id,
                                    exc.retry_after,
                                )

                            except TelegramForbiddenError:
                                logger.warning(
                                    "Cannot send scraped post to admin %s. "
                                    "Bot may be blocked or chat is unavailable.",
                                    admin_id,
                                )

                            except TelegramBadRequest as exc:
                                logger.warning(
                                    "Bad Telegram request while sending scraped post "
                                    "to admin %s: %s",
                                    admin_id,
                                    exc,
                                )

                            except TelegramNetworkError as exc:
                                logger.warning(
                                    "Network error while sending scraped post "
                                    "to admin %s: %s",
                                    admin_id,
                                    exc,
                                )

                            except TelegramAPIError as exc:
                                logger.warning(
                                    "Telegram API error while sending scraped post "
                                    "to admin %s: %s",
                                    admin_id,
                                    exc,
                                )

                            except Exception:
                                logger.exception(
                                    "Unexpected error while sending scraped post "
                                    "to admin %s",
                                    admin_id,
                                )
                        
                        await crud.log_action("SCRAPED", 0, channel["username"])
                    
                    if highest_id > channel["last_post_id"]:
                        await crud.update_channel_last_id(channel["id"], highest_id)
                        
        except asyncio.CancelledError:
            logger.info("Scraper loop was cancelled.")
            raise

        except Exception:
            logger.exception(
                "Unexpected error in scraper loop."
            )
            
        await asyncio.sleep(SCRAPE_INTERVAL)
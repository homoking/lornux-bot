# Lornux AI Content Assistant

بات دستیار محتوایی کانال تلگرام Lornux. RSS (و اختیاری: کانال‌های تلگرام دیگر) جمع
می‌کند، تکراری‌ها را حذف می‌کند، با یک فراخوانی ترکیبی LLM (رایگان) هرآیتم را امتیاز
می‌دهد و بازنویسی می‌کند، عکس مناسب پیدا می‌کند، پست‌های مرتبط قبلی را نشان می‌دهد، و
برای تأیید نهایی پیش از انتشار به ادمین می‌فرستد.

## وضعیت فعلی: فاز ۱ + فاز ۲ + Admin API (کد کامل)

### فاز ۱ ✅
RSS Collector، Dedup محلی (embedding رایگان)، Lornux Score، AI Rewrite ترکیبی،
Hashtag Selector، Admin Approval (تأیید/رد/بازنویسی مجدد)، Publish، مدیریت منابع از
طریق دستورات بات، Daily Digest

### فاز ۲ ✅
- **Media Finder**: تصویر مناسب برای هر پست (از RSS enclosure یا og:image صفحه‌ی مقاله) — رایگان
- **Series Detector**: نمایش پست‌های منتشرشده‌ی قبلی که به آیتم جدید مرتبط‌اند (نسخه‌ی
  ساده‌شده‌ی Knowledge Base — بر پایه‌ی شباهت embedding، نه یک entity graph کامل)
- **کانال‌های تلگرام دیگر (MTProto/Telethon)**: اختیاری و پیش‌فرض غیرفعال — نگاه کنید
  به بخش «⚠️ کانال‌های تلگرام» پایین قبل از فعال کردن

### هنوز پیاده نشده
- Knowledge Base کامل (structured entity tracking: شرکت/ابزار/تکنولوژی در طول زمان)

### آخرین فاز ✅ — Admin API
یک REST API جدا از بات برای مدیریت منابع و مشاهدهی آیتم‌ها/آمار — تأیید/رد پست‌ها عمداً فقط از طریق دکمه‌های تلگرام باقی می‌ماند (برای UX تعاملی/real-time بهتر است). نگاه کنید به بخش «۷) Admin API» پایین.

## معماری

```
Celery Beat --(هر POLL_INTERVAL_MINUTES دقیقه)--> poll_sources_task
                                                        |
                                    برای هر منبع (RSS یا کانال تلگرام)
                                                        v
                                              process_item_task
                                                        |
                              embedding محلی (رایگان) --> pgvector dedup check
                                                        |
                                        (اگر یکتا بود) --> LLM Evaluator
                                                            (Gemini free tier
                                                             --> fallback Groq free tier)
                                                        |
                                    اگر worth_posting=true و score>=threshold:
                                                        |
                                    Media Finder (عکس) + Series Detector (پست‌های مرتبط)
                                                        v
                                        پیام پیش‌نمایش (متن یا عکس+متن) + دکمه به ادمین
                                                        |
                                    ادمین: ✅ انتشار / ❌ رد / 🔄 بازنویسی مجدد

Celery Beat --(روزانه، DIGEST_HOUR_UTC)--> daily_digest_task --> گزارش به ادمین
```

## هزینه: صفر (به‌جز سرور)

- LLM: Gemini 2.5 Flash free tier (اصلی) + Groq free tier (fallback)
- Embedding: مدل local `intfloat/multilingual-e5-base` روی CPU — هیچ API call
- Media Finder: og:image از خود صفحه‌ی مقاله — هیچ API call
- محدودیت‌های free tier (RPM/RPD) را حتماً در Google AI Studio خودتان چک کنید

## راه‌اندازی

### ۱) پیش‌نیازها
- Docker + Docker Compose
- یک ربات تلگرام ساخته‌شده با @BotFather
- یک کانال تلگرام که ربات در آن ادمین است (برای انتشار)
- `chat_id` عددی خودتان به‌عنوان ادمین (با @userinfobot)
- کلید رایگان Gemini API از https://aistudio.google.com/apikey
- کلید رایگان Groq API از https://console.groq.com/keys

### ۲) تنظیم Environment
```bash
cp .env.example .env
# مقادیر TELEGRAM_*, GEMINI_API_KEY, GROQ_API_KEY را در .env پر کنید
```

### ۳) اجرا با Docker Compose
```bash
docker compose up -d --build
```

### ۴) اضافه کردن منابع
از طریق دستورات بات (در چت خصوصی با بات):
```
/addsource https://techcrunch.com/feed/ TechCrunch
/sources
```
یا با اسکریپت seed:
```bash
docker compose exec bot python -m scripts.seed_sources
```

### ۵) دستورات مدیریت منابع (فقط ادمین)

| دستور | کاربرد |
|---|---|
| `/addsource <url> [نام]` | افزودن منبع RSS |
| `/addchannel <username> [نام]` | افزودن کانال تلگرام (نیاز به راه‌اندازی MTProto — پایین را بخوانید) |
| `/sources` | نمایش لیست منابع با وضعیت و شناسه‌ی کوتاه |
| `/enable <id>` / `/disable <id>` | فعال/غیرفعال کردن |
| `/blacklist <id>` / `/unblacklist <id>` | قرار دادن یا خارج کردن از لیست سیاه |
| `/rating <id> <1-5>` | تنظیم امتیاز اعتبار منبع (در پرامپت LLM استفاده می‌شود) |

`<id>` همان ۸ کاراکتر اول UUID منبع است که در خروجی `/sources` نمایش داده می‌شود.

### ۶) بررسی که همه‌چیز کار می‌کند
```bash
docker compose logs -f worker beat bot
```

### ۷) Admin API

یک REST API جدا روی پورت ۸۰۰۰ بالا می‌آید (سرویس `api` در docker-compose). همه‌ی اندپوینت‌ها (بهجز `/health`) نیاز به هدر `x-api-key: <ADMIN_API_KEY>` دارند.

| متد و مسیر | کاربرد |
|---|---|
| `GET /health` | سلامتی سرویس (بدون auth) |
| `GET /sources` | لیست همه‌ی منابع |
| `POST /sources` | افزودن منبع RSS جدید (`{"url": ..., "name": ..., "rating": ...}`) |
| `PATCH /sources/{short_id}` | تغییر `is_active` / `is_blacklisted` / `rating` |
| `GET /items?status_filter=pending_approval&limit=50` | لیست آیتم‌ها به‌همراه آخرین evaluation هرکدام |
| `GET /digest/today` | همان گزارش روزانه‌ای که به ادمین در تلگرام می‌رود، به‌صورت JSON |

**تصمیم آگاهانه:** تأیید/رد نهایی پست‌ها عمداً فقط از طریق دکمه‌های تلگرام می‌ماند — آن تصمیم تعاملی و لحظه‌ای است، تلگرام برای آن UX بهتری دارد.

**امنیت:** `ADMIN_API_KEY` را حتماً یک مقدار قوی و تصادفی بگذارید (`openssl rand -hex 32`). اگر این API را فراتر از localhost/شبکه‌ی داخلی expose می‌کنید، حتماً پشت یک reverse proxy با HTTPS بگذارید — API key بدون TLS قابل شنود است.

تست‌شده (۱۳ سناریو: auth، CRUD منابع، فیلتر آیتم‌ها، serialization کامل evaluation) روی Postgres واقعی در sandbox توسعه‌دهنده (نه روی Docker واقعی شما).

---

## ⚠️ کانال‌های تلگرام دیگر (MTProto) — قبل از فعال کردن حتماً بخوانید

این قابلیت **پیش‌فرض خاموش** است (`MTPROTO_ENABLED=false`) و باید آگاهانه فعال شود.

**تفاوت کلیدی:** بر خلاف بقیه‌ی پروژه که فقط با Bot API کار می‌کند، این بخش از یک
**اکانت شخصی/کاربری واقعی تلگرام** (MTProto، از طریق Telethon) استفاده می‌کند تا به
کانال‌های دیگری دسترسی پیدا کند که بات شما در آن‌ها ادمین نیست.

**ریسک واقعی:** استفاده‌ی خودکار و مکرر از یک اکانت کاربری برای خواندن کانال‌ها می‌تواند
با سیستم‌های ضد اسپم تلگرام تداخل داشته باشد و در موارد نادر به محدودیت یا تعلیق اکانت
منجر شود.

**توصیه‌های ما:**
- از یک شماره‌ی تلفن جداگانه استفاده کنید، نه اکانت شخصی اصلی‌تان
- فرکانس poll را پایین نگه دارید (پیش‌فرض پروژه کافی است: هر ۲۰ دقیقه)
- تعداد کانال‌هایی که اضافه می‌کنید را محدود نگه دارید
- این قابلیت را فقط با آگاهی کامل از ریسک فعال کنید

**راه‌اندازی:**
```bash
# ۱. از https://my.telegram.org یک api_id و api_hash بگیرید
# ۲. به‌صورت محلی (نه در Docker) اجرا کنید:
pip install telethon
python scripts/telegram_login.py
# با شماره‌تلفن، کد تأیید، و (در صورت 2FA) رمزتان یک‌بار لاگین کنید
# خروجی session_string را کپی کنید

# ۳. در .env:
MTPROTO_ENABLED=true
TELEGRAM_API_ID=<از قدم ۱>
TELEGRAM_API_HASH=<از قدم ۱>
TELEGRAM_SESSION_STRING=<از قدم ۲>

# ۴. کانال اضافه کنید:
docker compose restart bot worker beat
# در چت با بات: /addchannel channel_username
```

**صداقت فنی:** این بخش (`app/services/telegram_collector.py`, `scripts/telegram_login.py`)
در sandbox من قابل تست end-to-end نبود چون به یک اکانت واقعی تلگرام و دسترسی شبکه به
`api.telegram.org` نیاز دارد که در محیط تست من مجاز نبود. فقط از نظر import/syntax و
منطق دیسپچ (RSS در برابر تلگرام) بررسی شده. اولین بار که فعالش می‌کنید، با احتیاط و
روی یک کانال تست شروع کنید.

---

## نکات مهم قبل از استفاده‌ی واقعی

- [ ] **تست کیفیت پرامپت**: چند ده آیتم واقعی را در Google AI Studio با
      `app/services/llm/prompt.py` تست کنید و few-shot examples را با نمونه‌های
      تأییدشده‌ی خودتان جایگزین/تکمیل کنید.
- [ ] **SDK Gemini**: `app/services/llm/gemini_client.py` بر اساس `google-genai`
      نوشته شده؛ امضای دقیق را قبل از اجرای واقعی با https://ai.google.dev/gemini-api/docs
      تطبیق دهید.
- [ ] **آستانه‌ها**: `DEDUP_SIMILARITY_THRESHOLD` (۰.۹۲)، `RELATED_SIMILARITY_THRESHOLD`
      (۰.۸۰)، و `SCORE_WORTH_POSTING_THRESHOLD` (۶۵) حدس‌های مهندسی منطقی‌اند — بعد از
      دیدن چند روز خروجی واقعی تنظیمشان کنید.
- [ ] **Rate limit واقعی**: `GEMINI_RPM_LIMIT` / `GEMINI_RPD_LIMIT` را با صفحه‌ی quota
      حساب Google خودتان مطابقت دهید.
- [ ] **MTProto**: اگر فعالش می‌کنید، حتماً بخش بالا را کامل بخوانید و با احتیاط شروع کنید.

## توسعه‌ی محلی (بدون Docker)

```bash
python -m venv .venv
source .venv/bin/activate  # ویندوز: .venv\Scripts\activate
pip install -r requirements.txt

# Postgres و Redis باید جداگانه بالا باشند
alembic upgrade head
python -m scripts.seed_sources

# در سه ترمینال جدا:
python -m app.bot.main
celery -A app.tasks.celery_app worker --loglevel=info
celery -A app.tasks.celery_app beat --loglevel=info
```

## قدم‌های بعدی (فراتر از همه‌ی فاز‌های بالا — هنوز پیاده‌سازی نشده)

- Knowledge Base کامل (structured entity tracking در طول زمان — فعلاً فقط یک Series Detector ساده بر پایه‌ی شباهت embedding داریم)
- احراز هویت قوی‌تر برای Admin API (مثلاً JWT/OAuth به‌جای API key ثابت، اگر قرار بود چند نفر به آن دسترسی داشته باشند)
- تست‌های خودکار (pytest suite) — تا اینجا تست‌ها دستی و در طی توسعه اجرا شده‌اند؛ تبدیل به یک مجموعه‌ی pytest رسمی برای CI ارزش‌مند است

# 🤖 Lornux Bot

> A lightweight, asynchronous Telegram content monitoring and moderation bot built with **Python**, **Aiogram 3**, **SQLite**, and **aiohttp**.

Lornux Bot monitors selected Telegram channels, detects new posts, sends them to authorized administrators for review, and allows approved content to be edited, tagged, and published to a destination channel.

It also provides a simple Telegram-based administration panel for managing monitored channels, administrators, hashtags, footer text, and activity statistics.

---

## ✨ Features

### 📡 Telegram Channel Monitoring

* Monitor multiple Telegram channels.
* Automatically detect newly published posts.
* Track the latest processed post for each channel.
* Prevent old posts from flooding administrators when a channel is added for the first time.
* Extract post text while preserving supported HTML formatting.
* Detect and download supported photo and video media.

---

### 👀 Multi-Admin Review System

Every detected post can be delivered to all authorized reviewers.

Administrators can:

* ✅ **Approve** a post
* ❌ **Reject** a post
* ✏️ **Edit** the post before publishing

Once one administrator begins processing a post, pending copies can be removed from the other administrators to avoid duplicate moderation.

---

### ✏️ Post Editing

Approved content does not have to be published exactly as it appeared in the source channel.

An administrator can:

1. Select **Edit**
2. Submit new text
3. Select hashtags
4. Confirm publication

The original media is preserved while the edited text is used as the new caption or message body.

---

### 🏷️ Hashtag Management

Administrators can maintain a reusable list of hashtags directly from Telegram.

Supported actions include:

* ➕ Add hashtags
* 📋 View existing hashtags
* ➖ Remove hashtags
* ✅ Select multiple hashtags before publication

If the `#` prefix is omitted while adding a hashtag, the bot adds it automatically.

---

### 📝 Automatic Footer

A configurable footer can be appended to published content.

The footer can be updated directly from the bot's administration panel.

It is used when publishing reviewed posts and can also be appended automatically to manually published text/caption content in the configured target channel.

---

### 📢 Channel Management

Monitored channels can be managed without editing the source code.

Administrators can:

* ➕ Add a channel
* 📋 View monitored channels
* ➖ Remove a channel

Both of the following input formats are accepted when adding channels:

```text
channel_username
@channel_username
https://t.me/channel_username
```

Internally, only the username is stored.

---

### 👥 Administrator Management

Access to the bot is restricted to:

* 👑 Owners configured through `.env`
* 👤 Administrators stored in the SQLite database

Authorized users can manage additional administrators directly from the Telegram interface.

---

### 📊 Statistics & Activity Logs

The bot records important moderation events.

Currently tracked events include:

```text
SCRAPED
APPROVED
REJECTED
EDITED
```

The statistics panel displays:

* 📥 Total scraped posts
* ✅ Total approved posts
* ❌ Total rejected posts
* 📢 Scraped posts per source channel
* 👤 Moderation activity per administrator

---

## 🔄 How It Works

The main workflow looks like this:

```text
Telegram Source Channels
          │
          ▼
   🔎 Scraper Loop
          │
          ▼
    New Post Found
          │
          ▼
 ┌─────────────────────┐
 │ Send to Admins      │
 │ with review buttons │
 └─────────────────────┘
          │
          ▼
 ┌────────────┬────────────┬─────────────┐
 │ ✅ Approve │ ❌ Reject │ ✏️ Edit    │
 └────────────┴────────────┴─────────────┘
          │
          ▼
     🏷️ Select Tags
          │
          ▼
     📝 Add Footer
          │
          ▼
  🚀 Publish to Target
        Channel
```

---

## 🧠 First-Time Channel Behavior

When a channel is added for the first time, its stored `last_post_id` is `0`.

The bot intentionally **does not send all existing posts** from that channel to administrators.

Instead, it:

1. Reads the currently visible posts.
2. Finds the highest post ID.
3. Stores that ID as the starting point.
4. Begins monitoring posts published after that point.

This prevents large amounts of historical content from being sent immediately after adding a channel.

---

## 🏗️ Project Structure

```text
lornux-bot/
│
├── database/
│   ├── __init__.py
│   ├── connection.py
│   └── crud.py
│
├── handlers/
│   ├── __init__.py
│   ├── admin_panel.py
│   ├── channel_events.py
│   └── review.py
│
├── keyboards/
│   ├── __init__.py
│   └── builders.py
│
├── middlewares/
│   ├── __init__.py
│   └── auth.py
│
├── scraper/
│   ├── __init__.py
│   └── task.py
│
├── utils/
│   ├── __init__.py
│   └── states.py
│
├── .gitignore
├── config.py
├── dumper.bat
├── main.py
├── messages.py
└── requirements.txt
```

---

## 🧩 Architecture Overview

### `main.py`

The application entry point.

Responsible for:

* Initializing the SQLite database
* Creating the Aiogram bot
* Creating the dispatcher
* Registering authentication middleware
* Registering routers
* Configuring Telegram bot commands
* Starting the scraper task
* Starting Telegram polling

---

### `config.py`

Loads configuration values from environment variables using `python-dotenv`.

Currently supports:

```env
BOT_TOKEN
TARGET_CHANNEL_ID
OWNER_IDS
```

It also contains local configuration values such as:

```python
DB_PATH = "bot_database.sqlite"
SCRAPE_INTERVAL = 60
```

---

### `database/`

Handles SQLite persistence using asynchronous `aiosqlite`.

The database stores:

* Monitored channels
* Administrators
* Hashtags
* Bot settings
* Pending moderation posts
* Activity logs

---

### `handlers/admin_panel.py`

Implements the Telegram administration interface.

Responsible for:

* Main menu
* Channel management
* Hashtag management
* Administrator management
* Footer configuration
* Statistics

---

### `handlers/review.py`

Handles the moderation workflow.

Responsible for:

* Approving posts
* Rejecting posts
* Editing posts
* Cleaning pending copies
* Selecting hashtags
* Publishing final posts

---

### `handlers/channel_events.py`

Monitors the configured destination channel and attempts to append the configured footer to applicable manually published text or caption content.

---

### `scraper/task.py`

Contains the Telegram channel scraper.

It:

* Requests Telegram's public channel page
* Parses posts using BeautifulSoup
* Extracts supported HTML formatting
* Detects photos and videos
* Downloads media
* Sends new content to reviewers
* Updates the latest processed post ID
* Records scraping activity

---

### `middlewares/auth.py`

Protects bot functionality from unauthorized users.

An incoming user is allowed when their Telegram user ID exists in either:

```text
OWNER_IDS
```

or the database-backed administrator list.

Unauthorized updates are silently ignored.

---

### `keyboards/builders.py`

Contains reusable inline keyboard builders for:

* Main menu
* Channel management
* Hashtag management
* Administrator management
* Review actions
* Hashtag selection
* Navigation buttons

---

### `messages.py`

Centralizes the bot's user-facing text.

Keeping messages separate makes interface text easier to maintain without modifying handler logic.

---

### `utils/states.py`

Defines Aiogram FSM states for interactive operations such as:

* Updating the footer
* Adding channels
* Adding hashtags
* Adding administrators
* Editing posts

---

## 🗄️ Database Schema

The database is automatically initialized when the bot starts.

No manual database migration is currently required.

### `channels`

Stores monitored Telegram channels.

```text
id
username
last_post_id
```

---

### `admins`

Stores authorized administrator Telegram IDs.

```text
user_id
```

---

### `hashtags`

Stores reusable publication hashtags.

```text
id
tag
```

---

### `settings`

Stores configurable bot settings.

```text
key
value
```

The footer is currently stored using:

```text
key = footer
```

---

### `pending_posts`

Tracks moderation messages delivered to administrators.

```text
internal_post_id
admin_id
telegram_message_id
```

This allows the bot to remove pending copies after another administrator processes the post.

---

### `action_logs`

Stores activity information.

```text
id
event_type
admin_id
source_channel
timestamp
```

---

# 🚀 Installation

## 1. Clone the Repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd lornux-bot
```

---

## 2. Create a Virtual Environment

### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

The project currently uses:

* `aiogram`
* `aiosqlite`
* `aiohttp`
* `beautifulsoup4`
* `python-dotenv`

---

# ⚙️ Configuration

Create a `.env` file in the project root:

```env
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
TARGET_CHANNEL_ID=-1001234567890
OWNER_IDS=123456789,987654321
```

---

## 🔑 `BOT_TOKEN`

The Telegram bot token.

Example:

```env
BOT_TOKEN=1234567890:YOUR_BOT_TOKEN
```

Keep this value private.

Never commit your real token to Git.

---

## 📢 `TARGET_CHANNEL_ID`

The numeric ID of the Telegram channel where approved posts should be published.

Example:

```env
TARGET_CHANNEL_ID=-1001234567890
```

The bot must have the permissions required to publish and edit applicable posts in this channel.

---

## 👑 `OWNER_IDS`

Comma-separated Telegram user IDs that always have access to the bot.

Example:

```env
OWNER_IDS=123456789,987654321
```

You can configure a single owner:

```env
OWNER_IDS=123456789
```

Or multiple owners:

```env
OWNER_IDS=123456789,987654321,1122334455
```

---

# ▶️ Running the Bot

Start the application with:

```bash
python main.py
```

You should see a log similar to:

```text
Bot is starting...
```

The bot will then:

1. Initialize the SQLite database.
2. Register handlers and middleware.
3. Configure the `/start` Telegram command.
4. Start the scraper loop.
5. Start polling Telegram updates.

---

# 🎛️ Using the Admin Panel

Send:

```text
/start
```

to the bot.

The main menu provides access to:

```text
📢 Channel Management
🏷️ Hashtag Management
👥 Admin Management
📝 Footer Settings
📊 Statistics
```

---

## 📢 Adding a Source Channel

Open:

```text
📢 Channel Management
        ↓
➕ Add Channel
```

Then submit the channel username.

Example:

```text
examplechannel
```

After registration, the bot initializes the channel's current post position and starts watching for future posts.

---

## 🏷️ Adding Hashtags

Open:

```text
🏷️ Hashtag Management
        ↓
➕ Add Hashtag
```

You may enter:

```text
technology
```

or:

```text
#technology
```

Both are stored as:

```text
#technology
```

---

## 👤 Adding Administrators

Open:

```text
👥 Admin Management
       ↓
➕ Add Admin
```

Enter the user's numeric Telegram ID:

```text
123456789
```

The user will then be recognized by the authentication middleware as an authorized administrator.

---

## 📝 Configuring the Footer

Open:

```text
📝 Footer Settings
```

Send the desired footer text.

Example:

```html
<b>Follow our channel for more updates 🚀</b>
```

The bot stores the submitted HTML-formatted message and uses it when preparing publication content.

---

# ✅ Reviewing Posts

When the scraper detects a new post, authorized reviewers receive it along with:

```text
✅ Approve
❌ Reject
✏️ Edit
```

---

## ✅ Approve

Selecting **Approve** starts hashtag selection.

The administrator can enable or disable available hashtags and then select:

```text
🚀 Final Confirm & Send
```

The final content is assembled as:

```text
Post Content

#selected #hashtags

Configured Footer
```

and sent to the configured target channel.

---

## ❌ Reject

Selecting **Reject**:

* Records a `REJECTED` event.
* Removes other pending reviewer copies where possible.
* Removes the moderation buttons from the processed message.
* Marks the post as rejected.

The content is not published.

---

## ✏️ Edit

Selecting **Edit** allows an administrator to replace the original text before publication.

The workflow becomes:

```text
Original Post
     ↓
✏️ Edit
     ↓
Enter New Text
     ↓
Select Hashtags
     ↓
Add Footer
     ↓
🚀 Publish
```

For media posts, the original media is retained while the edited text is used for publication.

---

# 📊 Statistics

The statistics section provides a simple overview of bot activity.

Example information includes:

```text
📥 Total scraped posts
✅ Total approvals
❌ Total rejections

📈 Activity by channel
👤 Moderation activity by admin
```

This information is generated from the `action_logs` database table.

---

# 🌐 Scraper Behavior

The scraper reads Telegram public channel pages using:

```text
https://t.me/s/<channel_username>
```

BeautifulSoup is used to parse the returned HTML.

Supported post information currently includes:

* Text
* Telegram post link
* Basic Telegram-compatible HTML formatting
* Photos
* Videos

The following HTML tags are preserved by the scraper where present:

```html
<b>
<strong>
<i>
<em>
<u>
<s>
<strike>
<del>
<a>
<code>
<pre>
```

Unsupported HTML tags are removed while their text content is preserved.

---

# ⏱️ Scraping Interval

The default scraper interval is:

```python
SCRAPE_INTERVAL = 60
```

which means the bot checks monitored channels approximately every:

```text
60 seconds
```

You can change this value in:

```text
config.py
```

Example:

```python
SCRAPE_INTERVAL = 120
```

for a two-minute interval.

---

# 🛡️ Security

Several basic security measures are already part of the project.

### 🔐 Environment Variables

Secrets are loaded from `.env` instead of being hardcoded.

The `.gitignore` excludes:

```text
.env
.env.local
```

Never publish these files.

---

### 👤 Access Control

The administration interface is protected by `AdminAuthMiddleware`.

Access is limited to:

```text
OWNER_IDS
+
database administrators
```

Unauthorized users are silently ignored.

---

### 🗃️ Database Protection

Local database files are excluded from Git:

```text
*.sqlite
*.sqlite3
*.db
bot_database.sqlite
```

This helps prevent accidentally publishing operational data.

---

# 📁 Ignored Files

The project `.gitignore` excludes common development and sensitive files, including:

```text
.env
.venv/
venv/
env/
*.sqlite
*.sqlite3
*.db
__pycache__/
*.pyc
.pytest_cache/
.vscode/
.idea/
*.log
.DS_Store
Thumbs.db
```

---

# 🛠️ Project Dump Utility

The repository includes:

```text
dumper.bat
```

This Windows utility creates a text dump of the project source code and project tree.

Run:

```powershell
dumper.bat
```

to dump the current directory.

You can also provide another project path:

```powershell
dumper.bat "E:\path\to\project"
```

The generated output is:

```text
project_dump.txt
```

The utility automatically excludes common environments, caches, databases, binaries, IDE folders, and secret environment files.

---

# ⚠️ Current Scope & Limitations

This project intentionally keeps its architecture lightweight.

Based on the current implementation:

* Channel monitoring is based on Telegram's public web channel view.
* The scraper currently has explicit extraction logic for text, photos, and videos.
* A newly added channel does not backfill its existing visible posts.
* SQLite is used as the persistent data store.
* The scraper runs as an asynchronous task inside the bot process.
* Scraping failures are retried naturally during future scraper iterations.
* There is currently no separate web dashboard.
* Administration is performed directly through Telegram.
* There is currently no external queue or worker service.
* There is currently no database migration framework.

These are implementation characteristics of the current version rather than requirements for future versions.

---

# 🧰 Technology Stack

| Technology       | Purpose                            |
| ---------------- | ---------------------------------- |
| 🐍 Python        | Core application                   |
| 🤖 Aiogram 3     | Telegram Bot framework             |
| 🗃️ SQLite       | Local persistent database          |
| ⚡ aiosqlite      | Async SQLite access                |
| 🌐 aiohttp       | Async HTTP requests                |
| 🍲 BeautifulSoup | Telegram HTML parsing              |
| 🔐 python-dotenv | Environment configuration          |
| 🔄 asyncio       | Background asynchronous processing |

---

# 🔧 Development

A typical development setup is:

```bash
git clone <repository>
cd lornux-bot

python -m venv .venv
```

Activate the environment and install dependencies:

```bash
pip install -r requirements.txt
```

Create:

```text
.env
```

Then start the bot:

```bash
python main.py
```

---

# 🧭 Example End-to-End Workflow

Imagine the bot is monitoring:

```text
@source_channel
```

and a new post appears.

### Step 1 — Detection

The scraper detects the new post.

```text
@source_channel
       ↓
New Telegram Post
```

### Step 2 — Review

Every authorized reviewer receives something similar to:

```text
📥 Source: @source_channel
🔗 Post Link: https://t.me/source_channel/123

Original post content...
```

with:

```text
✅ Approve   ❌ Reject
      ✏️ Edit
```

### Step 3 — Moderation

An administrator approves or edits the content.

### Step 4 — Hashtags

The bot displays configured hashtags:

```text
✅ #news
❌ #technology
✅ #telegram
❌ #python
```

### Step 5 — Publication

After final confirmation:

```text
Final post content...

#news #telegram

Configured footer
```

is published to:

```text
TARGET_CHANNEL_ID
```

---

# 📌 Recommended Deployment Checklist

Before running the bot in production, verify:

* [ ] Python is installed.
* [ ] Dependencies are installed.
* [ ] `.env` exists.
* [ ] `BOT_TOKEN` is configured.
* [ ] `TARGET_CHANNEL_ID` is correct.
* [ ] At least one `OWNER_IDS` value is configured.
* [ ] The bot has the necessary permissions in the target channel.
* [ ] Administrators are able to receive bot messages.
* [ ] Source channels are accessible to the scraper.
* [ ] `.env` is not committed to Git.
* [ ] The SQLite database is stored in a persistent location.

---

# 🔮 Possible Future Improvements

The current architecture provides a good foundation for further development.

Potential extensions could include:

* 🧪 Automated test coverage
* 🐳 Docker support
* 📝 Structured application logging
* 🔁 Better retry and recovery strategies
* 📊 Advanced analytics
* 🗄️ PostgreSQL support
* ⚡ Redis-backed processing
* 🌐 Web-based administration dashboard
* 📦 Album / media-group support
* 🖼️ Additional Telegram media types
* 🔔 Monitoring health notifications
* 📈 Per-admin approval/rejection breakdown
* 🧹 Automatic cleanup of old operational logs
* ⚙️ Configurable scraping interval from the admin panel

These are future ideas and are **not part of the current implementation**.

---

# 🤝 Contributing

Contributions and improvements are welcome.

A typical contribution workflow:

```bash
git checkout -b feature/my-feature
git add .
git commit -m "Add my feature"
git push origin feature/my-feature
```

Then open a Pull Request describing:

* What changed
* Why it was changed
* How it was tested

---

# 🔐 Important Security Notice

Never expose:

```text
BOT_TOKEN
.env
bot_database.sqlite
```

in a public repository.

If a Telegram bot token is accidentally exposed, replace/revoke it through Telegram's bot management tools before continuing to use the bot.

---

# 💡 Summary

**Lornux Bot** provides a simple moderation pipeline between Telegram source channels and a destination channel.

Its core philosophy is:

```text
Monitor → Review → Edit → Tag → Publish
```

with:

* 📡 Automated channel monitoring
* 👥 Multi-admin moderation
* ✏️ Content editing
* 🏷️ Hashtag selection
* 📝 Automatic footer support
* 📊 Activity statistics
* 🔐 Administrator access control
* ⚡ Fully asynchronous Python architecture

Built with Python and Aiogram for a lightweight and practical Telegram content workflow. 🚀

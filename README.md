<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:6C63FF,100:48CAE4&height=200&section=header&text=TuneBot&fontSize=80&fontColor=ffffff&animation=fadeIn&fontAlignY=38&desc=Premium%20Telegram%20Music%20Bot&descAlignY=60&descSize=20" width="100%" />

<br/>

[![Python](https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Pyrogram](https://img.shields.io/badge/Pyrogram-2.0-orange?style=for-the-badge&logo=telegram&logoColor=white)](https://pyrogram.org)
[![PyTgCalls](https://img.shields.io/badge/PyTgCalls-3.0-green?style=for-the-badge&logo=telegram&logoColor=white)](https://pytgcalls.github.io)
[![MongoDB](https://img.shields.io/badge/MongoDB-7.0-brightgreen?style=for-the-badge&logo=mongodb&logoColor=white)](https://mongodb.com)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

<br/>

**TuneBot** is a powerful, production-ready Telegram Music Bot that streams high-quality audio directly into Telegram Group Voice Chats. Built with Pyrogram + PyTgCalls, backed by MongoDB, and supporting YouTube, Spotify, and more.

<br/>

---

## ⚡ One-Click Deploy

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/yourname/TuneBot)
&nbsp;&nbsp;
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/yourname/TuneBot)
&nbsp;&nbsp;
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/yourname/TuneBot)

---

</div>

## 🎵 Features

### 🎶 Audio Sources
- **YouTube** search by song name or direct URL
- **YouTube Playlists** — queue an entire playlist at once
- **Spotify** tracks, albums, and playlists (auto-resolves to YouTube)
- **Telegram Audio** — reply to any audio/voice message with `/play`

### 🎛 Playback Controls
| Feature | Description |
|---|---|
| ▶️ Play / Queue | Instant play or queue when busy |
| ⏭ Skip | Skip one or N tracks |
| ⏸ Pause / ▶️ Resume | Full playback control |
| ⏩ Seek | Jump to any timestamp |
| 🔊 Volume | 1–200% volume control |
| 🔂 Loop Track | Repeat the current track |
| 🔁 Loop Queue | Repeat the entire queue |
| 🔀 Shuffle | Randomize queue order |
| 🔁 24/7 Mode | Stay in VC even when queue is empty |

### 🛡 Security & Safety
- Environment variable validation on startup
- Anti-spam cooldown per user
- Force-subscribe channel support
- Admin-only playback commands
- Safe subprocess handling for downloads
- User ban system (database-backed)

### 🚀 Deployment
- **Docker** + Docker Compose (single command)
- **Heroku** worker dyno with FFmpeg buildpack
- **Railway** Dockerfile deploy
- **Render** worker service
- **Termux** Android deployment
- Multi-assistant support (parallel VC sessions)

---

## 📋 Command Reference

| Command | Description | Permission |
|---|---|---|
| `/play <query\|URL>` | Play a song, YouTube or Spotify link | All users |
| `/vplay <query\|URL>` | Alias for /play | All users |
| `/skip [n]` | Skip current or next N tracks | Admin |
| `/pause` | Pause playback | Admin |
| `/resume` | Resume playback | Admin |
| `/stop` | Stop and clear queue | Admin |
| `/seek <seconds>` | Seek to position | Admin |
| `/volume <1-200>` | Set playback volume | Admin |
| `/loop [off\|track\|queue]` | Set loop mode | Admin |
| `/shuffle` | Shuffle the queue | Admin |
| `/queue` | View current queue | All users |
| `/lyrics [song]` | Get lyrics | All users |
| `/ping` | Check bot response time | All users |
| `/stats` | Bot and system statistics | All users |
| `/247` | Toggle 24/7 mode | Admin |
| `/speedtest` | Run network speed test | Owner |
| `/restart` | Restart the bot | Owner |

---

## 📁 Repository Structure

```
TuneBot/
│
├── __main__.py              # Entry point
│
├── config/
│   ├── __init__.py
│   └── config.py            # Environment variables & validation
│
├── core/
│   ├── __init__.py
│   ├── bot.py               # Client manager & plugin loader
│   └── call_manager.py      # PyTgCalls voice chat controller
│
├── plugins/
│   ├── __init__.py
│   ├── play.py              # /play, /vplay + playlist/Spotify logic
│   ├── controls.py          # /skip /pause /resume /stop /seek /volume /loop /shuffle
│   ├── utility.py           # /ping /stats /lyrics /speedtest /restart
│   ├── start.py             # /start /help /247
│   └── stream_events.py     # Auto-advance queue on stream end
│
├── helpers/
│   ├── __init__.py
│   ├── logger.py            # Structured logging (console + rotating file)
│   ├── downloader.py        # yt-dlp audio downloader with fallback
│   ├── spotify.py           # Spotify URL resolver
│   ├── ui.py                # Message formatters & inline keyboards
│   └── guards.py            # Cooldown, admin-only, sudo-only, force-sub
│
├── database/
│   ├── __init__.py
│   └── mongodb.py           # Motor async MongoDB client
│
├── downloads/               # Temporary audio files (auto-cleaned)
├── cache/                   # Thumbnail and metadata cache
├── logs/                    # Rotating log files
│
├── .env.example             # All environment variables documented
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── Procfile                 # Heroku
├── app.json                 # Heroku config
├── render.yaml              # Render config
├── railway.json             # Railway config
├── runtime.txt
└── termux_setup.sh
```

---

## 🛠 Setup Guide

### Prerequisites

- Python 3.12+
- FFmpeg
- MongoDB (local or Atlas)
- Telegram API credentials
- At least one Pyrogram string session (assistant account)

### 1. Get Your Credentials

#### Telegram API
1. Visit [https://my.telegram.org/apps](https://my.telegram.org/apps)
2. Create a new app and copy `API_ID` and `API_HASH`

#### Bot Token
1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the instructions
3. Copy the bot token

#### Assistant Session (String Session)
You need at least one Telegram account (not the bot) to join voice chats:

```bash
# Generate a Pyrogram string session
python3 -c "
from pyrogram import Client
import asyncio

async def gen():
    async with Client(
        'session',
        api_id=YOUR_API_ID,
        api_hash='YOUR_API_HASH'
    ) as app:
        print(await app.export_session_string())

asyncio.run(gen())
"
```

#### MongoDB
- **Cloud (recommended):** [MongoDB Atlas](https://cloud.mongodb.com) — free tier available
- **Local:** Install MongoDB Community and use `mongodb://localhost:27017/`

---

### 2. Local Installation

```bash
# Clone the repository
git clone https://github.com/yourname/TuneBot.git
cd TuneBot

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

#### Install FFmpeg

**Ubuntu/Debian:**
```bash
sudo apt-get update && sudo apt-get install -y ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
Download from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html) and add to PATH.

**Termux (Android):**
```bash
pkg install ffmpeg
```

### 3. Configure Environment

```bash
cp .env.example .env
nano .env   # Fill in all required values
```

Minimum required variables:
```env
API_ID=12345678
API_HASH=abcdef...
BOT_TOKEN=123456789:AAB...
STRING_SESSIONS=BQA...yoursession...
MONGO_DB_URI=mongodb+srv://...
OWNER_ID=123456789
```

### 4. Run the Bot

```bash
python3 -m __main__
```

You should see:
```
2024-01-01 12:00:00 | INFO     | core.bot | ✅ MongoDB connected.
2024-01-01 12:00:01 | INFO     | core.bot | 🤖 Bot logged in as @TuneBot (123456789)
2024-01-01 12:00:02 | INFO     | core.bot | 🎸 Assistant 1 logged in as @assistant (987654321)
2024-01-01 12:00:02 | INFO     | core.bot | 📦 5 plugins loaded.
2024-01-01 12:00:02 | INFO     | __main__ | ✅ TuneBot is now running!
```

---

## 🐳 Docker Deployment

```bash
# Copy and fill environment
cp .env.example .env

# Build and run (includes MongoDB)
docker-compose up -d

# View logs
docker-compose logs -f tunebot
```

---

## ☁️ Cloud Deployment

### Heroku
1. Click the **Deploy to Heroku** button above
2. Fill in all environment variables in the Heroku dashboard
3. Make sure the `worker` dyno is enabled (not `web`)

> ⚠️ Heroku requires the [FFmpeg buildpack](https://github.com/jonathanong/heroku-buildpack-ffmpeg-latest). It's included in `app.json`.

### Railway
1. Click the **Deploy on Railway** button above
2. Connect your GitHub account
3. Set environment variables in the Railway dashboard

### Render
1. Click the **Deploy to Render** button above
2. Select **Background Worker** (not Web Service)
3. Fill in all environment variables

---

## 📱 Termux (Android)

```bash
# Clone and run setup
git clone https://github.com/yourname/TuneBot.git
cd TuneBot
bash termux_setup.sh

# Configure and run
cp .env.example .env
nano .env
python3 -m __main__
```

---

## 🔧 Spotify Setup

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/)
2. Click **Create App**
3. Copy **Client ID** and **Client Secret**
4. Set in `.env`:
   ```env
   SPOTIFY_CLIENT_ID=your_client_id
   SPOTIFY_CLIENT_SECRET=your_client_secret
   ```

---

## 🎤 Lyrics Setup

1. Go to [Genius API Clients](https://genius.com/api-clients)
2. Create a new API client
3. Copy the **Client Access Token**
4. Set in `.env`:
   ```env
   GENIUS_API_TOKEN=your_token
   ```

---

## 🛡 Bot Permissions

Add the bot to your group and give it these admin permissions:
- ✅ **Manage Voice Chats** (required)
- ✅ **Invite Users** (required for assistant)
- ✅ Delete Messages (optional, for cleanup)

---

## ❓ Troubleshooting

| Issue | Solution |
|---|---|
| `No active group call` | Start a voice chat in your group first |
| `Format not available` | The bot automatically retries with fallback quality |
| `No playable stream` | The video may be geo-blocked; try a different source |
| `AuthKeyUnregistered` | Your string session is expired; generate a new one |
| `Assistant won't join` | Make sure the assistant account is not banned |
| High CPU usage | Reduce `QUEUE_LIMIT` or use fewer simultaneous streams |

---

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.

---

<div align="center">

Made with ❤️ and 🎵

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:48CAE4,100:6C63FF&height=100&section=footer" width="100%"/>

</div>

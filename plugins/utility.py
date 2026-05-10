"""
plugins/utility.py — /lyrics /ping /stats /speedtest /restart commands
"""

import asyncio
import os
import platform
import sys
import time

import psutil
from pyrogram import Client, filters
from pyrogram.types import Message

from config.config import Config
from core.bot import tunebot
from core.call_manager import call_manager
from helpers.guards import cooldown, sudo_only
from helpers.logger import LOGGER
from helpers.ui import seconds_to_time

log = LOGGER(__name__)


# ── /ping ─────────────────────────────────────────────────────────────────────

@tunebot.bot.on_message(filters.command(["ping"]) & (filters.group | filters.private))
@cooldown(5)
async def ping_command(client: Client, message: Message):
    start = time.monotonic()
    msg = await message.reply("🏓 **Pong!**", quote=True)
    elapsed_ms = (time.monotonic() - start) * 1000
    await msg.edit(f"🏓 **Pong!**\n⚡ Response time: `{elapsed_ms:.2f}ms`")


# ── /stats ────────────────────────────────────────────────────────────────────

@tunebot.bot.on_message(filters.command(["stats"]) & (filters.group | filters.private))
@cooldown(10)
async def stats_command(client: Client, message: Message):
    msg = await message.reply("📊 **Gathering stats…**", quote=True)

    try:
        # System info
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        uptime_secs = int(time.time() - psutil.boot_time())

        # Bot info
        total_plays = await tunebot.db.get_global_play_count()
        served_chats = await tunebot.db.get_served_chats_count()
        served_users = await tunebot.db.get_served_users_count()
        active_calls = len([s for s in call_manager._states.values() if s.is_playing])

        me = await client.get_me()

        text = (
            f"📊 **{Config.BOT_NAME} Statistics**\n\n"
            f"🤖 **Bot:** @{me.username}\n"
            f"🐍 **Python:** `{sys.version.split()[0]}`\n"
            f"🖥 **OS:** `{platform.system()} {platform.release()}`\n"
            f"⏱ **Uptime:** `{seconds_to_time(uptime_secs)}`\n\n"
            f"💻 **System Resources**\n"
            f"├ CPU: `{cpu}%`\n"
            f"├ RAM: `{ram.used // 1024 // 1024}MB / {ram.total // 1024 // 1024}MB` (`{ram.percent}%`)\n"
            f"└ Disk: `{disk.used // 1024 // 1024 // 1024}GB / {disk.total // 1024 // 1024 // 1024}GB`\n\n"
            f"🎵 **Music Stats**\n"
            f"├ Total Plays: `{total_plays:,}`\n"
            f"├ Active Calls: `{active_calls}`\n"
            f"├ Served Chats: `{served_chats:,}`\n"
            f"└ Served Users: `{served_users:,}`\n\n"
            f"🎸 **Assistants:** `{len(tunebot.assistants)}`"
        )
        await msg.edit(text)
    except Exception as e:
        await msg.edit(f"❌ Error gathering stats: `{e}`")


# ── /speedtest ────────────────────────────────────────────────────────────────

@tunebot.bot.on_message(filters.command(["speedtest", "speed"]) & (filters.group | filters.private))
@cooldown(30)
@sudo_only
async def speedtest_command(client: Client, message: Message):
    msg = await message.reply("🌐 **Running speed test…** (this may take 30s)", quote=True)
    try:
        import speedtest as st
        s = await asyncio.to_thread(_run_speedtest)
        await msg.edit(
            f"🌐 **Speed Test Results**\n\n"
            f"⬆️ **Upload:** `{s['upload']:.2f} Mbps`\n"
            f"⬇️ **Download:** `{s['download']:.2f} Mbps`\n"
            f"📍 **Server:** `{s['server']}`\n"
            f"📶 **Ping:** `{s['ping']:.2f} ms`"
        )
    except ImportError:
        await msg.edit("❌ `speedtest-cli` is not installed.\nRun: `pip install speedtest-cli`")
    except Exception as e:
        await msg.edit(f"❌ Speed test failed: `{e}`")


def _run_speedtest() -> dict:
    import speedtest as st
    s = st.Speedtest()
    s.get_best_server()
    s.download()
    s.upload()
    r = s.results.dict()
    return {
        "download": r["download"] / 1_000_000,
        "upload": r["upload"] / 1_000_000,
        "ping": r["ping"],
        "server": r["server"]["name"] + ", " + r["server"]["country"],
    }


# ── /lyrics ───────────────────────────────────────────────────────────────────

@tunebot.bot.on_message(filters.command(["lyrics", "ly"]) & (filters.group | filters.private))
@cooldown(10)
async def lyrics_command(client: Client, message: Message):
    args = message.text.split(None, 1)
    chat_id = message.chat.id

    # If no query, use currently playing track
    if len(args) < 2:
        state = call_manager.get_state(chat_id)
        if not state.current:
            await message.reply(
                "ℹ️ **Usage:** `/lyrics <song name>`\n"
                "Or use while a song is playing to auto-detect.",
                quote=True,
            )
            return
        query = state.current.title
    else:
        query = args[1].strip()

    if not Config.GENIUS_API_TOKEN:
        await message.reply(
            "⚠️ Lyrics feature is disabled.\n"
            "Set `GENIUS_API_TOKEN` in your environment to enable it.",
            quote=True,
        )
        return

    msg = await message.reply(f"🔍 Searching lyrics for **{query}**…", quote=True)

    try:
        import lyricsgenius
        genius = lyricsgenius.Genius(Config.GENIUS_API_TOKEN, verbose=False, remove_section_headers=True)
        song = await asyncio.to_thread(genius.search_song, query)

        if not song:
            await msg.edit(f"❌ No lyrics found for **{query}**.")
            return

        lyrics = song.lyrics
        # Genius adds an annoying prefix like "Embed" at the end
        if "Embed" in lyrics:
            lyrics = lyrics[:lyrics.rfind("Embed")].strip()

        # Telegram message limit is 4096 chars
        header = f"🎵 **{song.title}** — {song.artist}\n\n"
        max_len = 4096 - len(header)

        if len(lyrics) <= max_len:
            await msg.edit(header + lyrics)
        else:
            await msg.edit(header + lyrics[:max_len] + "\n\n_…lyrics truncated_")

    except ImportError:
        await msg.edit("❌ `lyricsgenius` is not installed.\nRun: `pip install lyricsgenius`")
    except Exception as e:
        log.error(f"Lyrics error: {e}")
        await msg.edit(f"❌ Could not fetch lyrics: `{e}`")


# ── /restart ──────────────────────────────────────────────────────────────────

@tunebot.bot.on_message(filters.command(["restart"]) & (filters.group | filters.private))
@sudo_only
async def restart_command(client: Client, message: Message):
    await message.reply("🔄 **Restarting bot…**", quote=True)
    if Config.LOGGER_ID:
        try:
            await client.send_message(Config.LOGGER_ID, "♻️ Bot restarting by owner request.")
        except Exception:
            pass
    os.execv(sys.executable, [sys.executable, "-m", "__main__"])

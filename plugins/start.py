"""
plugins/start.py — /start command, help message, and 24/7 mode toggle
"""

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config.config import Config
from core.bot import tunebot
from core.call_manager import call_manager
from helpers.guards import admin_only, cooldown
from helpers.logger import LOGGER

log = LOGGER(__name__)

# ── /start ────────────────────────────────────────────────────────────────────

START_TEXT = """
🎵 **Hello! I'm {bot_name}**
A powerful Telegram Music Bot built for group voice chats.

**Quick Start:**
1. Add me to your group
2. Give me admin rights (+ invite users)
3. Use `/play <song name>` to start the music!

Use `/help` to see all available commands.
"""

HELP_TEXT = """
🎵 **{bot_name} Command Guide**

**🎶 Playback**
`/play` `<query/URL>` — Play a song or YouTube/Spotify URL
`/vplay` — Same as /play
`/skip` `[count]` — Skip to next track (or skip N tracks)
`/pause` — Pause playback
`/resume` — Resume playback
`/stop` — Stop and clear queue

**🎛 Controls**
`/seek` `<seconds>` — Jump to position
`/volume` `<1-200>` — Set volume
`/loop` `[off|track|queue]` — Set loop mode
`/shuffle` — Shuffle the queue

**📋 Queue & Info**
`/queue` — View current queue
`/lyrics` `[song]` — Get song lyrics
`/ping` — Check bot response time

**📊 Stats & Admin**
`/stats` — Bot and system statistics
`/speedtest` — Network speed test _(owner only)_
`/restart` — Restart the bot _(owner only)_
`/247` — Toggle 24/7 mode _(admin only)_
"""


@tunebot.bot.on_message(filters.command(["start"]) & filters.private)
async def start_command(client: Client, message: Message):
    name = Config.BOT_NAME
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true"),
        ],
        [
            InlineKeyboardButton("📖 Help", callback_data="help_main"),
            InlineKeyboardButton("💬 Support", url=f"https://t.me/{Config.SUPPORT_CHAT}" if Config.SUPPORT_CHAT else "https://t.me/"),
        ],
    ])
    await message.reply(
        START_TEXT.format(bot_name=name),
        reply_markup=keyboard,
        quote=True,
    )


@tunebot.bot.on_message(filters.command(["help", "h"]) & (filters.group | filters.private))
@cooldown(5)
async def help_command(client: Client, message: Message):
    await message.reply(
        HELP_TEXT.format(bot_name=Config.BOT_NAME),
        quote=True,
    )


@tunebot.bot.on_callback_query(filters.regex("^help_main$"))
async def help_callback(client, callback):
    await callback.message.edit(
        HELP_TEXT.format(bot_name=Config.BOT_NAME),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("← Back", callback_data="start_main")
        ]]),
    )
    await callback.answer()


@tunebot.bot.on_callback_query(filters.regex("^start_main$"))
async def start_back_callback(client, callback):
    name = Config.BOT_NAME
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")],
        [
            InlineKeyboardButton("📖 Help", callback_data="help_main"),
            InlineKeyboardButton("💬 Support", url=f"https://t.me/{Config.SUPPORT_CHAT}" if Config.SUPPORT_CHAT else "https://t.me/"),
        ],
    ])
    await callback.message.edit(START_TEXT.format(bot_name=name), reply_markup=keyboard)
    await callback.answer()


# ── /247 (24/7 mode) ──────────────────────────────────────────────────────────

@tunebot.bot.on_message(filters.command(["247"]) & filters.group)
@cooldown()
@admin_only
async def always_on_command(client: Client, message: Message):
    chat_id = message.chat.id
    state = call_manager.get_state(chat_id)
    state.always_on = not state.always_on

    # Persist to DB
    try:
        await tunebot.db.set_always_on(chat_id, state.always_on)
    except Exception as e:
        log.warning(f"Could not save 24/7 setting: {e}")

    if state.always_on:
        await message.reply(
            "🔁 **24/7 Mode Enabled!**\n"
            "The bot will stay in the voice chat even when the queue is empty.",
            quote=True,
        )
    else:
        await message.reply(
            "⭕ **24/7 Mode Disabled.**\n"
            "The bot will leave the voice chat when the queue ends.",
            quote=True,
        )

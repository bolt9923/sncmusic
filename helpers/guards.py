"""
helpers/guards.py — Decorators for cooldown, force-subscribe, ban check, admin-only
"""

import asyncio
import functools
import time
from typing import Callable

from pyrogram import Client
from pyrogram.errors import UserNotParticipant, ChannelInvalid
from pyrogram.types import Message

from config.config import Config
from helpers.logger import LOGGER

log = LOGGER(__name__)

# ── Cooldown store: {user_id: last_used_timestamp} ───────────────────────────
_cooldown_store: dict = {}


def cooldown(seconds: int = None):
    """Rate-limit a command handler per user."""
    limit = seconds or Config.COMMAND_COOLDOWN

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(client: Client, message: Message, *args, **kwargs):
            uid = message.from_user.id if message.from_user else 0
            now = time.monotonic()
            last = _cooldown_store.get(uid, 0)
            if now - last < limit:
                remaining = limit - (now - last)
                await message.reply(
                    f"⏳ Please wait **{remaining:.1f}s** before using this command again.",
                    quote=True,
                )
                return
            _cooldown_store[uid] = now
            return await func(client, message, *args, **kwargs)
        return wrapper
    return decorator


def admin_only(func: Callable):
    """Restrict command to group admins or sudo users."""
    @functools.wraps(func)
    async def wrapper(client: Client, message: Message, *args, **kwargs):
        uid = message.from_user.id if message.from_user else 0

        if Config.is_sudo(uid):
            return await func(client, message, *args, **kwargs)

        try:
            member = await client.get_chat_member(message.chat.id, uid)
            if member.status.value not in ("administrator", "owner", "creator"):
                await message.reply("🚫 This command is for **admins only**.", quote=True)
                return
        except Exception:
            await message.reply("🚫 Could not verify your admin status.", quote=True)
            return

        return await func(client, message, *args, **kwargs)
    return wrapper


def sudo_only(func: Callable):
    """Restrict command to sudo users (bot owner / SUDO_USERS list)."""
    @functools.wraps(func)
    async def wrapper(client: Client, message: Message, *args, **kwargs):
        uid = message.from_user.id if message.from_user else 0
        if not Config.is_sudo(uid):
            await message.reply("🚫 This command is for the **bot owner** only.", quote=True)
            return
        return await func(client, message, *args, **kwargs)
    return wrapper


async def check_force_sub(client: Client, user_id: int) -> bool:
    """
    Return True if the user is subscribed to the force-subscribe channel.
    Returns True (passes check) if FORCE_SUB_CHANNEL is not configured.
    """
    if not Config.FORCE_SUB_CHANNEL:
        return True
    try:
        await client.get_chat_member(Config.FORCE_SUB_CHANNEL, user_id)
        return True
    except UserNotParticipant:
        return False
    except (ChannelInvalid, Exception) as e:
        log.warning(f"Force-sub check failed: {e}")
        return True  # Don't block users on misconfiguration


async def send_force_sub_message(message: Message, channel: str):
    """Send the force-subscribe prompt."""
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    channel_str = f"https://t.me/{channel.lstrip('@')}" if not channel.startswith("-") else channel
    await message.reply(
        "🔒 **Join Required**\n\n"
        "You must join our channel before using this bot.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📢 Join Channel", url=channel_str),
        ]]),
        quote=True,
    )

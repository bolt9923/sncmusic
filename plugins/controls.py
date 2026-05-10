"""
plugins/controls.py — Playback control commands:
/skip /pause /resume /stop /seek /volume /loop /shuffle
Also handles inline button callbacks for the now-playing keyboard.
"""

import asyncio

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from config.config import Config
from core.bot import tunebot
from core.call_manager import LoopMode, call_manager
from helpers.guards import admin_only, cooldown
from helpers.logger import LOGGER
from helpers.ui import (
    error_text,
    now_playing_keyboard,
    now_playing_text,
    queue_keyboard,
    queue_text,
    seconds_to_time,
)

log = LOGGER(__name__)


# ── Helper: get assistant_id for chat ─────────────────────────────────────────

async def _aid(chat_id: int) -> int:
    assistant = tunebot.get_assistant(chat_id)
    return (await assistant.get_me()).id


# ── /skip ─────────────────────────────────────────────────────────────────────

@tunebot.bot.on_message(filters.command(["skip", "s"]) & filters.group)
@cooldown()
@admin_only
async def skip_command(client: Client, message: Message):
    chat_id = message.chat.id
    state = call_manager.get_state(chat_id)
    if not state.is_playing and not state.is_paused:
        await message.reply("❌ Nothing is playing right now.", quote=True)
        return

    args = message.text.split()
    count = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1
    aid = await _aid(chat_id)

    skipped = 0
    for _ in range(max(1, count)):
        next_track = await call_manager.skip(chat_id, aid)
        skipped += 1
        if not next_track:
            break

    if next_track := state.current:
        np_text = now_playing_text(next_track, state)
        np_kbd = now_playing_keyboard(chat_id, state)
        await message.reply(f"⏭ Skipped **{skipped}** track(s).\n\n" + np_text, reply_markup=np_kbd, quote=True)
    else:
        await message.reply(f"⏭ Skipped **{skipped}** track(s). Queue is now empty.", quote=True)


# ── /pause ────────────────────────────────────────────────────────────────────

@tunebot.bot.on_message(filters.command(["pause"]) & filters.group)
@cooldown()
@admin_only
async def pause_command(client: Client, message: Message):
    chat_id = message.chat.id
    state = call_manager.get_state(chat_id)
    if not state.is_playing:
        await message.reply("❌ Nothing is playing or already paused.", quote=True)
        return
    aid = await _aid(chat_id)
    await call_manager.pause(chat_id, aid)
    await message.reply("⏸ **Paused.** Use /resume to continue.", quote=True)


# ── /resume ───────────────────────────────────────────────────────────────────

@tunebot.bot.on_message(filters.command(["resume", "r"]) & filters.group)
@cooldown()
@admin_only
async def resume_command(client: Client, message: Message):
    chat_id = message.chat.id
    state = call_manager.get_state(chat_id)
    if not state.is_paused:
        await message.reply("❌ Playback is not paused.", quote=True)
        return
    aid = await _aid(chat_id)
    await call_manager.resume(chat_id, aid)
    await message.reply("▶️ **Resumed.**", quote=True)


# ── /stop ─────────────────────────────────────────────────────────────────────

@tunebot.bot.on_message(filters.command(["stop", "end"]) & filters.group)
@cooldown()
@admin_only
async def stop_command(client: Client, message: Message):
    chat_id = message.chat.id
    state = call_manager.get_state(chat_id)
    if not state.is_playing and not state.is_paused and not state.queue:
        await message.reply("❌ Nothing to stop.", quote=True)
        return
    aid = await _aid(chat_id)
    await call_manager.stop(chat_id, aid)
    call_manager.cleanup_state(chat_id)
    await message.reply("⏹ **Stopped playback and cleared queue.**", quote=True)


# ── /seek ─────────────────────────────────────────────────────────────────────

@tunebot.bot.on_message(filters.command(["seek"]) & filters.group)
@cooldown()
@admin_only
async def seek_command(client: Client, message: Message):
    chat_id = message.chat.id
    args = message.text.split()
    if len(args) < 2:
        await message.reply("ℹ️ **Usage:** `/seek <seconds>`\nExample: `/seek 90`", quote=True)
        return

    try:
        seconds = int(args[1])
        if seconds < 0:
            raise ValueError
    except ValueError:
        await message.reply("❌ Please provide a valid number of seconds.", quote=True)
        return

    state = call_manager.get_state(chat_id)
    if not state.current:
        await message.reply("❌ Nothing is playing right now.", quote=True)
        return
    if seconds > state.current.duration:
        await message.reply(
            f"❌ Cannot seek beyond track duration (`{seconds_to_time(state.current.duration)}`).",
            quote=True,
        )
        return

    aid = await _aid(chat_id)
    try:
        await call_manager.seek(chat_id, seconds, aid)
        await message.reply(
            f"⏩ **Seeked to** `{seconds_to_time(seconds)}`", quote=True
        )
    except Exception as e:
        await message.reply(error_text(f"Seek failed: {e}"), quote=True)


# ── /volume ───────────────────────────────────────────────────────────────────

@tunebot.bot.on_message(filters.command(["volume", "vol", "v"]) & filters.group)
@cooldown()
@admin_only
async def volume_command(client: Client, message: Message):
    chat_id = message.chat.id
    args = message.text.split()
    if len(args) < 2:
        state = call_manager.get_state(chat_id)
        await message.reply(
            f"🔊 **Current volume:** `{state.volume}%`\n\n"
            f"ℹ️ Usage: `/volume <1-200>`",
            quote=True,
        )
        return

    try:
        vol = int(args[1])
    except ValueError:
        await message.reply("❌ Please provide a valid volume (1–200).", quote=True)
        return

    aid = await _aid(chat_id)
    try:
        await call_manager.set_volume(chat_id, vol, aid)
        state = call_manager.get_state(chat_id)
        emoji = "🔊" if state.volume > 50 else "🔉" if state.volume > 0 else "🔇"
        await message.reply(f"{emoji} **Volume set to** `{state.volume}%`", quote=True)
    except Exception as e:
        await message.reply(error_text(f"Could not set volume: {e}"), quote=True)


# ── /loop ─────────────────────────────────────────────────────────────────────

@tunebot.bot.on_message(filters.command(["loop", "repeat"]) & filters.group)
@cooldown()
@admin_only
async def loop_command(client: Client, message: Message):
    chat_id = message.chat.id
    args = message.text.split()

    if len(args) > 1:
        mode_str = args[1].lower()
        mode_map = {"off": LoopMode.NONE, "track": LoopMode.TRACK, "queue": LoopMode.QUEUE}
        mode = mode_map.get(mode_str)
        if mode is None:
            await message.reply(
                "ℹ️ **Usage:** `/loop [off|track|queue]`\n\n"
                "• `off` — disable loop\n"
                "• `track` — repeat current track\n"
                "• `queue` — repeat entire queue",
                quote=True,
            )
            return
        new_mode = call_manager.set_loop(chat_id, mode)
    else:
        new_mode = call_manager.cycle_loop(chat_id)

    mode_text = {
        LoopMode.NONE: "🔁 Loop **disabled**.",
        LoopMode.TRACK: "🔂 **Track loop** enabled — current track will repeat.",
        LoopMode.QUEUE: "🔁 **Queue loop** enabled — queue will repeat.",
    }
    await message.reply(mode_text[new_mode], quote=True)


# ── /shuffle ──────────────────────────────────────────────────────────────────

@tunebot.bot.on_message(filters.command(["shuffle"]) & filters.group)
@cooldown()
@admin_only
async def shuffle_command(client: Client, message: Message):
    chat_id = message.chat.id
    state = call_manager.get_state(chat_id)
    if not state.queue:
        await message.reply("❌ Queue is empty.", quote=True)
        return
    call_manager.shuffle_queue(chat_id)
    await message.reply(
        f"🔀 **Queue shuffled!** `{len(state.queue)}` tracks reordered.", quote=True
    )


# ── /queue ────────────────────────────────────────────────────────────────────

@tunebot.bot.on_message(filters.command(["queue", "q"]) & filters.group)
@cooldown(2)
async def queue_command(client: Client, message: Message):
    chat_id = message.chat.id
    state = call_manager.get_state(chat_id)
    import math
    total_pages = max(1, math.ceil(len(state.queue) / 10))
    text = queue_text(state, page=1)
    kbd = queue_keyboard(chat_id, 1, total_pages)
    await message.reply(text, reply_markup=kbd, quote=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Inline button callbacks
# ═══════════════════════════════════════════════════════════════════════════════

@tunebot.bot.on_callback_query(filters.regex(r"^(pause|resume|skip|stop|loop|shuffle|volup|voldn|queue|close|qpage)_"))
async def control_callback(client: Client, callback: CallbackQuery):
    data = callback.data
    uid = callback.from_user.id

    # Parse chat_id from callback data (format: action_chatid or action_chatid_page)
    parts = data.split("_")
    action = parts[0]

    try:
        chat_id = int(parts[1])
    except (IndexError, ValueError):
        await callback.answer("Invalid callback data.", show_alert=True)
        return

    # Check if caller is admin or sudo
    if not Config.is_sudo(uid):
        try:
            member = await client.get_chat_member(chat_id, uid)
            if member.status.value not in ("administrator", "owner", "creator"):
                await callback.answer("🚫 Only admins can use these controls.", show_alert=True)
                return
        except Exception:
            await callback.answer("🚫 Could not verify permissions.", show_alert=True)
            return

    aid = await _aid(chat_id)
    state = call_manager.get_state(chat_id)

    try:
        if action == "pause":
            if not state.is_playing:
                await callback.answer("Nothing is playing.", show_alert=True)
                return
            await call_manager.pause(chat_id, aid)
            await callback.answer("⏸ Paused.")

        elif action == "resume":
            if not state.is_paused:
                await callback.answer("Not paused.", show_alert=True)
                return
            await call_manager.resume(chat_id, aid)
            await callback.answer("▶️ Resumed.")

        elif action == "skip":
            await call_manager.skip(chat_id, aid)
            await callback.answer("⏭ Skipped.")

        elif action == "stop":
            await call_manager.stop(chat_id, aid)
            call_manager.cleanup_state(chat_id)
            await callback.message.edit("⏹ **Playback stopped and queue cleared.**")
            return

        elif action == "loop":
            new_mode = call_manager.cycle_loop(chat_id)
            labels = {LoopMode.NONE: "Off", LoopMode.TRACK: "Track", LoopMode.QUEUE: "Queue"}
            await callback.answer(f"🔁 Loop: {labels[new_mode]}")

        elif action == "shuffle":
            if state.queue:
                call_manager.shuffle_queue(chat_id)
                await callback.answer("🔀 Queue shuffled!")
            else:
                await callback.answer("Queue is empty.", show_alert=True)
                return

        elif action == "volup":
            new_vol = min(200, state.volume + 10)
            await call_manager.set_volume(chat_id, new_vol, aid)
            await callback.answer(f"🔊 Volume: {new_vol}%")

        elif action == "voldn":
            new_vol = max(1, state.volume - 10)
            await call_manager.set_volume(chat_id, new_vol, aid)
            await callback.answer(f"🔉 Volume: {new_vol}%")

        elif action == "queue":
            import math
            total_pages = max(1, math.ceil(len(state.queue) / 10))
            text = queue_text(state, 1)
            kbd = queue_keyboard(chat_id, 1, total_pages)
            await callback.message.edit(text, reply_markup=kbd)
            await callback.answer()
            return

        elif action == "qpage":
            page = int(parts[2]) if len(parts) > 2 else 1
            import math
            total_pages = max(1, math.ceil(len(state.queue) / 10))
            text = queue_text(state, page)
            kbd = queue_keyboard(chat_id, page, total_pages)
            await callback.message.edit(text, reply_markup=kbd)
            await callback.answer()
            return

        elif action == "close":
            await callback.message.delete()
            await callback.answer()
            return

        # Refresh now-playing message
        if state.current:
            np_text = now_playing_text(state.current, state)
            np_kbd = now_playing_keyboard(chat_id, state)
            try:
                await callback.message.edit(np_text, reply_markup=np_kbd)
            except Exception:
                pass

    except Exception as e:
        log.error(f"Control callback error ({action}): {e}", exc_info=True)
        await callback.answer(f"Error: {e}", show_alert=True)


# ── search_cancel callback ────────────────────────────────────────────────────

@tunebot.bot.on_callback_query(filters.regex("^search_cancel$"))
async def search_cancel_callback(client: Client, callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer("❌ Search cancelled.")


# ── play_yt_ callback — fires when user picks a search result ─────────────────

@tunebot.bot.on_callback_query(filters.regex(r"^play_yt_(.+)_(\d+)$"))
async def play_yt_callback(client: Client, callback: CallbackQuery):
    """Handle inline search result selection from /search command."""
    import re
    m = re.match(r"^play_yt_(.+)_(\d+)$", callback.data)
    if not m:
        await callback.answer("Invalid data.", show_alert=True)
        return

    vid_id = m.group(1)
    url = f"https://www.youtube.com/watch?v={vid_id}"

    await callback.answer("🎵 Adding to queue…")
    await callback.message.delete()

    # Reuse the play pipeline via a synthetic message edit
    from plugins.play import _queue_and_play
    # Build a minimal fake message context using the callback's message
    msg = callback.message
    msg.from_user = callback.from_user
    msg.chat = callback.message.chat
    await _queue_and_play(client, msg, query=url)

"""
plugins/play.py — /play and /vplay command handlers
Supports: YouTube search, YouTube URL, Spotify track/playlist/album,
          YouTube playlists.
"""

import asyncio
import math
import os
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import Message

from config.config import Config
from core.bot import tunebot
from core.call_manager import LoopMode, Track, call_manager
from helpers.downloader import downloader
from helpers.guards import cooldown, check_force_sub, send_force_sub_message
from helpers.logger import LOGGER
from helpers.spotify import is_spotify_url, resolve_spotify, spotify_url_type
from helpers.ui import (
    error_text,
    now_playing_keyboard,
    now_playing_text,
    search_results_keyboard,
    seconds_to_time,
)

log = LOGGER(__name__)

bot = tunebot.bot


# ── Utility ───────────────────────────────────────────────────────────────────

async def _resolve_track_info(query: str) -> Optional[dict]:
    """Resolve query/URL to a single yt-dlp info dict."""
    return await downloader.get_info(query)


async def _queue_and_play(
    client: Client,
    message: Message,
    query: str,
    title_override: str = None,
    duration_override: int = None,
    thumb_override: str = None,
):
    """
    Core play logic:
    1. Resolve metadata
    2. Download audio
    3. Add to queue or play immediately
    4. Send now-playing card
    """
    chat_id = message.chat.id
    user = message.from_user
    requester_name = user.first_name if user else "Unknown"
    requester_id = user.id if user else 0

    # ── Validate duration ─────────────────────────────────────────────────
    status_msg = await message.reply("🔍 **Searching…**", quote=True)

    try:
        info = await _resolve_track_info(query)
        if not info:
            await status_msg.edit(error_text("No results found. Try a different search term."))
            return

        duration = duration_override or (info.get("duration") or 0)
        limit = Config.DURATION_LIMIT_MIN * 60
        if duration > limit:
            await status_msg.edit(
                error_text(
                    f"Track is too long! Max allowed: **{Config.DURATION_LIMIT_MIN} minutes**."
                )
            )
            return

        title = title_override or info.get("title", "Unknown Track")
        thumbnail = thumb_override or info.get("thumbnail") or ""

        # ── Download ──────────────────────────────────────────────────────
        await status_msg.edit("⬇️ **Downloading audio…**")
        url = info.get("webpage_url") or info.get("url") or query
        file_path, dl_info = await downloader.download(url)

        if not file_path:
            await status_msg.edit(
                error_text(
                    "Could not download audio.\n"
                    "The stream may be unavailable or geo-restricted.\n"
                    "Try a different search or URL."
                )
            )
            return

        track = Track(
            title=title,
            url=url,
            duration=duration,
            thumbnail=thumbnail,
            requester_id=requester_id,
            requester_name=requester_name,
            file_path=file_path,
        )

        # ── Queue management ───────────────────────────────────────────────
        state = call_manager.get_state(chat_id)
        assistant = tunebot.get_assistant(chat_id)
        assistant_id = (await assistant.get_me()).id

        if state.is_playing or state.is_paused:
            # Add to queue
            if len(state.queue) >= Config.QUEUE_LIMIT:
                await status_msg.edit(
                    error_text(f"Queue is full! Maximum **{Config.QUEUE_LIMIT}** tracks.")
                )
                return
            pos = call_manager.add_to_queue(chat_id, track)
            await status_msg.edit(
                f"✅ **Added to queue at position #{pos}**\n\n"
                f"🎵 **{title}**\n"
                f"⏱ Duration: `{seconds_to_time(duration)}`\n"
                f"👤 Requested by: {requester_name}"
            )
        else:
            # Play immediately
            await status_msg.edit("🎵 **Joining voice chat…**")
            await call_manager.play(chat_id, track, assistant_id)

            np_text = now_playing_text(track, state)
            np_kbd = now_playing_keyboard(chat_id, state)

            if thumbnail:
                try:
                    sent = await client.send_photo(
                        chat_id,
                        photo=thumbnail,
                        caption=np_text,
                        reply_markup=np_kbd,
                    )
                    state.message_id = sent.id
                    await status_msg.delete()
                    return
                except Exception:
                    pass  # Fall through to text message

            sent = await status_msg.edit(np_text, reply_markup=np_kbd)
            state.message_id = sent.id

            # Log to database
            try:
                await tunebot.db.log_play(chat_id, requester_id, title)
                await tunebot.db.add_served_chat(chat_id)
                await tunebot.db.add_served_user(requester_id)
            except Exception as e:
                log.warning(f"DB log error: {e}")

    except Exception as e:
        log.error(f"_queue_and_play error: {e}", exc_info=True)
        try:
            await status_msg.edit(error_text(f"Unexpected error: {e}"))
        except Exception:
            pass


# ── /play ─────────────────────────────────────────────────────────────────────

@tunebot.bot.on_message(filters.command(["play", "p"]) & filters.group)
@cooldown()
async def play_command(client: Client, message: Message):
    # Force-subscribe check
    uid = message.from_user.id if message.from_user else 0
    if not await check_force_sub(client, uid):
        await send_force_sub_message(message, Config.FORCE_SUB_CHANNEL)
        return

    args = message.text.split(None, 1)

    # No argument — show usage or search prompt
    if len(args) < 2:
        # If replied to audio/video, use that file
        if message.reply_to_message:
            rep = message.reply_to_message
            if rep.audio or rep.voice or rep.video_note or rep.video:
                media = rep.audio or rep.voice or rep.video_note or rep.video
                await message.reply("📥 **Downloading attached media…**", quote=True)
                file = await rep.download(Config.DOWNLOAD_DIR)
                title = getattr(media, "title", None) or getattr(media, "file_name", "Unknown")
                duration = getattr(media, "duration", 0) or 0
                track = Track(
                    title=title,
                    url=file,
                    duration=duration,
                    thumbnail="",
                    requester_id=uid,
                    requester_name=message.from_user.first_name if message.from_user else "User",
                    file_path=file,
                    source="file",
                )
                state = call_manager.get_state(message.chat.id)
                assistant = tunebot.get_assistant(message.chat.id)
                assistant_id = (await assistant.get_me()).id
                if state.is_playing or state.is_paused:
                    call_manager.add_to_queue(message.chat.id, track)
                    await message.reply(f"✅ **Added to queue:** {title}", quote=True)
                else:
                    await call_manager.play(message.chat.id, track, assistant_id)
                    await message.reply(
                        now_playing_text(track, state),
                        reply_markup=now_playing_keyboard(message.chat.id, state),
                        quote=True,
                    )
                return
        await message.reply(
            "🎵 **Usage:** `/play <song name or YouTube URL>`\n\n"
            "**Examples:**\n"
            "• `/play Blinding Lights`\n"
            "• `/play https://youtu.be/xxxxx`\n"
            "• `/play https://open.spotify.com/track/xxxxx`",
            quote=True,
        )
        return

    query = args[1].strip()

    # ── Spotify URL ───────────────────────────────────────────────────────
    if is_spotify_url(query):
        url_type = spotify_url_type(query)
        if url_type == "track":
            tracks = await resolve_spotify(query)
            if not tracks:
                await message.reply(
                    error_text("Could not resolve Spotify track. Check the URL or your Spotify credentials."),
                    quote=True,
                )
                return
            t = tracks[0]
            await _queue_and_play(
                client, message,
                query=t["search_query"],
                title_override=f"{t['title']} — {t['artists']}",
                duration_override=t["duration"],
                thumb_override=t.get("thumbnail"),
            )
        elif url_type in ("playlist", "album"):
            tracks = await resolve_spotify(query)
            if not tracks:
                await message.reply(error_text("Could not load Spotify playlist."), quote=True)
                return
            status = await message.reply(
                f"🎵 **Loading {len(tracks)} tracks from Spotify {url_type}…**", quote=True
            )
            added = 0
            for t in tracks[:Config.QUEUE_LIMIT]:
                info = await downloader.get_info(t["search_query"])
                if not info:
                    continue
                file_path, _ = await downloader.download(
                    info.get("webpage_url") or info.get("url") or t["search_query"]
                )
                if not file_path:
                    continue
                track = Track(
                    title=f"{t['title']} — {t['artists']}",
                    url=info.get("webpage_url") or "",
                    duration=t["duration"],
                    thumbnail=t.get("thumbnail") or "",
                    requester_id=uid,
                    requester_name=message.from_user.first_name if message.from_user else "User",
                    file_path=file_path,
                    source="spotify",
                )
                state = call_manager.get_state(message.chat.id)
                assistant = tunebot.get_assistant(message.chat.id)
                assistant_id = (await assistant.get_me()).id
                if state.is_playing or state.is_paused or added > 0:
                    call_manager.add_to_queue(message.chat.id, track)
                else:
                    await call_manager.play(message.chat.id, track, assistant_id)
                added += 1
            await status.edit(f"✅ **Added {added} tracks to queue from Spotify {url_type}.**")
        return

    # ── YouTube playlist ──────────────────────────────────────────────────
    if "list=" in query or "/playlist" in query:
        status = await message.reply("📋 **Loading YouTube playlist…**", quote=True)
        entries = await downloader.get_playlist_info(query)
        if not entries:
            await status.edit(error_text("Could not load playlist. Check the URL."))
            return
        limited = entries[:Config.QUEUE_LIMIT]
        await status.edit(f"⬇️ **Loading {len(limited)} tracks…**")
        added = 0
        for entry in limited:
            url = entry.get("url") or entry.get("webpage_url") or f"https://www.youtube.com/watch?v={entry.get('id','')}"
            file_path, info = await downloader.download(url)
            if not file_path:
                continue
            title = entry.get("title") or (info.get("title") if info else "Unknown")
            duration = entry.get("duration") or (info.get("duration") if info else 0) or 0
            track = Track(
                title=title,
                url=url,
                duration=duration,
                thumbnail=entry.get("thumbnail") or "",
                requester_id=uid,
                requester_name=message.from_user.first_name if message.from_user else "User",
                file_path=file_path,
            )
            state = call_manager.get_state(message.chat.id)
            assistant = tunebot.get_assistant(message.chat.id)
            assistant_id = (await assistant.get_me()).id
            if state.is_playing or state.is_paused or added > 0:
                call_manager.add_to_queue(message.chat.id, track)
            else:
                await call_manager.play(message.chat.id, track, assistant_id)
            added += 1
        await status.edit(f"✅ **Queued {added} tracks from playlist.**")
        return

    # ── Standard search or direct URL ─────────────────────────────────────
    await _queue_and_play(client, message, query)


# ── /vplay (alias) ────────────────────────────────────────────────────────────

@tunebot.bot.on_message(filters.command(["vplay", "vp"]) & filters.group)
@cooldown()
async def vplay_command(client: Client, message: Message):
    """Same as /play but forces video quality download (audio only output)."""
    # Reuse play logic; yt-dlp still extracts audio
    await play_command(client, message)

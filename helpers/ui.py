"""
helpers/ui.py — Message formatters and inline keyboard builders
"""

import math
from typing import Optional, List

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.call_manager import GroupCallState, LoopMode, Track


# ── Time helpers ──────────────────────────────────────────────────────────────

def seconds_to_time(seconds: int) -> str:
    """Convert seconds → HH:MM:SS or MM:SS."""
    if seconds < 0:
        return "00:00"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def progress_bar(current: int, total: int, length: int = 12) -> str:
    """Return a text progress bar like ━━━━●──────."""
    if total <= 0:
        return "─" * length
    filled = int(length * current / total)
    bar = "━" * filled + "●" + "─" * (length - filled)
    return bar[:length + 1]


# ── Now-playing card ──────────────────────────────────────────────────────────

def now_playing_text(track: Track, state: GroupCallState, elapsed: int = 0) -> str:
    loop_icon = {
        LoopMode.NONE: "🔁",
        LoopMode.TRACK: "🔂",
        LoopMode.QUEUE: "🔁",
    }.get(state.loop_mode, "🔁")

    loop_label = {
        LoopMode.NONE: "Off",
        LoopMode.TRACK: "Track",
        LoopMode.QUEUE: "Queue",
    }.get(state.loop_mode, "Off")

    bar = progress_bar(elapsed, track.duration)
    elapsed_fmt = seconds_to_time(elapsed)
    total_fmt = seconds_to_time(track.duration)

    queue_count = len(state.queue)
    status = "▶️ Playing" if state.is_playing else "⏸ Paused"

    return (
        f"🎵 **Now Playing**\n\n"
        f"**{track.title}**\n\n"
        f"`{elapsed_fmt}` {bar} `{total_fmt}`\n\n"
        f"{status}  •  🔊 `{state.volume}%`  •  {loop_icon} Loop: `{loop_label}`\n"
        f"👤 Requested by: {track.requester_name}\n"
        f"📋 Queue: `{queue_count}` track(s) remaining"
    )


def now_playing_keyboard(chat_id: int, state: GroupCallState) -> InlineKeyboardMarkup:
    """Controls inline keyboard for the now-playing message."""
    pause_resume_btn = (
        InlineKeyboardButton("▶️ Resume", callback_data=f"resume_{chat_id}")
        if state.is_paused
        else InlineKeyboardButton("⏸ Pause", callback_data=f"pause_{chat_id}")
    )

    loop_icon = {
        LoopMode.NONE: "🔁 Loop Off",
        LoopMode.TRACK: "🔂 Loop Track",
        LoopMode.QUEUE: "🔁 Loop Queue",
    }.get(state.loop_mode, "🔁 Loop")

    return InlineKeyboardMarkup([
        [
            pause_resume_btn,
            InlineKeyboardButton("⏭ Skip", callback_data=f"skip_{chat_id}"),
            InlineKeyboardButton("⏹ Stop", callback_data=f"stop_{chat_id}"),
        ],
        [
            InlineKeyboardButton(loop_icon, callback_data=f"loop_{chat_id}"),
            InlineKeyboardButton("🔀 Shuffle", callback_data=f"shuffle_{chat_id}"),
            InlineKeyboardButton("🔊 Vol+", callback_data=f"volup_{chat_id}"),
            InlineKeyboardButton("🔉 Vol-", callback_data=f"voldn_{chat_id}"),
        ],
        [
            InlineKeyboardButton("📋 Queue", callback_data=f"queue_{chat_id}"),
            InlineKeyboardButton("❌ Close", callback_data=f"close_{chat_id}"),
        ],
    ])


# ── Queue list ────────────────────────────────────────────────────────────────

def queue_text(state: GroupCallState, page: int = 1, per_page: int = 10) -> str:
    if not state.current and not state.queue:
        return "📭 **Queue is empty.**"

    lines = ["📋 **Music Queue**\n"]

    if state.current:
        lines.append(f"▶️ **Now Playing:**\n   └ {state.current.title}\n")

    if not state.queue:
        lines.append("_No tracks in queue._")
        return "\n".join(lines)

    total_pages = math.ceil(len(state.queue) / per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page

    lines.append(f"**Up Next** (page {page}/{total_pages}):\n")
    for i, track in enumerate(state.queue[start:end], start=start + 1):
        dur = seconds_to_time(track.duration)
        lines.append(f"`{i}.` **{track.title}** `[{dur}]`")

    total_duration = sum(t.duration for t in state.queue)
    lines.append(f"\n_Total: {len(state.queue)} tracks • {seconds_to_time(total_duration)}_")
    return "\n".join(lines)


def queue_keyboard(chat_id: int, page: int, total_pages: int) -> InlineKeyboardMarkup:
    btns = []
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"qpage_{chat_id}_{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"qpage_{chat_id}_{page+1}"))
    if nav:
        btns.append(nav)
    btns.append([InlineKeyboardButton("❌ Close", callback_data=f"close_{chat_id}")])
    return InlineKeyboardMarkup(btns)


# ── Error card ────────────────────────────────────────────────────────────────

def error_text(message: str) -> str:
    return f"❌ **Error**\n\n{message}"


# ── Search results list ───────────────────────────────────────────────────────

def search_results_keyboard(results: List[dict], requester_id: int) -> InlineKeyboardMarkup:
    """Build inline keyboard for YouTube search results selection."""
    buttons = []
    for i, r in enumerate(results[:5], start=1):
        title = r.get("title", "Unknown")[:45]
        duration = seconds_to_time(r.get("duration") or 0)
        vid_id = r.get("id", "")
        buttons.append([
            InlineKeyboardButton(
                f"{i}. {title} [{duration}]",
                callback_data=f"play_yt_{vid_id}_{requester_id}",
            )
        ])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="search_cancel")])
    return InlineKeyboardMarkup(buttons)

"""
core/call_manager.py — Voice chat controller using PyTgCalls 2.1.0 (stable)

PyTgCalls 2.x API used here:
────────────────────────────
  from pytgcalls import PyTgCalls
  from pytgcalls.types.input_stream import AudioPiped, AudioParameters
  from pytgcalls.types import Update
  from pytgcalls.exceptions import (
      AlreadyJoinedError, NoActiveGroupCall, NotInCallError
  )

  call = PyTgCalls(client)
  await call.start()
  await call.join_group_call(chat_id, AudioPiped(path))
  await call.leave_group_call(chat_id)
  await call.pause_stream(chat_id)
  await call.resume_stream(chat_id)
  await call.change_stream(chat_id, AudioPiped(path))
  await call.change_volume_call(chat_id, volume)

  @call.on_stream_end()
  async def handler(_, update: Update): ...
  update.chat_id is the group chat ID.

Why 2.x not 3.x:
  All PyTgCalls 3.x dev builds depend on `tgcalls` (a compiled C++ wheel)
  which has never been published on PyPI — pip install fails on every
  platform (Heroku, Railway, Render, Docker).  PyTgCalls 2.1.0 is pure-Python
  compatible, installs cleanly, and is the version used by virtually all
  production Telegram music bots.
"""

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict, List, Optional

from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped, AudioParameters

# Graceful exception import — class names are stable in 2.1.0
try:
    from pytgcalls.exceptions import AlreadyJoinedError, NoActiveGroupCall, NotInCallError
except ImportError:
    # Fallback: treat everything as a generic Exception
    AlreadyJoinedError = Exception
    NoActiveGroupCall = Exception
    NotInCallError = Exception

from config.config import Config
from helpers.logger import LOGGER

log = LOGGER(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────

class LoopMode(Enum):
    NONE  = auto()
    TRACK = auto()
    QUEUE = auto()


@dataclass
class Track:
    title: str
    url: str               # Original source URL
    duration: int          # Total duration in seconds
    thumbnail: str         # Thumbnail URL or local path
    requester_id: int
    requester_name: str
    source: str = "youtube"           # youtube | spotify | file
    file_path: Optional[str] = None  # Local path after yt-dlp download


@dataclass
class GroupCallState:
    queue: List[Track] = field(default_factory=list)
    current: Optional[Track] = None
    is_playing: bool = False
    is_paused: bool = False
    loop_mode: LoopMode = LoopMode.NONE
    volume: int = Config.DEFAULT_VOLUME
    always_on: bool = Config.ALWAYS_ON_DEFAULT
    message_id: Optional[int] = None  # Telegram message ID of the now-playing card


# ─────────────────────────────────────────────────────────────────────────────
# Audio stream builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_stream(track: Track, seek_seconds: int = 0) -> AudioPiped:
    """
    Return an AudioPiped stream for the given track.
    Uses the local downloaded file when available; falls back to URL.
    Applies -ss <seek> via additional_ffmpeg_parameters when seeking.
    """
    source = track.file_path or track.url

    params = AudioParameters(
        bitrate=160,    # 160 kbps — good quality, low CPU
    )

    if seek_seconds > 0:
        return AudioPiped(
            source,
            audio_parameters=params,
            additional_ffmpeg_parameters=f"-ss {seek_seconds}",
        )

    return AudioPiped(source, audio_parameters=params)


# ─────────────────────────────────────────────────────────────────────────────
# CallManager
# ─────────────────────────────────────────────────────────────────────────────

class CallManager:
    """
    One PyTgCalls instance per assistant (userbot) client.
    One GroupCallState per active group chat.
    """

    def __init__(self):
        self._pytgcalls: Dict[int, PyTgCalls] = {}   # assistant_id → PyTgCalls
        self._states: Dict[int, GroupCallState] = {}  # chat_id → state
        self._chat_assistant: Dict[int, int] = {}     # chat_id → assistant_id

    # ── Startup ───────────────────────────────────────────────────────────

    async def init_assistants(self, assistants: list):
        """Start a PyTgCalls instance for every assistant Pyrogram client."""
        for client in assistants:
            me = await client.get_me()
            call = PyTgCalls(client)
            await call.start()
            self._pytgcalls[me.id] = call
            log.info(f"🎵 PyTgCalls 2.x ready for @{me.username} ({me.id})")

    # ── Internal ──────────────────────────────────────────────────────────

    def _call(self, assistant_id: int) -> PyTgCalls:
        inst = self._pytgcalls.get(assistant_id)
        if inst is None:
            raise RuntimeError(
                f"No PyTgCalls instance for assistant {assistant_id}. "
                "Call init_assistants() first."
            )
        return inst

    def get_state(self, chat_id: int) -> GroupCallState:
        if chat_id not in self._states:
            self._states[chat_id] = GroupCallState()
        return self._states[chat_id]

    # ── Queue helpers ──────────────────────────────────────────────────────

    def add_to_queue(self, chat_id: int, track: Track) -> int:
        """Append track to queue; return 1-based position."""
        state = self.get_state(chat_id)
        state.queue.append(track)
        return len(state.queue)

    def clear_queue(self, chat_id: int):
        self.get_state(chat_id).queue.clear()

    def shuffle_queue(self, chat_id: int):
        random.shuffle(self.get_state(chat_id).queue)

    # ── Playback ──────────────────────────────────────────────────────────

    async def play(self, chat_id: int, track: Track, assistant_id: int):
        """
        Stream *track* into *chat_id*'s voice chat.

        First call  → join_group_call (joins VC and starts streaming).
        Already in  → change_stream (swap audio source without re-joining).
        """
        state = self.get_state(chat_id)
        call  = self._call(assistant_id)
        stream = _build_stream(track)

        try:
            await call.join_group_call(chat_id, stream)

        except AlreadyJoinedError:
            # Already in the VC — just swap the audio source
            await call.change_stream(chat_id, stream)

        except Exception as e:
            msg = str(e).lower()
            if "already" in msg or "joined" in msg:
                await call.change_stream(chat_id, stream)
            else:
                log.error(f"join_group_call failed in {chat_id}: {e}", exc_info=True)
                raise

        # Update state
        state.current   = track
        state.is_playing = True
        state.is_paused  = False
        self._chat_assistant[chat_id] = assistant_id

        # Apply saved volume (best-effort; may lag a moment after joining)
        try:
            await call.change_volume_call(chat_id, state.volume)
        except Exception:
            pass

    async def skip(self, chat_id: int, assistant_id: int) -> Optional[Track]:
        """
        Advance the queue by one track.
        Respects TRACK loop (repeat same) and QUEUE loop (rotate).
        Returns the new current track, or None if the queue is now empty.
        """
        state = self.get_state(chat_id)

        # Loop track — replay current
        if state.loop_mode == LoopMode.TRACK and state.current:
            await self.play(chat_id, state.current, assistant_id)
            return state.current

        # Loop queue — push current to end
        if state.loop_mode == LoopMode.QUEUE and state.current:
            state.queue.append(state.current)

        if state.queue:
            next_track = state.queue.pop(0)
            await self.play(chat_id, next_track, assistant_id)
            return next_track

        # Nothing left
        await self._finish(chat_id, assistant_id)
        return None

    async def _finish(self, chat_id: int, assistant_id: int):
        """Queue exhausted. Leave VC unless 24/7 mode is on."""
        state = self.get_state(chat_id)
        state.current    = None
        state.is_playing = False
        state.is_paused  = False

        if state.always_on:
            log.info(f"🔁 24/7 mode active — staying in VC for {chat_id}.")
            return

        try:
            await self._call(assistant_id).leave_group_call(chat_id)
            log.info(f"👋 Left VC in {chat_id} (queue empty).")
        except NotInCallError:
            pass
        except Exception as e:
            if "not" not in str(e).lower():
                log.warning(f"leave_group_call error in {chat_id}: {e}")

    async def pause(self, chat_id: int, assistant_id: int):
        await self._call(assistant_id).pause_stream(chat_id)
        s = self.get_state(chat_id)
        s.is_playing = False
        s.is_paused  = True

    async def resume(self, chat_id: int, assistant_id: int):
        await self._call(assistant_id).resume_stream(chat_id)
        s = self.get_state(chat_id)
        s.is_playing = True
        s.is_paused  = False

    async def stop(self, chat_id: int, assistant_id: int):
        """Stop playback, clear queue, and leave VC."""
        state = self.get_state(chat_id)
        state.queue.clear()
        state.current    = None
        state.is_playing = False
        state.is_paused  = False
        try:
            await self._call(assistant_id).leave_group_call(chat_id)
        except Exception:
            pass

    async def seek(self, chat_id: int, seconds: int, assistant_id: int):
        """
        Seek to *seconds* by rebuilding the FFmpeg stream with -ss.
        Requires the track to have a local file (yt-dlp download).
        """
        state = self.get_state(chat_id)
        if not state.current:
            raise ValueError("Nothing is playing.")
        if not (0 <= seconds <= state.current.duration):
            raise ValueError(
                f"Seek position {seconds}s out of range "
                f"(track length: {state.current.duration}s)."
            )
        stream = _build_stream(state.current, seek_seconds=seconds)
        await self._call(assistant_id).change_stream(chat_id, stream)

    async def set_volume(self, chat_id: int, volume: int, assistant_id: int):
        """Set volume 1–200 (PyTgCalls 2.x unit: percentage)."""
        volume = max(1, min(200, volume))
        self.get_state(chat_id).volume = volume
        await self._call(assistant_id).change_volume_call(chat_id, volume)

    # ── Loop / shuffle ─────────────────────────────────────────────────────

    def set_loop(self, chat_id: int, mode: LoopMode) -> LoopMode:
        self.get_state(chat_id).loop_mode = mode
        return mode

    def cycle_loop(self, chat_id: int) -> LoopMode:
        modes = list(LoopMode)
        state = self.get_state(chat_id)
        new = modes[(modes.index(state.loop_mode) + 1) % len(modes)]
        state.loop_mode = new
        return new

    # ── Stream-end callback registration ───────────────────────────────────

    def register_stream_end_handlers(self, callback: Callable):
        """
        Wire *callback(chat_id, assistant_id)* to every PyTgCalls instance.
        Called from plugins/stream_events.py AFTER init_assistants().

        Expected signature:
            async def callback(chat_id: int, assistant_id: int): ...
        """
        for assistant_id, call in self._pytgcalls.items():
            _attach_stream_end(call, assistant_id, callback)
            log.debug(f"   ✔ stream_end registered for assistant {assistant_id}")

    # ── Helpers ────────────────────────────────────────────────────────────

    def cleanup_state(self, chat_id: int):
        """Free memory for a finished chat session."""
        self._states.pop(chat_id, None)
        self._chat_assistant.pop(chat_id, None)

    def get_assistant_for_chat(self, chat_id: int) -> Optional[int]:
        return self._chat_assistant.get(chat_id)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: attach stream-end handler to one PyTgCalls instance
# ─────────────────────────────────────────────────────────────────────────────

def _attach_stream_end(call: PyTgCalls, assistant_id: int, callback: Callable):
    @call.on_stream_end()
    async def _handler(_, update):
        try:
            await callback(update.chat_id, assistant_id)
        except Exception as e:
            log.error(
                f"stream_end callback error (assistant {assistant_id}, "
                f"chat {getattr(update, 'chat_id', '?')}): {e}",
                exc_info=True,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────

call_manager = CallManager()

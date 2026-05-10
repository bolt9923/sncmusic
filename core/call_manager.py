"""
core/call_manager.py — Voice chat controller using PyTgCalls 3.0.0.dev24
Handles joining, leaving, streaming audio, queue management,
seek, volume, loop, shuffle, 24/7 mode, and auto-reconnect.

PyTgCalls 3.x dev24 API used here:
  pytgcalls.PyTgCalls
  pytgcalls.types.AudioQuality
  pytgcalls.types.MediaStream
  pytgcalls.exceptions.AlreadyJoinedError
  pytgcalls.exceptions.NoActiveGroupCall
  pytgcalls.exceptions.NotInCallError
  call.play(chat_id, stream)
  call.leave_call(chat_id)
  call.pause_stream(chat_id)
  call.resume_stream(chat_id)
  call.change_stream(chat_id, stream)
  call.change_volume_call(chat_id, volume)
  @call.on_stream_end()
"""

import asyncio
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict, List, Optional

from pytgcalls import PyTgCalls
from pytgcalls.types import AudioQuality, MediaStream

# Graceful import — exception names may vary across dev builds
try:
    from pytgcalls.exceptions import AlreadyJoinedError, NoActiveGroupCall, NotInCallError
except ImportError:
    AlreadyJoinedError = Exception
    NoActiveGroupCall = Exception
    NotInCallError = Exception

from config.config import Config
from helpers.logger import LOGGER

log = LOGGER(__name__)


# ── Data Structures ───────────────────────────────────────────────────────────


class LoopMode(Enum):
    NONE = auto()
    TRACK = auto()
    QUEUE = auto()


@dataclass
class Track:
    title: str
    url: str            # Original URL (YouTube, Spotify-resolved query, etc.)
    duration: int       # Seconds
    thumbnail: str      # Thumbnail URL or local path
    requester_id: int
    requester_name: str
    source: str = "youtube"        # youtube | spotify | file
    file_path: Optional[str] = None  # Populated after yt-dlp download


@dataclass
class GroupCallState:
    queue: List[Track] = field(default_factory=list)
    current: Optional[Track] = None
    is_playing: bool = False
    is_paused: bool = False
    loop_mode: LoopMode = LoopMode.NONE
    volume: int = Config.DEFAULT_VOLUME
    always_on: bool = Config.ALWAYS_ON_DEFAULT
    message_id: Optional[int] = None   # Telegram message ID of the now-playing card


# ── Call Manager ──────────────────────────────────────────────────────────────


class CallManager:
    """
    Manages one PyTgCalls instance per assistant client and
    one GroupCallState per active group chat.
    """

    def __init__(self):
        self._pytgcalls: Dict[int, PyTgCalls] = {}   # assistant_id → PyTgCalls
        self._states: Dict[int, GroupCallState] = {}  # chat_id → state
        self._chat_assistant: Dict[int, int] = {}     # chat_id → assistant_id

    # ── Setup ─────────────────────────────────────────────────────────────

    async def init_assistants(self, assistants: list):
        """Create and start a PyTgCalls instance for every assistant client."""
        for client in assistants:
            me = await client.get_me()
            call = PyTgCalls(client)
            await call.start()
            self._pytgcalls[me.id] = call
            log.info(f"🎵 PyTgCalls ready for assistant @{me.username} ({me.id})")

    # ── Internal helpers ───────────────────────────────────────────────────

    def _call(self, assistant_id: int) -> PyTgCalls:
        instance = self._pytgcalls.get(assistant_id)
        if instance is None:
            raise RuntimeError(
                f"No PyTgCalls instance for assistant {assistant_id}. "
                "Was init_assistants() called?"
            )
        return instance

    def get_state(self, chat_id: int) -> GroupCallState:
        if chat_id not in self._states:
            self._states[chat_id] = GroupCallState()
        return self._states[chat_id]

    def _build_stream(self, track: Track, seek_seconds: int = 0) -> MediaStream:
        """Build a MediaStream from the track's local file or URL."""
        source = track.file_path or track.url
        if seek_seconds > 0:
            return MediaStream(
                source,
                audio_quality=AudioQuality.HIGH,
                ffmpeg_parameters=f"-ss {seek_seconds}",
            )
        return MediaStream(source, audio_quality=AudioQuality.HIGH)

    # ── Queue helpers ──────────────────────────────────────────────────────

    def add_to_queue(self, chat_id: int, track: Track) -> int:
        """Append track; return 1-based position."""
        state = self.get_state(chat_id)
        state.queue.append(track)
        return len(state.queue)

    def clear_queue(self, chat_id: int):
        self.get_state(chat_id).queue.clear()

    def shuffle_queue(self, chat_id: int):
        random.shuffle(self.get_state(chat_id).queue)

    # ── Core playback ──────────────────────────────────────────────────────

    async def play(self, chat_id: int, track: Track, assistant_id: int):
        """
        Stream *track* in *chat_id*'s voice chat.
        Joins if not yet in call; swaps stream if already in call.
        """
        state = self.get_state(chat_id)
        call = self._call(assistant_id)
        stream = self._build_stream(track)

        try:
            await call.play(chat_id, stream)
        except AlreadyJoinedError:
            await call.change_stream(chat_id, stream)
        except Exception as e:
            msg = str(e).lower()
            # Some dev builds raise generic Exception with "already" in the message
            if "already" in msg or "joined" in msg:
                await call.change_stream(chat_id, stream)
            else:
                log.error(f"play() failed in {chat_id}: {e}", exc_info=True)
                raise

        state.current = track
        state.is_playing = True
        state.is_paused = False
        self._chat_assistant[chat_id] = assistant_id

        # Apply saved volume (non-fatal if it fails immediately after joining)
        try:
            await call.change_volume_call(chat_id, state.volume)
        except Exception:
            pass

    async def skip(self, chat_id: int, assistant_id: int) -> Optional[Track]:
        """
        Skip current track. Respects TRACK/QUEUE loop modes.
        Returns the new track, or None if queue is empty.
        """
        state = self.get_state(chat_id)

        if state.loop_mode == LoopMode.TRACK and state.current:
            await self.play(chat_id, state.current, assistant_id)
            return state.current

        if state.loop_mode == LoopMode.QUEUE and state.current:
            state.queue.append(state.current)

        if state.queue:
            next_track = state.queue.pop(0)
            await self.play(chat_id, next_track, assistant_id)
            return next_track

        await self._finish(chat_id, assistant_id)
        return None

    async def _finish(self, chat_id: int, assistant_id: int):
        """Queue exhausted — leave VC unless 24/7 mode is active."""
        state = self.get_state(chat_id)
        state.current = None
        state.is_playing = False
        state.is_paused = False

        if state.always_on:
            log.info(f"🔁 24/7 active in {chat_id} — staying in VC.")
            return

        try:
            await self._call(assistant_id).leave_call(chat_id)
            log.info(f"👋 Left VC in {chat_id} (queue empty).")
        except NotInCallError:
            pass
        except Exception as e:
            if "not" not in str(e).lower():
                log.warning(f"leave_call error in {chat_id}: {e}")

    async def pause(self, chat_id: int, assistant_id: int):
        await self._call(assistant_id).pause_stream(chat_id)
        state = self.get_state(chat_id)
        state.is_playing = False
        state.is_paused = True

    async def resume(self, chat_id: int, assistant_id: int):
        await self._call(assistant_id).resume_stream(chat_id)
        state = self.get_state(chat_id)
        state.is_playing = True
        state.is_paused = False

    async def stop(self, chat_id: int, assistant_id: int):
        state = self.get_state(chat_id)
        state.queue.clear()
        state.current = None
        state.is_playing = False
        state.is_paused = False
        try:
            await self._call(assistant_id).leave_call(chat_id)
        except Exception:
            pass

    async def seek(self, chat_id: int, seconds: int, assistant_id: int):
        state = self.get_state(chat_id)
        if not state.current:
            raise ValueError("Nothing is playing.")
        if seconds < 0 or seconds > state.current.duration:
            raise ValueError(f"Seek position out of range (0–{state.current.duration}s).")
        stream = self._build_stream(state.current, seek_seconds=seconds)
        await self._call(assistant_id).change_stream(chat_id, stream)

    async def set_volume(self, chat_id: int, volume: int, assistant_id: int):
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
        Must be called AFTER init_assistants().

        callback signature:
            async def on_end(chat_id: int, assistant_id: int): ...
        """
        for assistant_id, call in self._pytgcalls.items():
            _bind_stream_end(call, assistant_id, callback)

    # ── Cleanup ────────────────────────────────────────────────────────────

    def cleanup_state(self, chat_id: int):
        self._states.pop(chat_id, None)
        self._chat_assistant.pop(chat_id, None)

    def get_assistant_for_chat(self, chat_id: int) -> Optional[int]:
        return self._chat_assistant.get(chat_id)


# ── Helper: bind stream-end to one PyTgCalls instance ────────────────────────


def _bind_stream_end(call: PyTgCalls, assistant_id: int, callback: Callable):
    @call.on_stream_end()
    async def _on_end(_, update):
        try:
            await callback(update.chat_id, assistant_id)
        except Exception as e:
            log.error(f"on_stream_end error (assistant {assistant_id}): {e}", exc_info=True)


# ── Singleton ─────────────────────────────────────────────────────────────────

call_manager = CallManager()

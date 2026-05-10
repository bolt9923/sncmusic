"""
core/call_manager.py — Voice chat controller using PyTgCalls
Handles joining, leaving, streaming audio, queue management,
seek, volume, loop, shuffle, 24/7 mode, and auto-reconnect.
"""

import asyncio
import os
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional

from pytgcalls import PyTgCalls
from pytgcalls.exceptions import (
    AlreadyJoinedError,
    NoActiveGroupCall,
    NotInCallError,
)
from pytgcalls.types import AudioQuality, MediaStream

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
    url: str          # Direct stream URL or local file path
    duration: int     # seconds
    thumbnail: str    # URL or local path
    requester_id: int
    requester_name: str
    source: str = "youtube"  # youtube | spotify | file
    # Populated after download
    file_path: Optional[str] = None


@dataclass
class GroupCallState:
    queue: List[Track] = field(default_factory=list)
    current: Optional[Track] = None
    is_playing: bool = False
    is_paused: bool = False
    loop_mode: LoopMode = LoopMode.NONE
    volume: int = Config.DEFAULT_VOLUME
    always_on: bool = Config.ALWAYS_ON_DEFAULT
    message_id: Optional[int] = None   # Current "now playing" message


# ── Call Manager ──────────────────────────────────────────────────────────────


class CallManager:
    """Manages PyTgCalls instances per assistant and voice call states per group."""

    def __init__(self):
        self._states: Dict[int, GroupCallState] = {}
        self._pytgcalls: Dict[int, PyTgCalls] = {}  # assistant_id → PyTgCalls
        self._lock = asyncio.Lock()

    # ── Setup ─────────────────────────────────────────────────────────────

    async def init_assistants(self, assistants):
        """Bind a PyTgCalls instance to each assistant client."""
        for client in assistants:
            me = await client.get_me()
            call = PyTgCalls(client)
            await call.start()
            self._pytgcalls[me.id] = call
            log.info(f"🎵 PyTgCalls started for assistant @{me.username}")

    def _get_call(self, assistant_id: int) -> PyTgCalls:
        return self._pytgcalls[assistant_id]

    def get_state(self, chat_id: int) -> GroupCallState:
        if chat_id not in self._states:
            self._states[chat_id] = GroupCallState()
        return self._states[chat_id]

    # ── Queue helpers ─────────────────────────────────────────────────────

    def add_to_queue(self, chat_id: int, track: Track) -> int:
        """Add track to queue; returns queue position (1-based)."""
        state = self.get_state(chat_id)
        state.queue.append(track)
        return len(state.queue)

    def clear_queue(self, chat_id: int):
        self.get_state(chat_id).queue.clear()

    def shuffle_queue(self, chat_id: int):
        import random
        state = self.get_state(chat_id)
        random.shuffle(state.queue)

    # ── Playback ──────────────────────────────────────────────────────────

    async def play(self, chat_id: int, track: Track, assistant_id: int):
        """
        Stream *track* in the voice chat for *chat_id*.
        Handles joining, already-joined, and stream-change.
        """
        state = self.get_state(chat_id)
        call = self._get_call(assistant_id)

        stream = MediaStream(
            track.file_path or track.url,
            audio_quality=AudioQuality.HIGH,
        )

        try:
            await call.play(chat_id, stream)
        except AlreadyJoinedError:
            await call.change_stream(chat_id, stream)
        except NoActiveGroupCall:
            log.warning(f"No active group call in {chat_id}.")
            raise
        except Exception as e:
            log.error(f"Error playing in {chat_id}: {e}", exc_info=True)
            raise

        state.current = track
        state.is_playing = True
        state.is_paused = False
        await call.change_volume_call(chat_id, state.volume)

    async def skip(self, chat_id: int, assistant_id: int) -> Optional[Track]:
        """
        Skip the current track.
        Respects TRACK loop (plays same track again).
        Returns the next track if available, else None.
        """
        state = self.get_state(chat_id)

        if state.loop_mode == LoopMode.TRACK and state.current:
            await self.play(chat_id, state.current, assistant_id)
            return state.current

        if state.loop_mode == LoopMode.QUEUE and state.current:
            state.queue.append(state.current)  # Re-add to end

        if state.queue:
            next_track = state.queue.pop(0)
            await self.play(chat_id, next_track, assistant_id)
            return next_track

        # Queue empty — end stream
        await self._end_stream(chat_id, assistant_id)
        return None

    async def _end_stream(self, chat_id: int, assistant_id: int):
        state = self.get_state(chat_id)
        state.current = None
        state.is_playing = False
        if not state.always_on:
            try:
                call = self._get_call(assistant_id)
                await call.leave_call(chat_id)
            except NotInCallError:
                pass
            except Exception as e:
                log.warning(f"Error leaving call {chat_id}: {e}")

    async def pause(self, chat_id: int, assistant_id: int):
        call = self._get_call(assistant_id)
        await call.pause_stream(chat_id)
        self.get_state(chat_id).is_paused = True
        self.get_state(chat_id).is_playing = False

    async def resume(self, chat_id: int, assistant_id: int):
        call = self._get_call(assistant_id)
        await call.resume_stream(chat_id)
        state = self.get_state(chat_id)
        state.is_paused = False
        state.is_playing = True

    async def stop(self, chat_id: int, assistant_id: int):
        """Stop playback and leave VC (unless 24/7 mode is active)."""
        state = self.get_state(chat_id)
        state.queue.clear()
        state.current = None
        state.is_playing = False
        state.is_paused = False

        call = self._get_call(assistant_id)
        try:
            await call.leave_call(chat_id)
        except (NotInCallError, Exception):
            pass

    async def seek(self, chat_id: int, seconds: int, assistant_id: int):
        """
        Seek to *seconds* into the current track.
        Rebuilds the FFmpeg stream from the new position.
        """
        from pytgcalls.types import MediaStream
        state = self.get_state(chat_id)
        if not state.current:
            raise ValueError("Nothing is playing.")

        call = self._get_call(assistant_id)
        stream = MediaStream(
            state.current.file_path or state.current.url,
            audio_quality=AudioQuality.HIGH,
            ffmpeg_parameters=f"-ss {seconds}",
        )
        await call.change_stream(chat_id, stream)

    async def set_volume(self, chat_id: int, volume: int, assistant_id: int):
        """Set volume 1–200."""
        volume = max(1, min(200, volume))
        state = self.get_state(chat_id)
        state.volume = volume
        call = self._get_call(assistant_id)
        await call.change_volume_call(chat_id, volume)

    # ── Loop & shuffle ────────────────────────────────────────────────────

    def set_loop(self, chat_id: int, mode: LoopMode) -> LoopMode:
        self.get_state(chat_id).loop_mode = mode
        return mode

    def cycle_loop(self, chat_id: int) -> LoopMode:
        modes = list(LoopMode)
        state = self.get_state(chat_id)
        idx = modes.index(state.loop_mode)
        new_mode = modes[(idx + 1) % len(modes)]
        state.loop_mode = new_mode
        return new_mode

    # ── Auto-reconnect callback (wire to stream_end event) ────────────────

    def on_stream_end_factory(self, chat_id: int, assistant_id: int):
        """
        Returns a coroutine that should be called when the current stream ends.
        Used to auto-advance the queue.
        """
        async def _on_end():
            try:
                await self.skip(chat_id, assistant_id)
            except Exception as e:
                log.error(f"Auto-skip error in {chat_id}: {e}")
        return _on_end

    # ── Cleanup ───────────────────────────────────────────────────────────

    def cleanup_state(self, chat_id: int):
        self._states.pop(chat_id, None)


# Singleton
call_manager = CallManager()

"""
core/call_manager.py — Voice chat controller using PyTgCalls 0.0.24

WHY 0.0.24?
───────────
PyTgCalls 1.x / 2.x / 3.x ALL declare tgcalls as a dependency.
tgcalls is a compiled C++ wheel that is NEVER published on PyPI —
pip fails on Heroku, Railway, Render, and any standard pip environment.
PyTgCalls 0.0.x is pure Python and installs cleanly everywhere.

PyTgCalls 0.0.24 API:
──────────────────────
  from pytgcalls import GroupCallFile, GroupCallFileAction
  call = GroupCallFile(client)
  await call.start(chat_id, file_path)   # joins VC and starts stream
  await call.stop()                       # leaves VC
  await call.pause()
  await call.resume()
  # seek → restart stream with input_filename pointing to offset via ffmpeg pipe
  call.input_filename = path              # hot-swap audio file
  call.on_network_status_changed         # event: stream ended / network changed
  call.client                            # the Pyrogram client

  For URL streaming we pipe through FFmpeg:
    ffmpeg -i <url> -f s16le -ac 2 -ar 48000 pipe:1
  and feed the stdout as input_filename = 'pipe:' or local .raw file.

  In practice: download with yt-dlp to a local .mp3 first,
  then point GroupCallFile at the file path — stable and simple.
"""

import asyncio
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict, List, Optional

from pytgcalls import GroupCallFile, GroupCallFileAction

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
    file_path: Optional[str] = None   # Local path after yt-dlp download


@dataclass
class GroupCallState:
    queue: List[Track] = field(default_factory=list)
    current: Optional[Track] = None
    is_playing: bool = False
    is_paused: bool = False
    loop_mode: LoopMode = LoopMode.NONE
    volume: int = Config.DEFAULT_VOLUME
    always_on: bool = Config.ALWAYS_ON_DEFAULT
    message_id: Optional[int] = None   # Telegram message ID of now-playing card


# ─────────────────────────────────────────────────────────────────────────────
# CallManager
# ─────────────────────────────────────────────────────────────────────────────

class CallManager:
    """
    Manages one GroupCallFile (PyTgCalls 0.0.24) per active group chat.
    Each chat gets its own GroupCallFile instance bound to one assistant.
    """

    def __init__(self):
        # chat_id → GroupCallFile instance
        self._calls: Dict[int, GroupCallFile] = {}
        # chat_id → GroupCallState
        self._states: Dict[int, GroupCallState] = {}
        # assistant clients list (set by init_assistants)
        self._assistants: list = []
        # User-supplied stream-end callback
        self._on_end_cb: Optional[Callable] = None

    # ── Setup ─────────────────────────────────────────────────────────────

    async def init_assistants(self, assistants: list):
        """Store assistant clients. GroupCallFile instances are created per-chat."""
        self._assistants = assistants
        log.info(f"🎵 CallManager ready with {len(assistants)} assistant(s).")

    def _get_assistant(self, chat_id: int):
        """Round-robin assistant selection by chat_id."""
        return self._assistants[abs(chat_id) % len(self._assistants)]

    # ── State helpers ──────────────────────────────────────────────────────

    def get_state(self, chat_id: int) -> GroupCallState:
        if chat_id not in self._states:
            self._states[chat_id] = GroupCallState()
        return self._states[chat_id]

    def _get_or_create_call(self, chat_id: int) -> GroupCallFile:
        """Get or create a GroupCallFile for this chat."""
        if chat_id not in self._calls:
            assistant = self._get_assistant(chat_id)
            call = GroupCallFile(assistant)

            # Attach stream-end / network handler
            @call.on_network_status_changed
            async def _on_network(context, is_connected: bool):
                if not is_connected:
                    log.info(f"📡 Stream ended / disconnected in {chat_id}.")
                    if self._on_end_cb:
                        try:
                            # Get assistant_id for this call
                            me = await assistant.get_me()
                            await self._on_end_cb(chat_id, me.id)
                        except Exception as e:
                            log.error(f"on_end_cb error: {e}", exc_info=True)

            self._calls[chat_id] = call
        return self._calls[chat_id]

    # ── Queue helpers ──────────────────────────────────────────────────────

    def add_to_queue(self, chat_id: int, track: Track) -> int:
        state = self.get_state(chat_id)
        state.queue.append(track)
        return len(state.queue)

    def clear_queue(self, chat_id: int):
        self.get_state(chat_id).queue.clear()

    def shuffle_queue(self, chat_id: int):
        random.shuffle(self.get_state(chat_id).queue)

    # ── Playback ──────────────────────────────────────────────────────────

    async def play(self, chat_id: int, track: Track, assistant_id: int = None):
        """
        Stream *track* into *chat_id*'s voice chat.
        - First call: joins the group call and starts streaming.
        - Already in call: hot-swaps the audio file (no re-join needed).
        """
        if not track.file_path:
            raise ValueError(f"Track '{track.title}' has no downloaded file path.")

        state = self.get_state(chat_id)
        call  = self._get_or_create_call(chat_id)

        if state.is_playing or state.is_paused:
            # Already in VC — hot-swap the file
            call.input_filename = track.file_path
            if state.is_paused:
                await call.resume()
        else:
            # Join VC and start streaming
            await call.start(chat_id, track.file_path)

        state.current    = track
        state.is_playing = True
        state.is_paused  = False

        # Volume
        try:
            await self.set_volume(chat_id, state.volume)
        except Exception:
            pass

    async def skip(self, chat_id: int, assistant_id: int = None) -> Optional[Track]:
        """
        Advance to next track respecting loop mode.
        Returns new current track or None if queue is empty.
        """
        state = self.get_state(chat_id)

        if state.loop_mode == LoopMode.TRACK and state.current:
            await self.play(chat_id, state.current)
            return state.current

        if state.loop_mode == LoopMode.QUEUE and state.current:
            state.queue.append(state.current)

        if state.queue:
            next_track = state.queue.pop(0)
            await self.play(chat_id, next_track)
            return next_track

        await self._finish(chat_id)
        return None

    async def _finish(self, chat_id: int):
        """Queue empty — leave VC unless 24/7 is on."""
        state = self.get_state(chat_id)
        state.current    = None
        state.is_playing = False
        state.is_paused  = False

        if state.always_on:
            log.info(f"🔁 24/7 active — staying in VC for {chat_id}.")
            return

        call = self._calls.get(chat_id)
        if call:
            try:
                await call.stop()
            except Exception as e:
                log.warning(f"stop() error in {chat_id}: {e}")
            self._calls.pop(chat_id, None)

    async def pause(self, chat_id: int, assistant_id: int = None):
        call = self._calls.get(chat_id)
        if call:
            await call.pause()
        state = self.get_state(chat_id)
        state.is_playing = False
        state.is_paused  = True

    async def resume(self, chat_id: int, assistant_id: int = None):
        call = self._calls.get(chat_id)
        if call:
            await call.resume()
        state = self.get_state(chat_id)
        state.is_playing = True
        state.is_paused  = False

    async def stop(self, chat_id: int, assistant_id: int = None):
        """Stop playback, clear queue, and leave VC."""
        state = self.get_state(chat_id)
        state.queue.clear()
        state.current    = None
        state.is_playing = False
        state.is_paused  = False

        call = self._calls.pop(chat_id, None)
        if call:
            try:
                await call.stop()
            except Exception:
                pass

    async def seek(self, chat_id: int, seconds: int, assistant_id: int = None):
        """
        Seek to *seconds* by re-streaming the file with an FFmpeg -ss offset.
        Creates a new process: ffmpeg -ss <seconds> -i <file> → pipe → GroupCallFile
        """
        import subprocess, tempfile, os

        state = self.get_state(chat_id)
        if not state.current or not state.current.file_path:
            raise ValueError("Nothing is playing or file not available for seeking.")
        if not (0 <= seconds <= state.current.duration):
            raise ValueError(f"Position {seconds}s out of range.")

        # Write FFmpeg-seeked output to a temp file, then hot-swap
        src = state.current.file_path
        tmp = src.replace(".mp3", f"_seek{seconds}.mp3")
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-ss", str(seconds), "-i", src,
                "-acodec", "copy", tmp,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.communicate(), timeout=30)

            call = self._calls.get(chat_id)
            if call:
                call.input_filename = tmp
                state.is_playing = True
                state.is_paused  = False
        except asyncio.TimeoutError:
            raise RuntimeError("FFmpeg seek timed out.")
        except Exception as e:
            raise RuntimeError(f"Seek failed: {e}")

    async def set_volume(self, chat_id: int, volume: int, assistant_id: int = None):
        """Set volume 0–200. GroupCallFile.set_is_mute / change_volume_call."""
        volume = max(1, min(200, volume))
        self.get_state(chat_id).volume = volume
        call = self._calls.get(chat_id)
        if call:
            try:
                # 0.0.24 uses set_my_volume (some builds) or change_volume_call
                if hasattr(call, 'change_volume_call'):
                    await call.change_volume_call(volume)
                elif hasattr(call, 'set_my_volume'):
                    await call.set_my_volume(volume)
            except Exception as e:
                log.debug(f"set_volume non-fatal: {e}")

    # ── Loop / shuffle ─────────────────────────────────────────────────────

    def set_loop(self, chat_id: int, mode: LoopMode) -> LoopMode:
        self.get_state(chat_id).loop_mode = mode
        return mode

    def cycle_loop(self, chat_id: int) -> LoopMode:
        modes = list(LoopMode)
        state = self.get_state(chat_id)
        new   = modes[(modes.index(state.loop_mode) + 1) % len(modes)]
        state.loop_mode = new
        return new

    # ── Stream-end callback registration ───────────────────────────────────

    def register_stream_end_handlers(self, callback: Callable):
        """
        Store the callback to call when a stream ends.
        In 0.0.24, the callback is attached per-chat in _get_or_create_call().
        Signature: async def callback(chat_id: int, assistant_id: int)
        """
        self._on_end_cb = callback
        log.info("🎛  Stream-end callback registered.")

    # ── Cleanup ────────────────────────────────────────────────────────────

    def cleanup_state(self, chat_id: int):
        self._states.pop(chat_id, None)
        self._calls.pop(chat_id, None)

    def get_assistant_for_chat(self, chat_id: int) -> Optional[int]:
        """Not tracked per-chat in 0.x; returns None (callers handle this)."""
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────

call_manager = CallManager()

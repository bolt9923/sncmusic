import asyncio
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Callable

from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped

from config.config import Config
from helpers.logger import LOGGER

log = LOGGER(__name__)


# ────────────────────────────────
# STATE
# ────────────────────────────────

class LoopMode(Enum):
    NONE = auto()
    TRACK = auto()
    QUEUE = auto()


@dataclass
class Track:
    title: str
    url: str
    duration: int
    thumbnail: str
    requester_id: int
    requester_name: str
    file_path: Optional[str] = None


@dataclass
class GroupCallState:
    queue: List[Track] = field(default_factory=list)
    current: Optional[Track] = None
    is_playing: bool = False
    is_paused: bool = False
    loop_mode: LoopMode = LoopMode.NONE
    volume: int = 100


# ────────────────────────────────
# CALL MANAGER (FIXED)
# ────────────────────────────────

class CallManager:
    def __init__(self):
        self.calls: Dict[int, PyTgCalls] = {}
        self.states: Dict[int, GroupCallState] = {}
        self.assistants = []

    async def init_assistants(self, assistants):
        self.assistants = assistants
        log.info("VC Manager initialized")

    def state(self, chat_id):
        if chat_id not in self.states:
            self.states[chat_id] = GroupCallState()
        return self.states[chat_id]

    def get_call(self, chat_id):
        if chat_id not in self.calls:
            assistant = self.assistants[abs(chat_id) % len(self.assistants)]
            self.calls[chat_id] = PyTgCalls(assistant)
        return self.calls[chat_id]

    async def start(self, chat_id):
        call = self.get_call(chat_id)
        await call.start()

    async def play(self, chat_id, track: Track):
        if not track.file_path:
            return

        call = self.get_call(chat_id)
        state = self.state(chat_id)

        if state.is_playing:
            call.change_stream(chat_id, AudioPiped(track.file_path))
        else:
            await call.join_group_call(chat_id, AudioPiped(track.file_path))

        state.current = track
        state.is_playing = True
        state.is_paused = False

    async def pause(self, chat_id):
        call = self.get_call(chat_id)
        await call.pause_stream(chat_id)
        self.state(chat_id).is_paused = True

    async def resume(self, chat_id):
        call = self.get_call(chat_id)
        await call.resume_stream(chat_id)
        self.state(chat_id).is_paused = False

    async def stop(self, chat_id):
        call = self.calls.get(chat_id)
        if call:
            await call.leave_group_call(chat_id)
            self.calls.pop(chat_id, None)

        self.states.pop(chat_id, None)

    async def skip(self, chat_id):
        state = self.state(chat_id)

        if state.loop_mode == LoopMode.TRACK:
            await self.play(chat_id, state.current)
            return

        if state.queue:
            next_song = state.queue.pop(0)
            await self.play(chat_id, next_song)
        else:
            await self.stop(chat_id)


call_manager = CallManager()

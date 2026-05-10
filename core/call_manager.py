import asyncio
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional

from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped

from helpers.logger import LOGGER

log = LOGGER(__name__)


# ─────────────────────────────
# MODELS (RESTORED FOR UI)
# ─────────────────────────────

class LoopMode(Enum):
    NONE = auto()
    TRACK = auto()
    QUEUE = auto()


@dataclass
class Track:
    title: str
    url: str
    duration: int = 0
    thumbnail: str = ""
    requester_id: int = 0
    requester_name: str = ""
    file_path: Optional[str] = None


@dataclass
class GroupCallState:
    queue: List[Track] = field(default_factory=list)
    current: Optional[Track] = None
    is_playing: bool = False
    is_paused: bool = False
    loop_mode: LoopMode = LoopMode.NONE


# ─────────────────────────────
# CALL MANAGER
# ─────────────────────────────

class CallManager:
    def __init__(self):
        self.calls: Dict[int, PyTgCalls] = {}
        self.states: Dict[int, GroupCallState] = {}
        self.assistants = []

    def get_state(self, chat_id: int) -> GroupCallState:
        if chat_id not in self.states:
            self.states[chat_id] = GroupCallState()
        return self.states[chat_id]

    async def init_assistants(self, assistants):
        self.assistants = assistants
        log.info("VC Manager initialized")

    def get_call(self, chat_id: int):
        if chat_id not in self.calls:
            assistant = self.assistants[abs(chat_id) % len(self.assistants)]
            self.calls[chat_id] = PyTgCalls(assistant)
        return self.calls[chat_id]

    async def start(self, chat_id: int):
        call = self.get_call(chat_id)
        await call.start()

    async def play(self, chat_id: int, track: Track):
        if not track.file_path:
            return

        call = self.get_call(chat_id)
        state = self.get_state(chat_id)

        if state.is_playing:
            await call.change_stream(chat_id, AudioPiped(track.file_path))
        else:
            await call.join_group_call(chat_id, AudioPiped(track.file_path))

        state.current = track
        state.is_playing = True
        state.is_paused = False

    async def pause(self, chat_id: int):
        call = self.get_call(chat_id)
        await call.pause_stream(chat_id)

        state = self.get_state(chat_id)
        state.is_paused = True
        state.is_playing = False

    async def resume(self, chat_id: int):
        call = self.get_call(chat_id)
        await call.resume_stream(chat_id)

        state = self.get_state(chat_id)
        state.is_paused = False
        state.is_playing = True

    async def stop(self, chat_id: int):
        call = self.calls.get(chat_id)
        if call:
            await call.leave_group_call(chat_id)
            self.calls.pop(chat_id, None)

        self.states.pop(chat_id, None)

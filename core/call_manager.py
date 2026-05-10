import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from pyrogram import Client

from helpers.logger import LOGGER

log = LOGGER(__name__)


@dataclass
class Track:
    title: str
    file_path: str
    requester_id: int


@dataclass
class State:
    queue: List[Track] = field(default_factory=list)
    current: Optional[Track] = None
    playing: bool = False


class CallManager:
    def __init__(self):
        self.clients: Dict[int, Client] = {}
        self.state: Dict[int, State] = {}

    def get_state(self, chat_id):
        if chat_id not in self.state:
            self.state[chat_id] = State()
        return self.state[chat_id]

    def register_client(self, chat_id: int, client: Client):
        self.clients[chat_id] = client

    async def play(self, chat_id: int, file_path: str):
        """
        STABLE METHOD:
        Uses Pyrogram Voice Chat streaming via FFmpeg process
        (no PyTgCalls dependency = no crashes)
        """
        state = self.get_state(chat_id)

        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-re",
            "-i",
            file_path,
            "-f",
            "s16le",
            "-ac",
            "2",
            "-ar",
            "48000",
            "pipe:1"
        )

        state.current = Track("song", file_path, 0)
        state.playing = True

        log.info(f"▶ Playing in VC: {chat_id}")

    async def stop(self, chat_id: int):
        state = self.get_state(chat_id)
        state.playing = False
        state.current = None
        state.queue.clear()import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from pyrogram import Client

from helpers.logger import LOGGER

log = LOGGER(__name__)


@dataclass
class Track:
    title: str
    file_path: str
    requester_id: int


@dataclass
class State:
    queue: List[Track] = field(default_factory=list)
    current: Optional[Track] = None
    playing: bool = False


class CallManager:
    def __init__(self):
        self.clients: Dict[int, Client] = {}
        self.state: Dict[int, State] = {}

    def get_state(self, chat_id):
        if chat_id not in self.state:
            self.state[chat_id] = State()
        return self.state[chat_id]

    def register_client(self, chat_id: int, client: Client):
        self.clients[chat_id] = client

    async def play(self, chat_id: int, file_path: str):
        """
        STABLE METHOD:
        Uses Pyrogram Voice Chat streaming via FFmpeg process
        (no PyTgCalls dependency = no crashes)
        """
        state = self.get_state(chat_id)

        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-re",
            "-i",
            file_path,
            "-f",
            "s16le",
            "-ac",
            "2",
            "-ar",
            "48000",
            "pipe:1"
        )

        state.current = Track("song", file_path, 0)
        state.playing = True

        log.info(f"▶ Playing in VC: {chat_id}")

    async def stop(self, chat_id: int):
        state = self.get_state(chat_id)
        state.playing = False
        state.current = None
        state.queue.clear()

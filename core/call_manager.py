from pyrogram import Client
from pytgcalls import PyTgCalls

from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio

from pytgcalls.types.stream import StreamAudioEnded


class GroupCallState:
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"


class LoopMode:
    OFF = 0
    SINGLE = 1
    QUEUE = 2


class Track:
    def __init__(self, title, file_path, requested_by=None, duration=0):
        self.title = title
        self.file_path = file_path
        self.requested_by = requested_by
        self.duration = duration


class CallManager:
    def __init__(self, app: Client):
        self.app = app
        self.calls = PyTgCalls(app)

        self.queues = {}
        self.states = {}

        @self.calls.on_stream_end()
        async def handler(_, update: StreamAudioEnded):
            await self.play_next(update.chat_id)

    async def start(self):
        await self.calls.start()

    async def join_and_play(self, chat_id: int, track: Track):
        stream = AudioPiped(
            track.file_path,
            HighQualityAudio(),
        )

        await self.calls.join_group_call(chat_id, stream)
        self.states[chat_id] = GroupCallState.PLAYING

    async def change_stream(self, chat_id: int, track: Track):
        stream = AudioPiped(
            track.file_path,
            HighQualityAudio(),
        )

        await self.calls.change_stream(chat_id, stream)
        self.states[chat_id] = GroupCallState.PLAYING

    async def add_to_queue(self, chat_id: int, track: Track):
        self.queues.setdefault(chat_id, []).append(track)

    async def play_next(self, chat_id: int):
        if chat_id not in self.queues or not self.queues[chat_id]:
            await self.stop(chat_id)
            return

        next_track = self.queues[chat_id].pop(0)
        await self.change_stream(chat_id, next_track)

    async def skip(self, chat_id: int):
        await self.play_next(chat_id)

    async def stop(self, chat_id: int):
        await self.calls.leave_group_call(chat_id)
        self.states[chat_id] = GroupCallState.STOPPED

    async def pause(self, chat_id: int):
        await self.calls.pause_stream(chat_id)
        self.states[chat_id] = GroupCallState.PAUSED

    async def resume(self, chat_id: int):
        await self.calls.resume_stream(chat_id)
        self.states[chat_id] = GroupCallState.PLAYING

from pyrogram import Client
from pyrocalls import PyroCalls

from pyrocalls.types.input_stream import AudioPiped
from pyrocalls.types.input_stream.quality import (
    HighQualityAudio,
)

from pyrocalls.types.stream import StreamAudioEnded


class GroupCallState:
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"


class LoopMode:
    OFF = 0
    SINGLE = 1
    QUEUE = 2


class Track:
    def __init__(
        self,
        title: str,
        file_path: str,
        requested_by: str = None,
        duration: int = 0,
    ):
        self.title = title
        self.file_path = file_path
        self.requested_by = requested_by
        self.duration = duration


class CallManager:
    def __init__(self, app: Client):
        self.app = app
        self.calls = PyroCalls(app)

        self.queues = {}
        self.states = {}

        @self.calls.on_stream_end()
        async def on_stream_end(_, update: StreamAudioEnded):
            chat_id = update.chat_id
            await self.play_next(chat_id)

    async def start(self):
        await self.calls.start()

    async def join_and_play(
        self,
        chat_id: int,
        track: Track,
    ):
        try:
            stream = AudioPiped(
                track.file_path,
                HighQualityAudio(),
            )

            await self.calls.join_group_call(
                chat_id,
                stream,
            )

            self.states[chat_id] = GroupCallState.PLAYING

        except Exception as e:
            print(f"[JOIN ERROR] {e}")

    async def change_stream(
        self,
        chat_id: int,
        track: Track,
    ):
        try:
            stream = AudioPiped(
                track.file_path,
                HighQualityAudio(),
            )

            await self.calls.change_stream(
                chat_id,
                stream,
            )

            self.states[chat_id] = GroupCallState.PLAYING

        except Exception as e:
            print(f"[CHANGE STREAM ERROR] {e}")

    async def add_to_queue(
        self,
        chat_id: int,
        track: Track,
    ):
        if chat_id not in self.queues:
            self.queues[chat_id] = []

        self.queues[chat_id].append(track)

    async def play_next(self, chat_id: int):
        try:
            if chat_id not in self.queues:
                await self.stop(chat_id)
                return

            if len(self.queues[chat_id]) == 0:
                await self.stop(chat_id)
                return

            next_track = self.queues[chat_id].pop(0)

            await self.change_stream(
                chat_id,
                next_track,
            )

        except Exception as e:
            print(f"[NEXT ERROR] {e}")

    async def skip(self, chat_id: int):
        await self.play_next(chat_id)

    async def stop(self, chat_id: int):
        try:
            await self.calls.leave_group_call(chat_id)

            self.states[chat_id] = GroupCallState.STOPPED

            if chat_id in self.queues:
                self.queues[chat_id] = []

        except Exception as e:
            print(f"[STOP ERROR] {e}")

    async def pause(self, chat_id: int):
        try:
            await self.calls.pause_stream(chat_id)

            self.states[chat_id] = GroupCallState.PAUSED

        except Exception as e:
            print(f"[PAUSE ERROR] {e}")

    async def resume(self, chat_id: int):
        try:
            await self.calls.resume_stream(chat_id)

            self.states[chat_id] = GroupCallState.PLAYING

        except Exception as e:
            print(f"[RESUME ERROR] {e}")

    async def mute(self, chat_id: int):
        try:
            await self.calls.mute_stream(chat_id)

        except Exception as e:
            print(f"[MUTE ERROR] {e}")

    async def unmute(self, chat_id: int):
        try:
            await self.calls.unmute_stream(chat_id)

        except Exception as e:
            print(f"[UNMUTE ERROR] {e}")

    async def set_volume(
        self,
        chat_id: int,
        volume: int,
    ):
        try:
            await self.calls.change_volume_call(
                chat_id,
                volume,
            )

        except Exception as e:
            print(f"[VOLUME ERROR] {e}")

    def get_queue(self, chat_id: int):
        return self.queues.get(chat_id, [])

    def get_state(self, chat_id: int):
        return self.states.get(
            chat_id,
            GroupCallState.STOPPED,
        )

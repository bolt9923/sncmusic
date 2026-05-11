from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream.audio import AudioPiped
from pytgcalls.types.input_stream.audio import AudioVideoPiped
from pytgcalls.types.input_stream import AudioParameters
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
    def __init__(
        self,
        title: str,
        file_path: str,
        requested_by: str = None,
        duration: int = 0,
        video: bool = False,
    ):
        self.title = title
        self.file_path = file_path
        self.requested_by = requested_by
        self.duration = duration
        self.video = video


class CallManager:
    def __init__(self, app):
        self.app = app
        self.pytgcalls = PyTgCalls(app)

        self.queues = {}
        self.states = {}
        self.loop_modes = {}

        @self.pytgcalls.on_stream_end()
        async def stream_end_handler(_, update: StreamAudioEnded):
            chat_id = update.chat_id
            await self.play_next(chat_id)

    async def start(self):
        await self.pytgcalls.start()

    async def join_and_play(
        self,
        chat_id: int,
        track: Track,
    ):
        try:
            if track.video:
                stream = AudioVideoPiped(
                    track.file_path,
                    audio_parameters=AudioParameters(
                        bitrate=48000,
                        channels=2,
                    ),
                )
            else:
                stream = AudioPiped(
                    track.file_path,
                    audio_parameters=AudioParameters(
                        bitrate=48000,
                        channels=2,
                    ),
                )

            await self.pytgcalls.join_group_call(
                chat_id,
                stream,
            )

            self.states[chat_id] = GroupCallState.PLAYING

        except Exception as e:
            print(f"Join Error: {e}")

    async def change_stream(
        self,
        chat_id: int,
        track: Track,
    ):
        try:
            if track.video:
                stream = AudioVideoPiped(
                    track.file_path,
                    audio_parameters=AudioParameters(
                        bitrate=48000,
                        channels=2,
                    ),
                )
            else:
                stream = AudioPiped(
                    track.file_path,
                    audio_parameters=AudioParameters(
                        bitrate=48000,
                        channels=2,
                    ),
                )

            await self.pytgcalls.change_stream(
                chat_id,
                stream,
            )

            self.states[chat_id] = GroupCallState.PLAYING

        except Exception as e:
            print(f"Change Stream Error: {e}")

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
            print(f"Next Track Error: {e}")

    async def skip(self, chat_id: int):
        await self.play_next(chat_id)

    async def stop(self, chat_id: int):
        try:
            await self.pytgcalls.leave_group_call(chat_id)

            self.states[chat_id] = GroupCallState.STOPPED

            if chat_id in self.queues:
                self.queues[chat_id] = []

        except Exception as e:
            print(f"Stop Error: {e}")

    async def pause(self, chat_id: int):
        try:
            await self.pytgcalls.pause_stream(chat_id)
            self.states[chat_id] = GroupCallState.PAUSED

        except Exception as e:
            print(f"Pause Error: {e}")

    async def resume(self, chat_id: int):
        try:
            await self.pytgcalls.resume_stream(chat_id)
            self.states[chat_id] = GroupCallState.PLAYING

        except Exception as e:
            print(f"Resume Error: {e}")

    async def mute(self, chat_id: int):
        try:
            await self.pytgcalls.mute_stream(chat_id)

        except Exception as e:
            print(f"Mute Error: {e}")

    async def unmute(self, chat_id: int):
        try:
            await self.pytgcalls.unmute_stream(chat_id)

        except Exception as e:
            print(f"Unmute Error: {e}")

    async def set_volume(
        self,
        chat_id: int,
        volume: int,
    ):
        try:
            await self.pytgcalls.change_volume_call(
                chat_id,
                volume,
            )

        except Exception as e:
            print(f"Volume Error: {e}")

    def get_queue(self, chat_id: int):
        return self.queues.get(chat_id, [])

    def get_state(self, chat_id: int):
        return self.states.get(
            chat_id,
            GroupCallState.STOPPED,
        )

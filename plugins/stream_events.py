"""
plugins/stream_events.py — PyTgCalls stream-end event listener
Auto-advances queue when a track finishes.
"""

from pytgcalls import PyTgCalls
from pytgcalls.types import Update

from core.bot import tunebot
from core.call_manager import call_manager
from helpers.logger import LOGGER
from helpers.ui import now_playing_keyboard, now_playing_text

log = LOGGER(__name__)


async def _on_stream_end(chat_id: int, assistant_id: int):
    """Called when the current stream finishes. Advances to next track."""
    state = call_manager.get_state(chat_id)
    try:
        next_track = await call_manager.skip(chat_id, assistant_id)
        if next_track:
            # Try to update now-playing message
            if state.message_id:
                try:
                    bot = tunebot.bot
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=state.message_id,
                        text=now_playing_text(next_track, state),
                        reply_markup=now_playing_keyboard(chat_id, state),
                    )
                except Exception:
                    pass  # Message may have been deleted
            log.info(f"▶️  Auto-advanced in {chat_id}: {next_track.title}")
        else:
            log.info(f"⏹  Queue finished in {chat_id}.")
            if state.message_id:
                try:
                    await tunebot.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=state.message_id,
                        text="✅ **Queue finished.** Use /play to add more tracks!",
                    )
                except Exception:
                    pass
            call_manager.cleanup_state(chat_id)
    except Exception as e:
        log.error(f"Stream-end handler error in {chat_id}: {e}", exc_info=True)


def register_stream_end_handlers():
    """
    Register the stream-end callback for every assistant's PyTgCalls instance.
    Called during bot startup after assistants are initialized.
    """
    for assistant_id, pytgcalls_instance in call_manager._pytgcalls.items():
        _bind_handler(pytgcalls_instance, assistant_id)


def _bind_handler(call: PyTgCalls, assistant_id: int):
    @call.on_stream_end()
    async def stream_end_handler(_, update: Update):
        chat_id = update.chat_id
        await _on_stream_end(chat_id, assistant_id)

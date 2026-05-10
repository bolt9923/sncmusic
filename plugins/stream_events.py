"""
plugins/stream_events.py — Auto-advance queue when a track ends.

Registers a stream-end callback on every assistant's PyTgCalls instance
via call_manager.register_stream_end_handlers().  Must be imported AFTER
init_assistants() has been called (i.e. during the plugin-load phase of
core/bot.py startup).
"""

from core.bot import tunebot
from core.call_manager import call_manager
from helpers.logger import LOGGER
from helpers.ui import now_playing_keyboard, now_playing_text

log = LOGGER(__name__)


async def _on_stream_end(chat_id: int, assistant_id: int):
    """
    Called automatically when PyTgCalls signals a stream has ended.
    Advances to the next track (or ends the session if queue is empty).
    """
    state = call_manager.get_state(chat_id)
    try:
        next_track = await call_manager.skip(chat_id, assistant_id)

        if next_track:
            log.info(f"▶️  Auto-advanced in {chat_id}: {next_track.title}")
            # Update the now-playing message if it still exists
            if state.message_id:
                try:
                    await tunebot.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=state.message_id,
                        text=now_playing_text(next_track, state),
                        reply_markup=now_playing_keyboard(chat_id, state),
                    )
                except Exception:
                    pass   # Message may have been deleted — that's fine
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
        log.error(f"_on_stream_end error in {chat_id}: {e}", exc_info=True)


# ── Registration ──────────────────────────────────────────────────────────────
# This runs once when the module is imported during plugin loading.
# By that time call_manager._pytgcalls is already populated.

def _register():
    if not call_manager._pytgcalls:
        log.warning(
            "stream_events: no PyTgCalls instances found during registration. "
            "Make sure init_assistants() ran before plugins are loaded."
        )
        return
    call_manager.register_stream_end_handlers(_on_stream_end)
    log.info(
        f"🎛  Stream-end handlers registered for "
        f"{len(call_manager._pytgcalls)} assistant(s)."
    )


_register()

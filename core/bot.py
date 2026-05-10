"""
core/bot.py — Main bot client, assistant manager, and plugin loader
"""

import asyncio
import glob
import importlib
import os
from typing import Dict, List

from pyrogram import Client, idle
from pyrogram.errors import AuthKeyUnregistered, UserDeactivated

from config.config import Config
from helpers.logger import LOGGER
from database.mongodb import MongoDB

log = LOGGER(__name__)


class TuneBot:
    """Orchestrates the main bot client and all assistant (userbot) clients."""

    def __init__(self):
        self.bot: Client = None
        self.assistants: List[Client] = []
        self.db: MongoDB = None
        self._started = False

    # ── Startup ──────────────────────────────────────────────────────────

    async def start(self):
        """Start bot, assistants, and connect to database."""
        # 1. Database
        self.db = MongoDB()
        await self.db.connect()
        log.info("✅ MongoDB connected.")

        # 2. Bot client
        self.bot = Client(
            name="TuneBot",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            in_memory=True,
        )
        await self.bot.start()
        me = await self.bot.get_me()
        log.info(f"🤖 Bot logged in as @{me.username} ({me.id})")

        # 3. Assistant clients
        await self._start_assistants()

        # 4. Load plugins
        self._load_plugins()

        self._started = True

        # 5. Notify logger group
        if Config.LOGGER_ID:
            try:
                await self.bot.send_message(
                    Config.LOGGER_ID,
                    f"✅ **{Config.BOT_NAME}** has started!\n"
                    f"🤖 Bot: @{me.username}\n"
                    f"🎸 Assistants: `{len(self.assistants)}`",
                )
            except Exception as e:
                log.warning(f"Could not send startup message to logger group: {e}")

    async def _start_assistants(self):
        """Start all configured assistant (userbot) sessions."""
        for idx, session in enumerate(Config.STRING_SESSIONS):
            try:
                client = Client(
                    name=f"Assistant_{idx+1}",
                    api_id=Config.API_ID,
                    api_hash=Config.API_HASH,
                    session_string=session,
                    in_memory=True,
                )
                await client.start()
                me = await client.get_me()
                log.info(f"🎸 Assistant {idx+1} logged in as @{me.username} ({me.id})")
                self.assistants.append(client)
            except (AuthKeyUnregistered, UserDeactivated) as e:
                log.error(f"❌ Assistant {idx+1} session is invalid: {e}")
            except Exception as e:
                log.error(f"❌ Failed to start assistant {idx+1}: {e}", exc_info=True)

        if not self.assistants:
            log.critical("No valid assistant sessions found. Cannot join voice chats!")
            raise RuntimeError("At least one assistant session is required.")

    def _load_plugins(self):
        """Dynamically import all plugin modules from the plugins/ directory."""
        plugin_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugins")
        plugin_files = sorted(glob.glob(os.path.join(plugin_path, "**", "*.py"), recursive=True))

        loaded = 0
        for filepath in plugin_files:
            if os.path.basename(filepath).startswith("_"):
                continue
            module_name = (
                filepath.replace(os.path.dirname(os.path.dirname(__file__)) + os.sep, "")
                .replace(os.sep, ".")
                .replace(".py", "")
            )
            try:
                importlib.import_module(module_name)
                log.debug(f"   ✔ Loaded plugin: {module_name}")
                loaded += 1
            except Exception as e:
                log.error(f"   ✘ Failed to load {module_name}: {e}", exc_info=True)

        log.info(f"📦 {loaded} plugins loaded.")

    # ── Helpers ───────────────────────────────────────────────────────────

    def get_assistant(self, chat_id: int) -> Client:
        """Round-robin assistant selection by chat_id."""
        return self.assistants[abs(chat_id) % len(self.assistants)]

    async def stop(self):
        """Gracefully stop all clients."""
        for assistant in self.assistants:
            try:
                await assistant.stop()
            except Exception:
                pass
        if self.bot:
            await self.bot.stop()
        if self.db:
            await self.db.close()
        log.info("🛑 TuneBot stopped.")


# Singleton instance
tunebot = TuneBot()

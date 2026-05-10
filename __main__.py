"""
TuneBot — A Production-Grade Telegram Music Bot
Built with Pyrogram + PyTgCalls + MongoDB
"""

import asyncio
import sys
import os

# Ensure Python 3.12+
if sys.version_info < (3, 12):
    print("❌ Python 3.12 or higher is required.")
    sys.exit(1)

from core.bot import TuneBot
from config.config import Config
from helpers.logger import LOGGER


async def main():
    LOGGER(__name__).info("🎵 Starting TuneBot...")

    # Validate environment
    Config.validate()

    bot = TuneBot()
    await bot.start()

    LOGGER(__name__).info("✅ TuneBot is now running!")
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        LOGGER(__name__).info("🛑 TuneBot stopped by user.")
    except Exception as e:
        LOGGER(__name__).critical(f"💥 Fatal error: {e}", exc_info=True)
        sys.exit(1)

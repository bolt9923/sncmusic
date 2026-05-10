"""
TuneBot — Stable Production Version (Fixed)
"""

import asyncio
import sys

# FIX: match Heroku Python 3.11
if sys.version_info < (3, 10):
    print("❌ Python 3.10+ required")
    sys.exit(1)

from core.bot import TuneBot
from config.config import Config
from helpers.logger import LOGGER


async def main():
    LOGGER(__name__).info("🎵 Starting TuneBot...")

    Config.validate()

    bot = TuneBot()
    await bot.start()

    LOGGER(__name__).info("✅ Bot Running")

    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        LOGGER(__name__).critical(f"Crash: {e}", exc_info=True)
        sys.exit(1)

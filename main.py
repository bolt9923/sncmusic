"""
TuneBot / SNCMusic - Production Entry File
Stable Heroku + Render Compatible Version
"""

import asyncio
import sys

from core.bot import TuneBot
from config.config import Config
from helpers.logger import LOGGER

log = LOGGER(__name__)


# ─────────────────────────────────────────────
# PYTHON VERSION CHECK (SAFE)
# ─────────────────────────────────────────────
if sys.version_info < (3, 10):
    print("❌ Python 3.10+ required")
    sys.exit(1)


# ─────────────────────────────────────────────
# MAIN START FUNCTION
# ─────────────────────────────────────────────
async def main():
    try:
        log.info("🎵 Starting TuneBot...")

        # Validate config (API_ID, BOT_TOKEN, etc.)
        Config.validate()

        # Start bot
        bot = TuneBot()
        await bot.start()

        log.info("✅ TuneBot is ONLINE")

        # Keep alive (VERY IMPORTANT for Heroku worker)
        await asyncio.Event().wait()

    except Exception as e:
        log.critical(f"💥 Fatal startup error: {e}", exc_info=True)
        sys.exit(1)


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("🛑 Bot stopped manually")
    except Exception as e:
        log.critical(f"💥 Crash: {e}", exc_info=True)
        sys.exit(1)

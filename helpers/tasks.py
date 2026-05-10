"""
helpers/tasks.py — Background tasks:
  • Periodic temp file cleanup
  • Auto-restart on crash (watchdog)
"""

import asyncio
import os
import sys

from helpers.downloader import Downloader
from helpers.logger import LOGGER

log = LOGGER(__name__)


async def cleanup_downloads_task(interval_seconds: int = 3600):
    """
    Runs every *interval_seconds* and deletes temp files older than 1 hour.
    """
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            Downloader.cleanup_old_files(max_age_seconds=3600)
            log.debug("🗑  Periodic temp file cleanup complete.")
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.warning(f"Cleanup task error: {e}")


async def watchdog_task(coroutine_factory, restart_delay: int = 5):
    """
    Runs *coroutine_factory()* and restarts it if it crashes.
    Used to keep the bot alive through transient errors.

    Example usage:
        asyncio.create_task(watchdog_task(lambda: main()))
    """
    while True:
        try:
            await coroutine_factory()
        except (KeyboardInterrupt, SystemExit):
            break
        except Exception as e:
            log.critical(f"💥 Bot crashed: {e}. Restarting in {restart_delay}s…", exc_info=True)
            await asyncio.sleep(restart_delay)


def start_background_tasks():
    """Schedule all background tasks. Call after event loop is running."""
    loop = asyncio.get_event_loop()
    loop.create_task(cleanup_downloads_task())
    log.info("🔧 Background tasks started.")

"""
Configuration — Environment variable loader and validator
"""

import os
import sys
from typing import List


class Config:
    # ── Telegram Credentials ──────────────────────────────────────────────
    API_ID: int = int(os.environ.get("API_ID", 0))
    API_HASH: str = os.environ.get("API_HASH", "")
    BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "")

    # ── Assistant Accounts (Userbot sessions for VC) ───────────────────────
    # Comma-separated Pyrogram string sessions
    STRING_SESSIONS: List[str] = [
        s.strip()
        for s in os.environ.get("STRING_SESSIONS", "").split(",")
        if s.strip()
    ]

    # ── Database ──────────────────────────────────────────────────────────
    MONGO_DB_URI: str = os.environ.get("MONGO_DB_URI", "")
    DATABASE_NAME: str = os.environ.get("DATABASE_NAME", "TuneBot")

    # ── Owner & Admins ────────────────────────────────────────────────────
    OWNER_ID: int = int(os.environ.get("OWNER_ID", 0))
    # Comma-separated list of additional sudo user IDs
    SUDO_USERS: List[int] = [
        int(x.strip())
        for x in os.environ.get("SUDO_USERS", "").split(",")
        if x.strip().isdigit()
    ]

    # ── Logger Group ─────────────────────────────────────────────────────
    LOGGER_ID: int = int(os.environ.get("LOGGER_ID", 0))

    # ── Force Subscribe ───────────────────────────────────────────────────
    # Set channel username (without @) or channel ID; leave empty to disable
    FORCE_SUB_CHANNEL: str = os.environ.get("FORCE_SUB_CHANNEL", "")

    # ── Spotify ───────────────────────────────────────────────────────────
    SPOTIFY_CLIENT_ID: str = os.environ.get("SPOTIFY_CLIENT_ID", "")
    SPOTIFY_CLIENT_SECRET: str = os.environ.get("SPOTIFY_CLIENT_SECRET", "")

    # ── Genius Lyrics ────────────────────────────────────────────────────
    GENIUS_API_TOKEN: str = os.environ.get("GENIUS_API_TOKEN", "")

    # ── Playback Settings ─────────────────────────────────────────────────
    DURATION_LIMIT_MIN: int = int(os.environ.get("DURATION_LIMIT_MIN", 180))  # 3 hours
    QUEUE_LIMIT: int = int(os.environ.get("QUEUE_LIMIT", 100))
    DEFAULT_VOLUME: int = int(os.environ.get("DEFAULT_VOLUME", 100))

    # ── Bot Appearance ───────────────────────────────────────────────────
    BOT_NAME: str = os.environ.get("BOT_NAME", "TuneBot")
    SUPPORT_CHAT: str = os.environ.get("SUPPORT_CHAT", "")
    BOT_USERNAME: str = os.environ.get("BOT_USERNAME", "")

    # ── 24/7 Mode Default ─────────────────────────────────────────────────
    ALWAYS_ON_DEFAULT: bool = os.environ.get("ALWAYS_ON_DEFAULT", "False").lower() == "true"

    # ── Anti-Spam ─────────────────────────────────────────────────────────
    # Cooldown in seconds between commands per user
    COMMAND_COOLDOWN: int = int(os.environ.get("COMMAND_COOLDOWN", 3))

    # ── Temp/Cache ───────────────────────────────────────────────────────
    DOWNLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "downloads")
    CACHE_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")

    # ── Proxy (optional) ─────────────────────────────────────────────────
    PROXIES: str = os.environ.get("PROXIES", "")

    @classmethod
    def validate(cls):
        """Validate required environment variables on startup."""
        errors = []

        if not cls.API_ID:
            errors.append("API_ID is not set or invalid.")
        if not cls.API_HASH:
            errors.append("API_HASH is not set.")
        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN is not set.")
        if not cls.MONGO_DB_URI:
            errors.append("MONGO_DB_URI is not set.")
        if not cls.STRING_SESSIONS:
            errors.append(
                "STRING_SESSIONS is not set. At least one assistant session is required."
            )
        if not cls.OWNER_ID:
            errors.append("OWNER_ID is not set.")

        if errors:
            print("\n❌  Configuration Errors:")
            for e in errors:
                print(f"   • {e}")
            print("\n👉  Please fill in your .env file. See .env.example for reference.\n")
            sys.exit(1)

        # Ensure directories exist
        os.makedirs(cls.DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(cls.CACHE_DIR, exist_ok=True)
        os.makedirs("logs", exist_ok=True)

    @classmethod
    def is_sudo(cls, user_id: int) -> bool:
        return user_id == cls.OWNER_ID or user_id in cls.SUDO_USERS

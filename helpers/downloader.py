"""
helpers/downloader.py — Audio downloader backed by yt-dlp
Handles YouTube, direct URLs, and Spotify (via search fallback).
"""

import asyncio
import os
import re
import uuid
from typing import Optional, Tuple

import yt_dlp

from config.config import Config
from helpers.logger import LOGGER

log = LOGGER(__name__)

# ── yt-dlp base options ───────────────────────────────────────────────────────

YDL_OPTS_AUDIO = {
    "format": "bestaudio[ext=m4a]/bestaudio/best",
    "outtmpl": os.path.join(Config.DOWNLOAD_DIR, "%(id)s.%(ext)s"),
    "writethumbnail": False,
    "quiet": True,
    "no_warnings": True,
    "extract_flat": False,
    "nocheckcertificate": True,
    "geo_bypass": True,
    "postprocessors": [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }
    ],
    "postprocessor_args": ["-ar", "48000"],
}

YDL_OPTS_INFO = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": False,
    "nocheckcertificate": True,
    "geo_bypass": True,
    "skip_download": True,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_url(text: str) -> bool:
    return re.match(r"https?://", text) is not None


def _is_youtube_url(text: str) -> bool:
    return any(x in text for x in ("youtube.com/watch", "youtu.be/", "youtube.com/playlist"))


def _is_playlist(text: str) -> bool:
    return "list=" in text or "/playlist" in text


# ── Main downloader class ─────────────────────────────────────────────────────


class Downloader:
    """Async wrapper around yt-dlp for audio extraction."""

    def __init__(self):
        self._loop = asyncio.get_event_loop

    # ── Public API ────────────────────────────────────────────────────────

    async def get_info(self, query: str) -> Optional[dict]:
        """
        Resolve a search query or URL to track metadata dict.
        Returns None on failure.
        """
        search_url = query if _is_url(query) else f"ytsearch:{query}"
        return await asyncio.to_thread(self._extract_info, search_url)

    async def get_playlist_info(self, url: str) -> Optional[list]:
        """Return list of track info dicts from a YouTube playlist URL."""
        opts = {**YDL_OPTS_INFO, "extract_flat": "in_playlist"}
        return await asyncio.to_thread(self._extract_playlist, url, opts)

    async def download(self, url: str) -> Tuple[Optional[str], Optional[dict]]:
        """
        Download best audio from *url*.
        Returns (file_path, info_dict) or (None, None) on failure.
        """
        try:
            info = await asyncio.to_thread(self._download_audio, url)
            if not info:
                return None, None
            # yt-dlp postprocessor outputs .mp3
            raw_path = os.path.join(Config.DOWNLOAD_DIR, f"{info['id']}.mp3")
            if not os.path.exists(raw_path):
                # Try any extension yt-dlp may have chosen
                for fname in os.listdir(Config.DOWNLOAD_DIR):
                    if fname.startswith(info["id"]):
                        raw_path = os.path.join(Config.DOWNLOAD_DIR, fname)
                        break
                else:
                    log.error(f"Downloaded file not found for {info['id']}")
                    return None, info
            return raw_path, info
        except yt_dlp.utils.DownloadError as e:
            error_str = str(e)
            if "Requested format is not available" in error_str:
                log.warning(f"Format unavailable for {url}, retrying with fallback…")
                return await self._fallback_download(url)
            log.error(f"yt-dlp download error: {e}")
            return None, None
        except Exception as e:
            log.error(f"Unexpected download error: {e}", exc_info=True)
            return None, None

    # ── Search ────────────────────────────────────────────────────────────

    async def search_youtube(self, query: str, limit: int = 5) -> list:
        """Return up to *limit* YouTube search results."""
        opts = {**YDL_OPTS_INFO, "default_search": f"ytsearch{limit}"}
        url = f"ytsearch{limit}:{query}"
        results = await asyncio.to_thread(self._extract_info_list, url, opts)
        return results or []

    # ── Private sync helpers (run in thread) ──────────────────────────────

    def _extract_info(self, url: str) -> Optional[dict]:
        with yt_dlp.YoutubeDL(YDL_OPTS_INFO) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                # ytsearch returns a list; grab first entry
                if info and "entries" in info:
                    return info["entries"][0] if info["entries"] else None
                return info
            except Exception as e:
                log.error(f"_extract_info error: {e}")
                return None

    def _extract_info_list(self, url: str, opts: dict) -> list:
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                if info and "entries" in info:
                    return list(info["entries"])
                return [info] if info else []
            except Exception as e:
                log.error(f"_extract_info_list error: {e}")
                return []

    def _extract_playlist(self, url: str, opts: dict) -> Optional[list]:
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                if info and "entries" in info:
                    return list(info["entries"])
                return None
            except Exception as e:
                log.error(f"_extract_playlist error: {e}")
                return None

    def _download_audio(self, url: str) -> Optional[dict]:
        with yt_dlp.YoutubeDL(YDL_OPTS_AUDIO) as ydl:
            info = ydl.extract_info(url, download=True)
            if info and "entries" in info:
                return info["entries"][0] if info["entries"] else None
            return info

    async def _fallback_download(self, url: str) -> Tuple[Optional[str], Optional[dict]]:
        """Retry with a more permissive format selection."""
        fallback_opts = {
            **YDL_OPTS_AUDIO,
            "format": "bestaudio/best",
        }
        try:
            info = await asyncio.to_thread(self._download_with_opts, url, fallback_opts)
            if not info:
                return None, None
            raw_path = os.path.join(Config.DOWNLOAD_DIR, f"{info['id']}.mp3")
            if not os.path.exists(raw_path):
                for fname in os.listdir(Config.DOWNLOAD_DIR):
                    if fname.startswith(info["id"]):
                        raw_path = os.path.join(Config.DOWNLOAD_DIR, fname)
                        break
                else:
                    return None, info
            return raw_path, info
        except Exception as e:
            log.error(f"Fallback download error: {e}")
            return None, None

    def _download_with_opts(self, url: str, opts: dict) -> Optional[dict]:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info and "entries" in info:
                return info["entries"][0] if info["entries"] else None
            return info

    # ── Cleanup ───────────────────────────────────────────────────────────

    @staticmethod
    def cleanup_file(path: Optional[str]):
        """Delete a downloaded file safely."""
        if path and os.path.exists(path):
            try:
                os.remove(path)
                log.debug(f"🗑  Deleted temp file: {path}")
            except Exception as e:
                log.warning(f"Could not delete {path}: {e}")

    @staticmethod
    def cleanup_old_files(max_age_seconds: int = 3600):
        """Remove downloaded files older than *max_age_seconds*."""
        import time
        now = time.time()
        for fname in os.listdir(Config.DOWNLOAD_DIR):
            fpath = os.path.join(Config.DOWNLOAD_DIR, fname)
            try:
                if os.path.isfile(fpath) and (now - os.path.getmtime(fpath)) > max_age_seconds:
                    os.remove(fpath)
            except Exception:
                pass


# Singleton
downloader = Downloader()

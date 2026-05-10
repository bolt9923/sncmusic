"""
helpers/spotify.py — Spotify track / playlist resolver
Converts Spotify URLs → search queries for yt-dlp.
"""

import re
from typing import Optional, List, Dict

from helpers.logger import LOGGER

log = LOGGER(__name__)

try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
    SPOTIPY_AVAILABLE = True
except ImportError:
    SPOTIPY_AVAILABLE = False

_sp = None


def _get_client():
    global _sp
    if _sp:
        return _sp
    from config.config import Config
    if not (Config.SPOTIFY_CLIENT_ID and Config.SPOTIFY_CLIENT_SECRET):
        return None
    try:
        auth = SpotifyClientCredentials(
            client_id=Config.SPOTIFY_CLIENT_ID,
            client_secret=Config.SPOTIFY_CLIENT_SECRET,
        )
        _sp = spotipy.Spotify(auth_manager=auth)
        return _sp
    except Exception as e:
        log.warning(f"Spotify init error: {e}")
        return None


def is_spotify_url(text: str) -> bool:
    return "open.spotify.com" in text


def spotify_url_type(url: str) -> Optional[str]:
    """Return 'track', 'playlist', 'album', or None."""
    m = re.search(r"spotify\.com/(track|playlist|album)/", url)
    return m.group(1) if m else None


def _extract_id(url: str) -> Optional[str]:
    m = re.search(r"spotify\.com/(?:track|playlist|album)/([A-Za-z0-9]+)", url)
    return m.group(1) if m else None


async def resolve_spotify(url: str) -> List[Dict]:
    """
    Resolve a Spotify URL to a list of dicts with keys:
      title, artists, duration_ms, search_query
    """
    if not SPOTIPY_AVAILABLE:
        log.warning("spotipy is not installed. Spotify support disabled.")
        return []

    sp = _get_client()
    if not sp:
        return []

    url_type = spotify_url_type(url)
    sp_id = _extract_id(url)
    if not sp_id:
        return []

    try:
        if url_type == "track":
            return [_parse_track(sp.track(sp_id))]

        elif url_type == "album":
            album = sp.album(sp_id)
            tracks = []
            for item in album["tracks"]["items"]:
                tracks.append(_parse_track_simple(item, album))
            return tracks

        elif url_type == "playlist":
            results = sp.playlist_tracks(sp_id)
            tracks = []
            while results:
                for item in results["items"]:
                    t = item.get("track")
                    if t:
                        tracks.append(_parse_track(t))
                if results["next"]:
                    results = sp.next(results)
                else:
                    break
            return tracks
    except Exception as e:
        log.error(f"Spotify resolve error: {e}")
        return []

    return []


def _parse_track(track: dict) -> dict:
    title = track.get("name", "Unknown")
    artists = ", ".join(a["name"] for a in track.get("artists", []))
    duration_ms = track.get("duration_ms", 0)
    thumb = None
    images = track.get("album", {}).get("images", [])
    if images:
        thumb = images[0]["url"]
    return {
        "title": title,
        "artists": artists,
        "duration_ms": duration_ms,
        "duration": duration_ms // 1000,
        "thumbnail": thumb,
        "search_query": f"{title} {artists}",
    }


def _parse_track_simple(item: dict, album: dict) -> dict:
    title = item.get("name", "Unknown")
    artists = ", ".join(a["name"] for a in item.get("artists", []))
    duration_ms = item.get("duration_ms", 0)
    thumb = None
    images = album.get("images", [])
    if images:
        thumb = images[0]["url"]
    return {
        "title": title,
        "artists": artists,
        "duration_ms": duration_ms,
        "duration": duration_ms // 1000,
        "thumbnail": thumb,
        "search_query": f"{title} {artists}",
    }

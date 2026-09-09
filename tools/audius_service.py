"""
Audius Streaming Service for VW California Trip Recaps.

This module integrates with the decentralized Audius music protocol
(https://audius.co) to search, stream, and cache indie travel soundtracks.
It provides mood-based presets tailored for vanlife, full-text music search,
MP3 caching for FFmpeg video multiplexing, and graceful offline fallback.
"""

import os
import time
import urllib.parse
from typing import Any, Dict, List, Optional
import requests

# Application identifier sent with Audius API requests
APP_NAME = "VWCaliforniaTripPlanner"

# List of healthy Audius Discovery Nodes (used in round-robin / failover)
DEFAULT_DISCOVERY_HOSTS = [
    "https://discoveryprovider.audius.co",
    "https://audius-discovery-1.cultur3stake.com",
    "https://audius-dp.amsterdam.creatorseed.com",
    "https://dn-usa.audius.metadata.fyi",
]

# Audio cache directory for downloaded MP3 streams
CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".tmp",
    "audio_cache",
)

# Preset travel moods and associated Audius search queries
MOOD_PRESETS: Dict[str, Dict[str, Any]] = {
    "roadtrip": {
        "label": "Roadtrip & Vanlife",
        "icon": "🚐",
        "query": "roadtrip chill",
        "genre": "Lo-Fi / Indie",
    },
    "lofi": {
        "label": "Lo-Fi Sunset",
        "icon": "🌅",
        "query": "lofi chill beats",
        "genre": "Lo-Fi",
    },
    "acoustic": {
        "label": "Acoustic Folk",
        "icon": "🎸",
        "query": "acoustic guitar travel",
        "genre": "Acoustic / Folk",
    },
    "nature": {
        "label": "Alpine & Nature",
        "icon": "🌲",
        "query": "ambient nature chill",
        "genre": "Ambient",
    },
    "summer": {
        "label": "Summer Breeze",
        "icon": "☀️",
        "query": "summer chill vibes",
        "genre": "Electronic / Chill",
    },
    "jazz": {
        "label": "Smooth Jazz",
        "icon": "🎷",
        "query": "smooth jazz chillout",
        "genre": "Jazz",
    },
}

# Offline procedural tracks built into the project
OFFLINE_TRACKS: List[Dict[str, Any]] = [
    {
        "id": "offline_vanlife_chill",
        "track_id": "vanlife_chill",
        "title": "Vanlife Chill",
        "artist": "VW California Studio",
        "duration": 38,
        "formatted_duration": "0:38",
        "genre": "Acoustic / Vanlife",
        "artwork_url": None,
        "stream_url": "/assets/audio/vanlife_chill.mp3",
        "source": "local",
    },
    {
        "id": "offline_acoustic_sunset",
        "track_id": "acoustic_sunset",
        "title": "Acoustic Sunset",
        "artist": "VW California Studio",
        "duration": 38,
        "formatted_duration": "0:38",
        "genre": "Acoustic Guitar",
        "artwork_url": None,
        "stream_url": "/assets/audio/acoustic_sunset.mp3",
        "source": "local",
    },
    {
        "id": "offline_coastal_breeze",
        "track_id": "coastal_breeze",
        "title": "Coastal Breeze",
        "artist": "VW California Studio",
        "duration": 38,
        "formatted_duration": "0:38",
        "genre": "Ambient Coast",
        "artwork_url": None,
        "stream_url": "/assets/audio/coastal_breeze.mp3",
        "source": "local",
    },
    {
        "id": "offline_alpine_acoustic",
        "track_id": "alpine_acoustic",
        "title": "Alpine Acoustic",
        "artist": "VW California Studio",
        "duration": 38,
        "formatted_duration": "0:38",
        "genre": "Alpine Folk",
        "artwork_url": None,
        "stream_url": "/assets/audio/alpine_acoustic.mp3",
        "source": "local",
    },
    {
        "id": "offline_jazz_trio",
        "track_id": "jazz_trio",
        "title": "Jazz Trio",
        "artist": "VW California Studio",
        "duration": 38,
        "formatted_duration": "0:38",
        "genre": "Jazz Rhodes",
        "artwork_url": None,
        "stream_url": "/assets/audio/jazz_trio.mp3",
        "source": "local",
    },
    {
        "id": "offline_folk_guitar",
        "track_id": "folk_guitar",
        "title": "Folk Guitar",
        "artist": "VW California Studio",
        "duration": 38,
        "formatted_duration": "0:38",
        "genre": "Folk Guitar",
        "artwork_url": None,
        "stream_url": "/assets/audio/folk_guitar.mp3",
        "source": "local",
    },
    {
        "id": "offline_reggae_sunshine",
        "track_id": "reggae_sunshine",
        "title": "Reggae Sunshine",
        "artist": "VW California Studio",
        "duration": 38,
        "formatted_duration": "0:38",
        "genre": "Dub / Reggae",
        "artwork_url": None,
        "stream_url": "/assets/audio/reggae_sunshine.mp3",
        "source": "local",
    },
    {
        "id": "offline_cinematic_orchestral",
        "track_id": "cinematic_orchestral",
        "title": "Cinematic Orchestral",
        "artist": "VW California Studio",
        "duration": 38,
        "formatted_duration": "0:38",
        "genre": "Cinematic",
        "artwork_url": None,
        "stream_url": "/assets/audio/cinematic_orchestral.mp3",
        "source": "local",
    },
    {
        "id": "offline_electronic_lofi",
        "track_id": "electronic_lofi",
        "title": "Electronic Lo-Fi",
        "artist": "VW California Studio",
        "duration": 38,
        "formatted_duration": "0:38",
        "genre": "Lo-Fi Beats",
        "artwork_url": None,
        "stream_url": "/assets/audio/electronic_lofi.mp3",
        "source": "local",
    },
]

# In-memory cache for healthy host and recent queries
_ACTIVE_HOST: Optional[str] = None
_LAST_HOST_CHECK: float = 0.0
_HOST_CHECK_TTL: float = 300.0  # 5 minutes


def get_active_host() -> str:
    """
    Return a healthy Audius discovery host with caching.

    Checks known discovery nodes and returns the first responding one.
    Defaults to https://discoveryprovider.audius.co if all checks fail.
    """
    global _ACTIVE_HOST, _LAST_HOST_CHECK
    now = time.time()
    if _ACTIVE_HOST and (now - _LAST_HOST_CHECK < _HOST_CHECK_TTL):
        return _ACTIVE_HOST

    headers = {
        "User-Agent": f"VWCaliforniaApp/1.0 (+{APP_NAME})",
        "Accept": "application/json",
    }
    for host in DEFAULT_DISCOVERY_HOSTS:
        try:
            url = f"{host}/v1/tracks/trending?app_name={APP_NAME}&limit=1"
            resp = requests.get(url, headers=headers, timeout=3.5)
            if resp.status_code == 200:
                _ACTIVE_HOST = host
                _LAST_HOST_CHECK = now
                return host
        except Exception:
            continue

    # Fallback to the primary discovery provider
    _ACTIVE_HOST = DEFAULT_DISCOVERY_HOSTS[0]
    _LAST_HOST_CHECK = now
    return _ACTIVE_HOST


def _format_seconds(seconds: int) -> str:
    """Format duration in seconds to MM:SS string."""
    mins = seconds // 60
    secs = seconds % 60
    return f"{mins}:{secs:02d}"


def _format_track(item: Dict[str, Any], host: str) -> Dict[str, Any]:
    """
    Format raw Audius track JSON into normalized VW California model.
    """
    track_id = item.get("id")
    title = item.get("title", "Untitled Track")
    user = item.get("user") or {}
    artist = user.get("name") or user.get("handle") or "Unknown Artist"
    duration = int(item.get("duration", 0))

    artwork = item.get("artwork") or {}
    artwork_url = (
        artwork.get("480x480")
        or artwork.get("150x150")
        or artwork.get("1000x1000")
    )

    stream_url = f"{host}/v1/tracks/{track_id}/stream?app_name={APP_NAME}"

    return {
        "id": f"audius:{track_id}",
        "track_id": track_id,
        "title": title,
        "artist": artist,
        "duration": duration,
        "formatted_duration": _format_seconds(duration),
        "genre": item.get("genre") or "Indie",
        "artwork_url": artwork_url,
        "stream_url": stream_url,
        "source": "audius",
    }


def search_tracks(query: str, limit: int = 12) -> List[Dict[str, Any]]:
    """
    Search tracks on Audius by title, genre, or keyword.

    Args:
        query: Search string (e.g. 'lofi roadtrip').
        limit: Maximum number of tracks to return (default 12).

    Returns:
        List of formatted track dictionaries.
    """
    query = (query or "").strip()
    if not query:
        return []

    host = get_active_host()
    encoded = urllib.parse.quote_plus(query)
    url = f"{host}/v1/tracks/search?query={encoded}&app_name={APP_NAME}"

    headers = {
        "User-Agent": f"VWCaliforniaApp/1.0 (+{APP_NAME})",
        "Accept": "application/json",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=8.0)
        if resp.status_code != 200:
            return []

        data = resp.json().get("data", [])
        formatted = []
        for item in data:
            if not isinstance(item, dict):
                continue
            # Filter out tracks that are deleted or unlisted
            if item.get("is_delete") or item.get("is_unlisted"):
                continue
            dur = item.get("duration", 0)
            # Only include tracks between 20s and 600s
            if dur < 20 or dur > 600:
                continue
            formatted.append(_format_track(item, host))
            if len(formatted) >= limit:
                break
        return formatted
    except Exception as e:
        print(f"  ⚠️ Audius search error for '{query}': {e}")
        return []


def get_mood_tracks(mood: str = "roadtrip", limit: int = 8) -> Dict[str, Any]:
    """
    Retrieve curated tracks for a given VW California travel mood.

    Args:
        mood: Key from MOOD_PRESETS or 'offline'.
        limit: Max tracks to return.

    Returns:
        Dictionary with mood metadata and tracks list.
    """
    if mood == "offline":
        return {
            "mood": "offline",
            "label": "Dźwięki Offline (Proceduralne)",
            "icon": "📁",
            "genre": "Offline Local",
            "tracks": OFFLINE_TRACKS[:limit],
        }

    preset = MOOD_PRESETS.get(mood, MOOD_PRESETS["roadtrip"])
    query = preset["query"]

    tracks = search_tracks(query=query, limit=limit)

    # Fallback to offline tracks if network search yielded zero results
    if not tracks:
        print(f"  ℹ️ Falling back to offline tracks for mood '{mood}'")
        tracks = OFFLINE_TRACKS[:limit]

    return {
        "mood": mood,
        "label": preset["label"],
        "icon": preset["icon"],
        "genre": preset["genre"],
        "tracks": tracks,
    }


def download_and_cache_track(track_identifier: str, timeout: int = 25) -> Optional[str]:
    """
    Download and cache an Audius MP3 track locally for FFmpeg video processing.

    Args:
        track_identifier: Track ID or 'audius:<id>' string, or local track name.
        timeout: Maximum time in seconds to wait for download.

    Returns:
        Absolute filesystem path to the cached MP3 file, or None if failed.
    """
    if not track_identifier or track_identifier == "none":
        return None

    # Handle local offline tracks
    clean_id = track_identifier.replace("audius:", "").strip()
    if clean_id.startswith("offline_"):
        clean_id = clean_id.replace("offline_", "")

    # Check if this matches one of our local project tracks
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_candidates = [
        os.path.join(project_root, "frontend", "assets", "audio", f"{clean_id}.mp3"),
        os.path.join(project_root, "tools", "assets", "audio", f"{clean_id}.mp3"),
        os.path.join(project_root, "frontend", "assets", "audio", clean_id),
    ]
    for cand in local_candidates:
        if os.path.exists(cand):
            return cand

    # If it's an Audius track, cache in .tmp/audio_cache/
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, f"audius_{clean_id}.mp3")

    # If already cached and valid (> 100 KB), reuse immediately
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 100_000:
        return cache_path

    # Stream download from Audius
    host = get_active_host()
    stream_url = f"{host}/v1/tracks/{clean_id}/stream?app_name={APP_NAME}"
    temp_path = f"{cache_path}.part_{int(time.time())}"

    headers = {
        "User-Agent": f"VWCaliforniaApp/1.0 (+{APP_NAME})",
    }

    try:
        resp = requests.get(
            stream_url,
            headers=headers,
            allow_redirects=True,
            stream=True,
            timeout=timeout,
        )
        if resp.status_code != 200:
            print(f"  ⚠️ Audius stream status {resp.status_code} for {clean_id}")
            return None

        total_bytes = 0
        with open(temp_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    total_bytes += len(chunk)

        # Basic validity check (at least 50 KB)
        if total_bytes < 50_000:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return None

        # Atomic rename to target file
        os.replace(temp_path, cache_path)
        return cache_path

    except Exception as e:
        print(f"  ⚠️ Error downloading Audius track {clean_id}: {e}")
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        return None

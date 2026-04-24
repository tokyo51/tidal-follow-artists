"""Shared Tidal session / API logic used by all subcommands."""

import json
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import tidalapi
import requests

CONFIG_DIR = Path.home() / ".tidal-follow"
SESSIONS_DIR = CONFIG_DIR / "sessions"
WATCH_DIR = CONFIG_DIR / "watch"
DEFAULT_PROFILE = "default"
REQUEST_DELAY = 0.25

CONFIG_DIR.mkdir(exist_ok=True)
SESSIONS_DIR.mkdir(exist_ok=True)
WATCH_DIR.mkdir(exist_ok=True)

# Back-compat: migrate old single-session file if present
_LEGACY = Path.home() / ".tidal-follow-session.json"
_LEGACY_TARGET = SESSIONS_DIR / f"{DEFAULT_PROFILE}.json"
if _LEGACY.exists() and not _LEGACY_TARGET.exists():
    try:
        _LEGACY_TARGET.write_text(_LEGACY.read_text())
    except Exception:
        pass


# ─── Profile management ───────────────────────────────────────

def session_path(profile: str) -> Path:
    return SESSIONS_DIR / f"{profile}.json"

def list_profiles() -> list[str]:
    return sorted(p.stem for p in SESSIONS_DIR.glob("*.json"))

def delete_profile(profile: str) -> bool:
    p = session_path(profile)
    if p.exists():
        p.unlink()
        return True
    return False


# ─── Login ────────────────────────────────────────────────────

@dataclass
class LoginInit:
    url: str
    future: object  # concurrent.futures.Future


def restore_session(session: tidalapi.Session, profile: str) -> bool:
    sp = session_path(profile)
    if not sp.exists():
        return False
    try:
        data = json.loads(sp.read_text())
        session.load_oauth_session(
            data["token_type"], data["access_token"],
            data.get("refresh_token"), data.get("expiry_time"),
        )
        if session.check_login():
            return True
    except Exception:
        pass
    return False


def begin_login(session: tidalapi.Session) -> LoginInit:
    login_obj, future = session.login_oauth()
    url = f"https://{login_obj.verification_uri_complete}"
    try: webbrowser.open(url)
    except Exception: pass
    return LoginInit(url=url, future=future)


def persist_session(session: tidalapi.Session, profile: str) -> None:
    session_path(profile).write_text(json.dumps({
        "token_type": session.token_type,
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expiry_time": session.expiry_time.isoformat() if session.expiry_time else None,
    }, default=str))


# ─── Playlists & artists ──────────────────────────────────────

def all_playlists(session: tidalapi.Session):
    user = session.user
    playlists = list(user.playlists()) + list(user.favorites.playlists())
    seen, unique = set(), []
    for p in playlists:
        if p.id not in seen:
            seen.add(p.id); unique.append(p)
    return unique


def playlist_by_id(session: tidalapi.Session, pid: str):
    for p in all_playlists(session):
        if str(p.id) == str(pid):
            return p
    return None


def collect_artists(playlists, on_playlist=None) -> dict:
    """Return {artist_id: (name, track_count)}."""
    artists: dict = {}
    for p in playlists:
        tracks = p.tracks()
        if on_playlist:
            on_playlist(p, len(tracks))
        for t in tracks:
            for a in (t.artists or []):
                if not a.id: continue
                if a.id in artists:
                    name, cnt = artists[a.id]
                    artists[a.id] = (name, cnt + 1)
                else:
                    artists[a.id] = (a.name, 1)
    return artists


def followed_artist_ids(session: tidalapi.Session) -> set:
    try:
        return {a.id for a in session.user.favorites.artists()}
    except Exception:
        return set()


def follow_artist(session: tidalapi.Session, artist_id) -> bool:
    url = f"https://api.tidal.com/v1/users/{session.user.id}/favorites/artists"
    headers = {"Authorization": f"{session.token_type} {session.access_token}"}
    params = {"countryCode": session.country_code}
    data = {"artistIds": str(artist_id)}
    try:
        r = requests.post(url, headers=headers, params=params, data=data, timeout=15)
        return r.status_code in (200, 201)
    except requests.RequestException:
        return False


# ─── Watch-mode config ────────────────────────────────────────

def watch_config_path(profile: str) -> Path:
    return WATCH_DIR / f"{profile}.json"

def load_watch_config(profile: str) -> Optional[dict]:
    p = watch_config_path(profile)
    if not p.exists(): return None
    try: return json.loads(p.read_text())
    except Exception: return None

def save_watch_config(profile: str, data: dict) -> None:
    watch_config_path(profile).write_text(json.dumps(data, indent=2, default=str))

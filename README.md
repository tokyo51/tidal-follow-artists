# tidal-follow-artists

A small CLI tool that automatically follows every artist from your Tidal playlists — including featured and contributing artists — in one go.

```
  ████████╗██╗██████╗  █████╗ ██╗
  ╚══██╔══╝██║██╔══██╗██╔══██╗██║
     ██║   ██║██║  ██║███████║██║
     ██║   ██║██║  ██║██╔══██║██║
     ██║   ██║██████╔╝██║  ██║███████╗
     ╚═╝   ╚═╝╚═════╝ ╚═╝  ╚═╝╚══════╝
      ─── follow-artists tool ───
```

## Why

Tidal has no built-in way to mass-follow the artists of a playlist. If you've got a big "Liked Songs" or curated playlist and want to populate your followed-artists feed, doing it manually is painful. This script does it for you in seconds.

## Features

- OAuth login via Tidal's device flow (no password handling)
- **Single / Multiple / All** playlist modes
- Picks up **featured and contributing artists**, not just the primary one
- Skips artists you already follow
- Rate-limit friendly (configurable delay)
- Session cached locally so you only log in once
- Colorful Tidal-styled terminal UI with a live progress bar

## Requirements

- Python 3.10+
- A Tidal account (any tier that allows following artists)
- macOS / Linux / Windows

## Install

```bash
git clone https://github.com/<your-username>/tidal-follow-artists.git
cd tidal-follow-artists
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

```bash
python follow_artists.py
```

On macOS you can also just double-click `run.command`.

### First run

1. A URL like `https://link.tidal.com/ABC12` is printed and opened in your browser.
2. Log into Tidal (if not already) and click **Log In** to authorize.
3. The script caches the session in `~/.tidal-follow-session.json` — no login needed next time.

### Flow

1. Pick a mode: Single, Multiple, or All playlists
2. Pick the playlist(s) by number (supports ranges like `2-5,8`)
3. Confirm — the script collects all unique artists, skips ones you already follow, and follows the rest

Typical run for ~500 artists takes about a minute.

## Configuration

Edit the top of `follow_artists.py`:

```python
REQUEST_DELAY = 0.25  # seconds between follow requests
```

Lower it to go faster, raise it if you get rate-limited.

## How it works

- Authenticated access to playlists and favorites uses [`tidalapi`](https://github.com/tamland/python-tidal) (OAuth device flow).
- Following artists uses Tidal's internal API endpoint `POST /v1/users/{userId}/favorites/artists` with the OAuth access token — the same endpoint tidal.com uses.

Because the follow endpoint is Tidal's internal API (not the public developer API), it is technically undocumented and could change at any time. It currently works reliably.

## Troubleshooting

**"The device code you entered is wrong"**
You typed the code manually on `link.tidal.com/activate`. Instead, copy the full URL printed by the script (`link.tidal.com/XXXXX`) into your browser — the code is auto-filled.

**Follows fail / 401**
Delete `~/.tidal-follow-session.json` and log in again.

**Rate limiting**
Increase `REQUEST_DELAY`.

## Privacy

- No data leaves your machine except requests to Tidal's API.
- The session token is stored locally in your home directory.
- No analytics, no telemetry.

## Disclaimer

This is an unofficial tool, not affiliated with or endorsed by Tidal. Use at your own risk. Respect Tidal's Terms of Service.

## License

MIT — see [LICENSE](LICENSE).

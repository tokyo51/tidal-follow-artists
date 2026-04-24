<div align="center">

```
  ████████╗██╗██████╗  █████╗ ██╗
  ╚══██╔══╝██║██╔══██╗██╔══██╗██║
     ██║   ██║██║  ██║███████║██║
     ██║   ██║██║  ██║██╔══██║██║
     ██║   ██║██████╔╝██║  ██║███████╗
     ╚═╝   ╚═╝╚═════╝ ╚═╝  ╚═╝╚══════╝
```

### **tidal-follow-artists**

*Bulk-follow every artist from your Tidal playlists — features, collabs, contributors, all of them.*

![Python](https://img.shields.io/badge/python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-000000?style=flat-square)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey?style=flat-square)
![Tidal](https://img.shields.io/badge/Tidal-000000?style=flat-square&logo=tidal&logoColor=white)

</div>

---

## 🎧 Why

Tidal has no built-in "follow all artists in this playlist" button. If you curate a big "Liked Songs" playlist and want your followed-artists feed to actually reflect the music you listen to, doing it manually is hell — thousands of clicks. This tool does it in one run, and can keep doing it automatically as your playlists grow.

## ✨ Features

- 🔐 **OAuth device login** — no password handling
- 🎯 **Picks up everyone** — primary artists + featured + contributors
- 📚 **Modes** — Single / Multiple / All playlists / Dry-run preview
- 👁 **Watch mode** — daemon that auto-follows new artists as you add songs
- 👥 **Multi-account** — separate profiles for e.g. personal vs. shared accounts
- ⚡ **Skips** artists you already follow
- 🎨 **Gorgeous terminal UI** — gradient progress bars, spinners, live stats
- 💾 **Session cached per profile** — log in once, run forever
- 🚦 **Rate-limit friendly** — configurable delay

## 📸 Preview

```
  ████████╗██╗██████╗  █████╗ ██╗
  ╚══██╔══╝██║██╔══██╗██╔══██╗██║
     ██║   ██║██║  ██║███████║██║        follow-artists
     ██║   ██║██████╔╝██║  ██║███████╗

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FOLLOWING ARTISTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✓ Tame Impala                        ██████████░░░░░  214/312  68.6%
    ✓ 214  ✗ 0  ·  54.2s elapsed
```

## 🚀 Quick start

```bash
git clone https://github.com/<your-username>/tidal-follow-artists.git
cd tidal-follow-artists
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python follow_artists.py
```

On macOS you can also just **double-click `run.command`** in Finder.

## 📖 Commands

| Command | What it does |
|---|---|
| `python follow_artists.py` | Default — interactive bulk-follow (same as `run`) |
| `python follow_artists.py run` | Pick playlist(s), follow every artist in them |
| `python follow_artists.py watch` | Daemon — auto-follow new artists as playlists grow |
| `python follow_artists.py profiles` | List / manage saved Tidal accounts |

Every command accepts `--profile NAME` to target a specific account.

### First run

1. A URL like `https://link.tidal.com/ABC12` opens in your browser.
2. Log into Tidal and click **Log In** to authorize.
3. The session is cached — no login needed next time.

## 👁 Watch mode

Run the tool as a daemon that periodically checks your chosen playlists and follows any newly appearing artists — so your followed-artists feed always reflects what's in your playlists.

```bash
python follow_artists.py watch --interval 1800        # check every 30 min
python follow_artists.py watch --reset                # reconfigure watched playlists
```

**How it works:**

1. On first run you pick which playlists to watch.
2. The current artist set is stored as a **baseline** in `~/.tidal-follow/watch/<profile>.json`.
3. Every `--interval` seconds the tool re-fetches those playlists, diffs against the baseline, follows any new artists, then updates the baseline.

Leave it running in a terminal tab, screen/tmux session, or wrap it in a `launchd` plist (macOS) / systemd unit (Linux) to run on boot.

## 👥 Multi-account (profiles)

Use separate Tidal sessions for different accounts — e.g. your personal Tidal and a shared family one:

```bash
python follow_artists.py run --profile personal
python follow_artists.py run --profile family
python follow_artists.py profiles                     # list
python follow_artists.py profiles --delete family     # log out / remove
```

Profiles live in `~/.tidal-follow/sessions/<profile>.json`. Each has its own cached session and watch config, so you can even run `watch` for multiple accounts in parallel.

## 🔧 Configuration

Top of [`tidal_core.py`](tidal_core.py):

```python
REQUEST_DELAY = 0.25  # seconds between follow requests
```

Lower to go faster. Raise if you hit rate limits.

## 🧠 How it works

- **Reads playlists + favorites** via [`tidalapi`](https://github.com/tamland/python-tidal) (OAuth device flow).
- **Follows artists** via Tidal's internal endpoint `POST /v1/users/{userId}/favorites/artists` using the OAuth access token — the same endpoint the Tidal web app uses.

Because the follow endpoint is Tidal's internal API (not the public developer API), it is undocumented and could change. It currently works reliably.

## 📂 Files on disk

```
~/.tidal-follow/
  sessions/
    default.json          # cached OAuth session per profile
    personal.json
  watch/
    default.json          # watched playlists + baseline per profile
```

## 🛠 Troubleshooting

<details>
<summary><b>"The device code you entered is wrong"</b></summary>

You typed the code manually on `link.tidal.com/activate`. Instead, copy the full URL printed by the script (`link.tidal.com/XXXXX`) into your browser — the code is auto-filled.
</details>

<details>
<summary><b>Follows fail / 401</b></summary>

Session expired. Delete the profile and log in again:
```bash
python follow_artists.py profiles --delete default
python follow_artists.py run
```
</details>

<details>
<summary><b>Rate limiting</b></summary>

Increase `REQUEST_DELAY` in `tidal_core.py`.
</details>

## 🗺 Roadmap

- [ ] `--unfollow` mode (bulk-unfollow artists from a playlist)
- [ ] `--min-tracks N` filter (only follow artists with ≥ N tracks in selection)
- [ ] `--export artists.csv` / `--export artists.json`
- [ ] Include "Liked Albums" as a virtual playlist
- [ ] Stats-only mode (read-only insights)
- [ ] Docker image
- [ ] Cross-service mirror (Spotify → Tidal follow parity)

Suggestions and PRs welcome.

## 🔒 Privacy

- No data leaves your machine except requests to Tidal's API.
- Session tokens stored only in your home directory.
- No analytics, no telemetry, no third-party calls.

## ⚠️ Disclaimer

Unofficial tool, not affiliated with or endorsed by Tidal. Uses an undocumented internal endpoint. Use at your own risk and respect Tidal's Terms of Service.

## 📄 License

[MIT](LICENSE) — do whatever, no warranty.

---

<div align="center">
<sub>Made because clicking follow 1000 times is not a personality trait.</sub>
</div>

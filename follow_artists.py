#!/usr/bin/env python3
"""
Tidal: Follow all artists from selected playlist(s), including featured/contributing artists.
"""

import json
import sys
import time
import webbrowser
from pathlib import Path

import tidalapi
import requests

SESSION_FILE = Path.home() / ".tidal-follow-session.json"
REQUEST_DELAY = 0.25

# ── ANSI colors (Tidal-ish: black bg, cyan/white accents) ──
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[38;5;51m"       # bright cyan (Tidal accent)
    BLUE = "\033[38;5;45m"
    WHITE = "\033[97m"
    GREY = "\033[38;5;244m"
    GREEN = "\033[38;5;46m"
    RED = "\033[38;5;203m"
    YELLOW = "\033[38;5;221m"
    MAGENTA = "\033[38;5;213m"
    BG_BLACK = "\033[40m"

BANNER = f"""{C.CYAN}{C.BOLD}
  ████████╗██╗██████╗  █████╗ ██╗
  ╚══██╔══╝██║██╔══██╗██╔══██╗██║
     ██║   ██║██║  ██║███████║██║
     ██║   ██║██║  ██║██╔══██║██║
     ██║   ██║██████╔╝██║  ██║███████╗
     ╚═╝   ╚═╝╚═════╝ ╚═╝  ╚═╝╚══════╝{C.RESET}
{C.GREY}      ─── follow-artists tool ───{C.RESET}
"""

def hr(char="─", color=C.GREY):
    print(f"{color}{char * 60}{C.RESET}")

def info(msg): print(f"{C.CYAN}ℹ{C.RESET}  {msg}")
def ok(msg):   print(f"{C.GREEN}✓{C.RESET}  {msg}")
def warn(msg): print(f"{C.YELLOW}⚠{C.RESET}  {msg}")
def err(msg):  print(f"{C.RED}✗{C.RESET}  {msg}")
def ask(msg):  return input(f"{C.MAGENTA}?{C.RESET}  {C.BOLD}{msg}{C.RESET} ")


def login(session: tidalapi.Session) -> None:
    if SESSION_FILE.exists():
        try:
            data = json.loads(SESSION_FILE.read_text())
            session.load_oauth_session(
                data["token_type"], data["access_token"],
                data.get("refresh_token"), data.get("expiry_time"),
            )
            if session.check_login():
                ok(f"Logged in as {C.BOLD}{session.user.id}{C.RESET} (cached session)")
                return
        except Exception:
            pass

    login_obj, future = session.login_oauth()
    url = f"https://{login_obj.verification_uri_complete}"
    print()
    hr("═", C.CYAN)
    print(f"  {C.BOLD}{C.CYAN}TIDAL LOGIN{C.RESET}")
    hr("═", C.CYAN)
    print(f"  Open this {C.BOLD}full URL{C.RESET} in your browser")
    print(f"  {C.DIM}(don't type the code on link.tidal.com/activate){C.RESET}\n")
    print(f"    {C.CYAN}{C.BOLD}{url}{C.RESET}\n")
    print(f"  Then click {C.BOLD}Log In{C.RESET} to confirm.")
    hr("═", C.CYAN)
    try: webbrowser.open(url)
    except Exception: pass
    info("Waiting for browser confirmation...")
    future.result()

    SESSION_FILE.write_text(json.dumps({
        "token_type": session.token_type,
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expiry_time": session.expiry_time.isoformat() if session.expiry_time else None,
    }, default=str))
    ok("Logged in. Session cached.")


def list_playlists(session: tidalapi.Session):
    user = session.user
    playlists = list(user.playlists()) + list(user.favorites.playlists())
    seen, unique = set(), []
    for p in playlists:
        if p.id not in seen:
            seen.add(p.id)
            unique.append(p)
    return unique


def choose_mode():
    print()
    hr()
    print(f"  {C.BOLD}{C.WHITE}MODE{C.RESET}")
    hr()
    print(f"  {C.CYAN}[1]{C.RESET} Single playlist")
    print(f"  {C.CYAN}[2]{C.RESET} Multiple playlists")
    print(f"  {C.CYAN}[3]{C.RESET} All playlists")
    while True:
        c = ask("Choose mode [1/2/3]:").strip()
        if c in ("1", "2", "3"): return c
        err("Invalid choice.")


def render_playlists(playlists):
    print()
    hr()
    print(f"  {C.BOLD}{C.WHITE}YOUR PLAYLISTS{C.RESET}  {C.GREY}({len(playlists)} total){C.RESET}")
    hr()
    for i, p in enumerate(playlists, 1):
        count = getattr(p, "num_tracks", "?")
        idx = f"{C.CYAN}[{i:>3}]{C.RESET}"
        name = f"{C.WHITE}{p.name}{C.RESET}"
        meta = f"{C.GREY}{count} tracks{C.RESET}"
        print(f"  {idx} {name}  {meta}")
    hr()


def select_playlists(playlists, mode):
    if mode == "3":
        return playlists
    if mode == "1":
        while True:
            c = ask(f"Pick playlist number [1-{len(playlists)}]:").strip()
            if c.isdigit() and 1 <= int(c) <= len(playlists):
                return [playlists[int(c) - 1]]
            err("Invalid choice.")
    # multi
    info("Enter numbers separated by commas (e.g. 1,3,7) or ranges (e.g. 2-5,8).")
    while True:
        raw = ask("Pick playlists:").strip()
        picked = set()
        try:
            for part in raw.split(","):
                part = part.strip()
                if "-" in part:
                    a, b = part.split("-")
                    picked.update(range(int(a), int(b) + 1))
                else:
                    picked.add(int(part))
            if not picked or any(i < 1 or i > len(playlists) for i in picked):
                raise ValueError
            return [playlists[i - 1] for i in sorted(picked)]
        except ValueError:
            err("Invalid input. Try again.")


def collect_artists(playlists) -> dict:
    artists = {}
    for p in playlists:
        tracks = p.tracks()
        info(f"Scanning {C.BOLD}{p.name}{C.RESET} {C.GREY}({len(tracks)} tracks){C.RESET}")
        for t in tracks:
            for a in (t.artists or []):
                if a.id and a.id not in artists:
                    artists[a.id] = a.name
    return artists


def get_already_followed(session):
    try:
        return {a.id for a in session.user.favorites.artists()}
    except Exception as e:
        warn(f"Could not fetch current follows: {e}")
        return set()


def follow_artist(session, artist_id) -> bool:
    url = f"https://api.tidal.com/v1/users/{session.user.id}/favorites/artists"
    headers = {"Authorization": f"{session.token_type} {session.access_token}"}
    params = {"countryCode": session.country_code}
    data = {"artistIds": str(artist_id)}
    try:
        r = requests.post(url, headers=headers, params=params, data=data, timeout=15)
        return r.status_code in (200, 201)
    except requests.RequestException:
        return False


def progress_bar(current, total, width=30):
    pct = current / total if total else 1
    filled = int(width * pct)
    bar = f"{C.CYAN}{'█' * filled}{C.GREY}{'░' * (width - filled)}{C.RESET}"
    return f"{bar} {C.BOLD}{current}/{total}{C.RESET} {C.GREY}({pct*100:.0f}%){C.RESET}"


def main():
    print(BANNER)
    session = tidalapi.Session()
    login(session)

    playlists = list_playlists(session)
    if not playlists:
        err("No playlists found."); sys.exit(1)

    mode = choose_mode()
    render_playlists(playlists)
    selected = select_playlists(playlists, mode)

    print()
    ok(f"Selected {C.BOLD}{len(selected)}{C.RESET} playlist(s):")
    for p in selected:
        print(f"   {C.CYAN}•{C.RESET} {p.name}")

    print()
    artists = collect_artists(selected)
    ok(f"Found {C.BOLD}{len(artists)}{C.RESET} unique artists (incl. features)")

    already = get_already_followed(session)
    to_follow = {aid: name for aid, name in artists.items() if aid not in already}
    info(f"Already following: {C.BOLD}{len(artists) - len(to_follow)}{C.RESET}  "
         f"• To follow: {C.BOLD}{C.GREEN}{len(to_follow)}{C.RESET}")

    if not to_follow:
        ok("Nothing to do."); return

    print()
    if ask(f"Follow {C.BOLD}{len(to_follow)}{C.RESET} artists? [y/N]:").strip().lower() != "y":
        warn("Aborted."); return

    print()
    hr("═", C.CYAN)
    print(f"  {C.BOLD}{C.CYAN}FOLLOWING ARTISTS{C.RESET}")
    hr("═", C.CYAN)

    ok_count, fail = 0, 0
    total = len(to_follow)
    for i, (aid, name) in enumerate(to_follow.items(), 1):
        success = follow_artist(session, aid)
        mark = f"{C.GREEN}✓{C.RESET}" if success else f"{C.RED}✗{C.RESET}"
        name_disp = name[:40] + ("…" if len(name) > 40 else "")
        print(f"  {mark} {C.WHITE}{name_disp:<42}{C.RESET} {progress_bar(i, total)}")
        if success: ok_count += 1
        else: fail += 1
        time.sleep(REQUEST_DELAY)

    print()
    hr("═", C.CYAN)
    print(f"  {C.BOLD}{C.GREEN}DONE{C.RESET}  "
          f"followed: {C.BOLD}{C.GREEN}{ok_count}{C.RESET}  "
          f"failed: {C.BOLD}{C.RED}{fail}{C.RESET}")
    hr("═", C.CYAN)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}Interrupted.{C.RESET}")

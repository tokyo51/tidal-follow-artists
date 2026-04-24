#!/usr/bin/env python3
"""
Tidal follow-artists tool.

Usage:
    python follow_artists.py                      # interactive run (default)
    python follow_artists.py run [--profile X]
    python follow_artists.py watch [--profile X] [--interval 1800]
    python follow_artists.py profiles             # list / manage profiles
"""

import argparse
import sys
import time
import threading
import shutil

import tidalapi

import tidal_core as core

TERM_W = shutil.get_terminal_size((80, 24)).columns


# ─── Colors ───────────────────────────────────────────────────
class C:
    RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"; ITALIC = "\033[3m"
    WHITE = "\033[97m"; GREY = "\033[38;5;244m"; DARKGREY = "\033[38;5;238m"
    GREEN = "\033[38;5;46m"; RED = "\033[38;5;203m"
    YELLOW = "\033[38;5;221m"; MAGENTA = "\033[38;5;213m"
    CYAN = "\033[38;5;51m"; BLUE = "\033[38;5;39m"
    DEEPBLUE = "\033[38;5;33m"; NAVY = "\033[38;5;27m"

GRADIENT = ["\033[38;5;27m","\033[38;5;33m","\033[38;5;39m",
            "\033[38;5;45m","\033[38;5;51m","\033[38;5;87m"]

BANNER_LINES = [
    "  ████████╗██╗██████╗  █████╗ ██╗",
    "  ╚══██╔══╝██║██╔══██╗██╔══██╗██║",
    "     ██║   ██║██║  ██║███████║██║",
    "     ██║   ██║██║  ██║██╔══██║██║",
    "     ██║   ██║██████╔╝██║  ██║███████╗",
    "     ╚═╝   ╚═╝╚═════╝ ╚═╝  ╚═╝╚══════╝",
]

# ─── UI helpers ───────────────────────────────────────────────
def clear_line(): sys.stdout.write("\r\033[K")
def hide_cursor(): sys.stdout.write("\033[?25l"); sys.stdout.flush()
def show_cursor(): sys.stdout.write("\033[?25h"); sys.stdout.flush()

def hr(char="─", color=C.DARKGREY, width=None):
    print(f"{color}{char * (width or min(TERM_W, 62))}{C.RESET}")

def info(m): print(f"{C.CYAN}ℹ{C.RESET}  {m}")
def ok(m):   print(f"{C.GREEN}✓{C.RESET}  {m}")
def warn(m): print(f"{C.YELLOW}⚠{C.RESET}  {m}")
def err(m):  print(f"{C.RED}✗{C.RESET}  {m}")
def ask(m):  return input(f"{C.MAGENTA}?{C.RESET}  {C.BOLD}{m}{C.RESET} ")

def section(title, color=C.CYAN):
    print(); hr("━", color)
    print(f"  {color}{C.BOLD}{title}{C.RESET}")
    hr("━", color)

def print_banner(subtitle, animate=True):
    if animate:
        for i, line in enumerate(BANNER_LINES):
            print(f"{GRADIENT[min(i, len(GRADIENT)-1)]}{C.BOLD}{line}{C.RESET}")
            time.sleep(0.04)
    else:
        for i, line in enumerate(BANNER_LINES):
            print(f"{GRADIENT[min(i, len(GRADIENT)-1)]}{C.BOLD}{line}{C.RESET}")
    print(f"  {C.DIM}{C.ITALIC}{subtitle}{C.RESET}\n")


class Spinner:
    FRAMES = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    def __init__(self, text, color=C.CYAN):
        self.text, self.color = text, color
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)
    def _run(self):
        hide_cursor(); i = 0
        while not self._stop.is_set():
            sys.stdout.write(f"\r{self.color}{self.FRAMES[i%len(self.FRAMES)]}{C.RESET}  {self.text}")
            sys.stdout.flush(); time.sleep(0.08); i += 1
        clear_line(); show_cursor()
    def __enter__(self): self._t.start(); return self
    def __exit__(self,*a): self._stop.set(); self._t.join()


def gradient_bar(cur, tot, width=34):
    pct = cur / tot if tot else 1
    filled = int(width * pct)
    bar = ""
    for i in range(width):
        if i < filled:
            idx = int((i / max(width - 1, 1)) * (len(GRADIENT) - 1))
            bar += f"{GRADIENT[idx]}█"
        else:
            bar += f"{C.DARKGREY}░"
    return f"{bar}{C.RESET} {C.BOLD}{cur:>4}/{tot}{C.RESET} {C.GREY}{pct*100:5.1f}%{C.RESET}"

def stat(label, val, color=C.CYAN):
    return f"{C.GREY}{label}{C.RESET} {color}{C.BOLD}{val}{C.RESET}"


# ─── Login wrapper ────────────────────────────────────────────
def ensure_login(profile: str) -> tidalapi.Session:
    session = tidalapi.Session()
    with Spinner("Restoring cached session…"):
        restored = core.restore_session(session, profile)
    if restored:
        ok(f"Logged in  {C.GREY}· profile {C.BOLD}{profile}{C.RESET}{C.GREY} · user {session.user.id}{C.RESET}")
        return session

    init = core.begin_login(session)
    section("TIDAL LOGIN", C.CYAN)
    print(f"  Profile: {C.BOLD}{profile}{C.RESET}")
    print(f"  Open this {C.BOLD}full URL{C.RESET} in your browser")
    print(f"  {C.DIM}(don't type the code on link.tidal.com/activate){C.RESET}\n")
    print(f"    {C.CYAN}{C.BOLD}{init.url}{C.RESET}\n")
    print(f"  Then click {C.BOLD}Log In{C.RESET} to confirm.")
    hr("━", C.CYAN)
    with Spinner("Waiting for browser confirmation…", C.MAGENTA):
        init.future.result()
    core.persist_session(session, profile)
    ok(f"Logged in. Session cached to profile {C.BOLD}{profile}{C.RESET}.")
    return session


# ─── Interactive playlist selection ───────────────────────────
def choose_mode():
    section("MODE")
    print(f"  {C.CYAN}[1]{C.RESET} Single playlist")
    print(f"  {C.CYAN}[2]{C.RESET} Multiple playlists   {C.GREY}(e.g. 1,3,7 or 2-5,8){C.RESET}")
    print(f"  {C.CYAN}[3]{C.RESET} All playlists")
    print(f"  {C.CYAN}[4]{C.RESET} Dry-run              {C.GREY}(preview only){C.RESET}")
    while True:
        c = ask("Choose mode [1/2/3/4]:").strip()
        if c in ("1","2","3","4"): return c
        err("Invalid choice.")

def render_playlists(playlists):
    section(f"YOUR PLAYLISTS  ({len(playlists)})")
    for i, p in enumerate(playlists, 1):
        cnt = getattr(p, "num_tracks", "?")
        print(f"  {C.DEEPBLUE}▸{C.RESET} {C.CYAN}{i:>3}{C.RESET}  {C.WHITE}{p.name}{C.RESET}  {C.GREY}{cnt} tracks{C.RESET}")

def select_playlists(playlists, mode):
    if mode == "3": return playlists
    if mode == "1":
        while True:
            c = ask(f"Pick playlist number [1-{len(playlists)}]:").strip()
            if c.isdigit() and 1 <= int(c) <= len(playlists):
                return [playlists[int(c)-1]]
            err("Invalid choice.")
    while True:
        raw = ask("Pick playlists:").strip()
        picked = set()
        try:
            for part in raw.split(","):
                part = part.strip()
                if "-" in part:
                    a, b = part.split("-")
                    picked.update(range(int(a), int(b)+1))
                else:
                    picked.add(int(part))
            if not picked or any(i < 1 or i > len(playlists) for i in picked):
                raise ValueError
            return [playlists[i-1] for i in sorted(picked)]
        except ValueError:
            err("Invalid input. Try again.")


# ─── CMD: run (bulk follow) ───────────────────────────────────
def cmd_run(args):
    print()
    print_banner("run · bulk-follow every artist from your playlists")
    session = ensure_login(args.profile)

    with Spinner("Fetching your playlists…"):
        playlists = core.all_playlists(session)
    if not playlists:
        err("No playlists found."); sys.exit(1)

    mode = choose_mode()
    render_playlists(playlists)
    selected = select_playlists(playlists, "2" if mode == "4" else mode)
    dry_run = mode == "4"

    print()
    ok(f"Selected {C.BOLD}{len(selected)}{C.RESET} playlist(s)")
    for p in selected:
        print(f"   {C.DEEPBLUE}▸{C.RESET} {C.WHITE}{p.name}{C.RESET}")

    def _scan_cb(p, n): ok(f"{p.name}  {C.GREY}· {n} tracks{C.RESET}")
    print()
    artists = {}
    for p in selected:
        with Spinner(f"Scanning {C.BOLD}{p.name}{C.RESET}…"):
            partial = core.collect_artists([p])
        for aid, (name, cnt) in partial.items():
            if aid in artists:
                n0, c0 = artists[aid]
                artists[aid] = (n0, c0 + cnt)
            else:
                artists[aid] = (name, cnt)
        ok(f"{p.name}  {C.GREY}· scanned{C.RESET}")

    with Spinner("Checking existing follows…"):
        already = core.followed_artist_ids(session)
    to_follow = {aid: v for aid, v in artists.items() if aid not in already}
    skipped = len(artists) - len(to_follow)
    top = sorted(artists.items(), key=lambda kv: -kv[1][1])[:5]

    section("OVERVIEW")
    print(f"  {stat('Total unique artists', len(artists))}")
    print(f"  {stat('Already following   ', skipped, C.GREY)}")
    print(f"  {stat('Will follow         ', len(to_follow), C.GREEN)}")
    if top:
        print(f"\n  {C.DIM}Top artists in selection:{C.RESET}")
        for _, (name, cnt) in top:
            print(f"    {C.CYAN}♪{C.RESET} {C.WHITE}{name}{C.RESET}  {C.GREY}× {cnt}{C.RESET}")

    if not to_follow:
        ok("\nNothing to do."); return
    if dry_run:
        print(); warn(f"{C.BOLD}Dry-run{C.RESET} — nothing will be followed."); return

    print()
    if ask(f"Follow {C.BOLD}{len(to_follow)}{C.RESET} artists? [y/N]:").strip().lower() != "y":
        warn("Aborted."); return

    section("FOLLOWING ARTISTS", C.CYAN)
    ok_c, fail = 0, 0
    total = len(to_follow); start = time.time()
    hide_cursor()
    try:
        for i, (aid, (name, _)) in enumerate(to_follow.items(), 1):
            s = core.follow_artist(session, aid)
            if s: ok_c += 1
            else: fail += 1
            mark = f"{C.GREEN}✓{C.RESET}" if s else f"{C.RED}✗{C.RESET}"
            disp = name[:32] + ("…" if len(name) > 32 else "")
            clear_line()
            sys.stdout.write(f"  {mark} {C.WHITE}{disp:<33}{C.RESET}  {gradient_bar(i, total)}\n")
            sys.stdout.write(f"    {C.DIM}✓ {ok_c}  ✗ {fail}  ·  {(time.time()-start):.1f}s elapsed{C.RESET}")
            sys.stdout.flush()
            time.sleep(core.REQUEST_DELAY)
    finally:
        clear_line(); show_cursor()

    print()
    hr("━", C.CYAN)
    print(f"  {C.BOLD}{C.CYAN}✨ DONE{C.RESET}")
    hr("━", C.CYAN)
    print(f"  {stat('Followed    ', ok_c, C.GREEN)}")
    print(f"  {stat('Failed      ', fail, C.RED if fail else C.GREY)}")
    print(f"  {stat('Skipped     ', skipped, C.GREY)}")
    print(f"  {stat('Time elapsed', f'{time.time()-start:.1f}s', C.CYAN)}")
    hr("━", C.CYAN)


# ─── CMD: watch (daemon) ──────────────────────────────────────
def cmd_watch(args):
    print()
    print_banner(f"watch · auto-follow new artists every {args.interval}s")
    session = ensure_login(args.profile)

    cfg = core.load_watch_config(args.profile)
    if cfg is None or args.reset:
        with Spinner("Fetching your playlists…"):
            playlists = core.all_playlists(session)
        render_playlists(playlists)
        selected = select_playlists(playlists, "2")
        section("BUILDING BASELINE")
        baseline = core.collect_artists(selected)
        cfg = {
            "playlist_ids": [str(p.id) for p in selected],
            "playlist_names": [p.name for p in selected],
            "baseline_artist_ids": list(baseline.keys()),
            "created_at": time.time(),
        }
        core.save_watch_config(args.profile, cfg)
        ok(f"Baseline saved: {len(baseline)} artists across {len(selected)} playlists.")
    else:
        info(f"Watching {len(cfg['playlist_ids'])} playlist(s): "
             + ", ".join(cfg['playlist_names']))
        info(f"Baseline: {len(cfg['baseline_artist_ids'])} artists.")

    section("WATCHING", C.CYAN)
    info(f"Interval: {C.BOLD}{args.interval}s{C.RESET}. Press Ctrl+C to stop.")
    print()

    tick = 0
    while True:
        tick += 1
        try:
            playlists = [core.playlist_by_id(session, pid) for pid in cfg["playlist_ids"]]
            playlists = [p for p in playlists if p is not None]
            current = core.collect_artists(playlists)
            baseline_ids = set(cfg["baseline_artist_ids"])
            new_ids = [aid for aid in current.keys() if aid not in baseline_ids]

            ts = time.strftime("%H:%M:%S")
            if new_ids:
                already = core.followed_artist_ids(session)
                actually_new = [aid for aid in new_ids if aid not in already]
                print(f"{C.GREY}[{ts}] tick #{tick}{C.RESET}  "
                      f"{C.YELLOW}{len(new_ids)} new{C.RESET} in playlists  "
                      f"({C.GREEN}{len(actually_new)} to follow{C.RESET})")
                for aid in actually_new:
                    name, _ = current[aid]
                    s = core.follow_artist(session, aid)
                    mark = f"{C.GREEN}✓{C.RESET}" if s else f"{C.RED}✗{C.RESET}"
                    print(f"  {mark} {name}")
                    time.sleep(core.REQUEST_DELAY)
                cfg["baseline_artist_ids"] = list(current.keys())
                core.save_watch_config(args.profile, cfg)
            else:
                print(f"{C.GREY}[{ts}] tick #{tick}  · no changes{C.RESET}")
        except Exception as e:
            err(f"Tick failed: {e}")

        time.sleep(args.interval)


# ─── CMD: profiles ────────────────────────────────────────────
def cmd_profiles(args):
    print()
    print_banner("profiles · manage multiple Tidal accounts", animate=False)
    profiles = core.list_profiles()
    section("PROFILES")
    if not profiles:
        info("No profiles yet. Run `follow_artists.py run --profile NAME` to create one.")
    else:
        for p in profiles:
            mark_default = f" {C.CYAN}(default){C.RESET}" if p == core.DEFAULT_PROFILE else ""
            print(f"  {C.DEEPBLUE}▸{C.RESET} {C.WHITE}{C.BOLD}{p}{C.RESET}{mark_default}")
    if args.delete:
        if core.delete_profile(args.delete):
            ok(f"Deleted profile {args.delete}.")
        else:
            err(f"Profile {args.delete} not found.")


# ─── Arg parser ───────────────────────────────────────────────
def build_parser():
    p = argparse.ArgumentParser(prog="follow_artists")
    p.add_argument("--profile", default=core.DEFAULT_PROFILE,
                   help="Tidal session profile (default: 'default')")
    sub = p.add_subparsers(dest="cmd")

    p_run = sub.add_parser("run", help="Bulk-follow all artists from selected playlist(s)")
    p_run.add_argument("--profile", default=core.DEFAULT_PROFILE)
    p_run.set_defaults(func=cmd_run)

    p_watch = sub.add_parser("watch", help="Daemon: auto-follow new artists in watched playlists")
    p_watch.add_argument("--profile", default=core.DEFAULT_PROFILE)
    p_watch.add_argument("--interval", type=int, default=1800, help="Seconds between checks (default 1800)")
    p_watch.add_argument("--reset", action="store_true", help="Reset baseline and re-select playlists")
    p_watch.set_defaults(func=cmd_watch)

    p_pr = sub.add_parser("profiles", help="List / manage profiles")
    p_pr.add_argument("--delete", help="Delete a profile by name")
    p_pr.set_defaults(func=cmd_profiles)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not args.cmd:
        args = parser.parse_args(["run"])
    try:
        args.func(args)
    except KeyboardInterrupt:
        show_cursor()
        print(f"\n{C.YELLOW}Interrupted.{C.RESET}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import argparse
import json
import time
import curses
import ssl
from urllib import request, error
from urllib.parse import urlparse

POLL_INTERVAL = 1.0         # seconds
HISTORY_LENGTH = 60         # how many seconds to keep in the graph


def classify_status(status):
    """
    Map arbitrary status text to one of: good, warn, bad, unknown.
    """
    if status is None:
        return "unknown"

    s = str(status).lower()

    if s in ("good", "ok", "okay", "healthy", "green"):
        return "good"

    if any(word in s for word in ("warn", "degrad", "yellow")):
        return "warn"

    if any(word in s for word in ("bad", "down", "error", "fail", "critical", "red")):
        return "bad"

    return "unknown"


def fetch_status(base_url, token, timeout=2, insecure=False):
    """
    Call <base_url>/api/gateway/ve/status with Bearer token.
    Returns (status_string, extra_info_dict).
    """
    base_url = base_url.rstrip("/")
    url = f"{base_url}/api/gateway/ve/status"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    req = request.Request(url, headers=headers)

    try:
        with request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw)

            # Prefer top-level 'status', fall back to derived
            overall = data.get("status")
            if not overall and isinstance(data.get("services"), list):
                # If any service isn't good, degrade status
                statuses = [str(s.get("status", "")).lower()
                            for s in data["services"]]
                if any("down" in s or "fail" in s or "error" in s for s in statuses):
                    overall = "bad"
                elif any("warn" in s or "degrad" in s for s in statuses):
                    overall = "warn"
                else:
                    overall = "good"

            return overall, data

    except error.HTTPError as e:
        return f"HTTP {e.code}", {"error": f"HTTP {e.code}: {e.reason}"}
    except error.URLError as e:
        return "down", {"error": f"URL error: {e.reason}"}
    except Exception as e:
        return "down", {"error": f"Exception: {e}"}


def short_name_from_url(u):
    try:
        parsed = urlparse(u)
        if parsed.hostname:
            return parsed.hostname
    except Exception:
        pass
    # fall back
    return u


def run_dashboard(stdscr, endpoints, token, insecure=False):
    curses.curs_set(0)
    stdscr.nodelay(True)
    curses.start_color()

    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)   # good
    curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # warn
    curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)     # bad
    curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)    # unknown
    curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLACK)   # text

    color_for_class = {
        "good": curses.color_pair(1),
        "warn": curses.color_pair(2),
        "bad": curses.color_pair(3),
        "unknown": curses.color_pair(4),
    }

    histories = {e: [] for e in endpoints}
    last_errors = {e: "" for e in endpoints}

    while True:
        start = time.time()
        h, w = stdscr.getmaxyx()
        stdscr.erase()

        # Header
        title = "AAP Gateway Health Monitor (press 'q' to quit)"
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        header = f"{title}  {now}"
        stdscr.addstr(0, 0, header[:w - 1], curses.color_pair(5))

        # Legend
        legend = "Legend: GOOD ●   WARN ●   BAD ●   UNKNOWN ●"
        stdscr.addstr(1, 0, legend[:w - 1], curses.color_pair(5))
        stdscr.addstr(1, len("Legend: "), "GOOD ●", color_for_class["good"])
        off = len("Legend: GOOD ●   ")
        stdscr.addstr(1, off, "WARN ●", color_for_class["warn"])
        off += len("WARN ●   ")
        stdscr.addstr(1, off, "BAD ●", color_for_class["bad"])
        off += len("BAD ●   ")
        stdscr.addstr(1, off, "UNKNOWN ●", color_for_class["unknown"])

        # Poll endpoints
        for endpoint in endpoints:
            status_text, extra = fetch_status(endpoint, token, insecure=insecure)
            cls = classify_status(status_text)
            histories[endpoint].append(cls)
            if len(histories[endpoint]) > HISTORY_LENGTH:
                histories[endpoint] = histories[endpoint][-HISTORY_LENGTH:]

            last_errors[endpoint] = extra.get("error") or ""

        # Draw per-endpoint rows
        row = 3
        graph_width = max(10, w - 35)  # space for name + status text

        for endpoint in endpoints:
            if row >= h:
                break  # no more space on screen

            name = short_name_from_url(endpoint)
            latest_cls = histories[endpoint][-1] if histories[endpoint] else "unknown"
            latest_str = latest_cls.upper()

            # Row label: endpoint + latest status
            label = f"{name:20} [{latest_str:7}] "
            stdscr.addstr(row, 0, label[:30], curses.color_pair(5))

            # History graph (right to left)
            hist = histories[endpoint][-graph_width:]
            x_start = 30
            padding = graph_width - len(hist)
            # pad with unknown to the left
            hist = ["unknown"] * padding + hist

            for i, cls in enumerate(hist):
                x = x_start + i
                if x >= w:
                    break
                style = color_for_class.get(cls, color_for_class["unknown"])
                stdscr.addstr(row, x, "●", style)

            row += 1

            # Optional one-line error/info
            err = last_errors.get(endpoint)
            if err and row < h:
                msg = f"  last error: {err}"
                stdscr.addstr(row, 2, msg[:w - 3], curses.color_pair(5))
                row += 1

        stdscr.refresh()

        # Handle keypress (non-blocking)
        remaining = POLL_INTERVAL - (time.time() - start)
        end_wait = time.time() + max(0.0, remaining)
        while time.time() < end_wait:
            try:
                ch = stdscr.getch()
            except KeyboardInterrupt:
                return
            if ch in (ord("q"), ord("Q"), 27):  # q or ESC
                return
            time.sleep(0.05)


def parse_args():
    p = argparse.ArgumentParser(
        description="Simple AAP gateway health monitor (terminal dashboard)."
    )
    p.add_argument(
        "endpoints",
        nargs="+",
        help="Base URLs of gateways/LB (e.g. https://gw1.example.com)",
    )
    p.add_argument(
        "--token",
        "-t",
        required=True,
        help="Bearer token to use for Authorization header.",
    )
    p.add_argument(
        "--insecure",
        "-k",
        action="store_true",
        help="Skip TLS certificate verification.",
    )
    return p.parse_args()


def main():
    args = parse_args()
    curses.wrapper(run_dashboard, args.endpoints, args.token, args.insecure)


if __name__ == "__main__":
    main()

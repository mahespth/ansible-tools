#!/usr/bin/env python3
"""
AAP Gateway Health Monitor (Terminal Dashboard)
==============================================

Description
-----------
Simple Python 3 terminal app (curses-based) to monitor the health of
AAP gateways and/or a load balancer.

It:
- Polls one or more endpoints every second.
- By default calls:  <base_url>/api/gateway/v1/status/
- Optionally calls:  <base_url>/api/gateway/v1/ping/ instead (with --ping).
- Sends a Bearer token in the Authorization header.
- Classifies status into: GOOD / WARN / BAD / UNKNOWN.
- Displays a scrolling, colored graph of recent status for each endpoint.
- Tracks and displays the % of requests that are NOT GOOD, ignoring UNKNOWN.
- Tracks how many times each distinct error has occurred per endpoint and
  shows an error section grouped by endpoint label.
- Shows in the header which host the monitor itself is running on.
- Uses only the Python standard library (suitable for typical AAP installs).
- Can optionally fetch all endpoints concurrently using threads.
- By default shows a truncated hostname:
    - FQDN like gw1.example.com -> "gw1"
    - IP addresses like 10.0.0.1 are shown in full.
  Use --show-full-hostnames to show the full hostname (including domain).

Controls
--------
- Press 'q' or ESC to quit the dashboard.
- Press Ctrl-C to exit cleanly (no traceback).

"""

import argparse
import json
import time
import curses
import ssl
import socket
from urllib import request, error
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

POLL_INTERVAL = 1.0         # seconds between polls
HISTORY_LENGTH = 60         # number of points kept per endpoint

# Host running the monitor
MONITOR_HOST = socket.gethostname()


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


def fetch_status(base_url, token, timeout=5, insecure=False, use_ping=False):
    """
    Call the appropriate endpoint with Bearer token.

    - If use_ping is False:
        <base_url>/api/gateway/v1/status/
        Expects JSON and derives an overall status.
    - If use_ping is True:
        <base_url>/api/gateway/v1/ping/
        Treats any successful call as "good" and returns body in extra_info.
    """
    base_url = base_url.rstrip("/")
    if use_ping:
        url = f"{base_url}/api/gateway/v1/ping/"
    else:
        url = f"{base_url}/api/gateway/v1/status/"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json" if not use_ping else "*/*",
    }

    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    req = request.Request(url, headers=headers)

    try:
        with request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read().decode("utf-8", errors="replace")

            if use_ping:
                extra = {"body": raw}
                overall = "good"
                return overall, extra

            data = json.loads(raw)

            overall = data.get("status")
            if not overall and isinstance(data.get("services"), list):
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


def hostname_from_url(u):
    try:
        parsed = urlparse(u)
        if parsed.hostname:
            return parsed.hostname
    except Exception:
        pass
    return u


def truncate_hostname(host):
    """
    Truncate a FQDN to just the host part; keep IPs as-is.
    """
    if not host:
        return host

    parts = host.split(".")

    # IPv4-ish: all numeric parts
    if all(p.isdigit() for p in parts if p):
        return host

    if "." in host:
        return host.split(".", 1)[0]
    return host


def run_dashboard(
    stdscr,
    endpoints,
    token,
    timeout,
    insecure=False,
    async_requests=False,
    use_ping=False,
    show_full_hostnames=False,
):
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

    # Histories and stats
    histories = {e: [] for e in endpoints}
    last_errors = {e: "" for e in endpoints}
    stats = {e: {"non_good": 0, "known": 0} for e in endpoints}
    error_counts = {e: {} for e in endpoints}

    # Labels (hostnames) and dynamic name width
    labels = {}
    for ep in endpoints:
        host = hostname_from_url(ep)
        labels[ep] = host if show_full_hostnames else truncate_hostname(host)

    max_name_len = max((len(n) for n in labels.values()), default=4)
    name_width = max(max_name_len, 4)

    executor = ThreadPoolExecutor(max_workers=len(endpoints)) if async_requests else None

    try:
        try:
            while True:
                start = time.time()
                h, w = stdscr.getmaxyx()
                stdscr.erase()

                # Header
                mode_str = "PING" if use_ping else "STATUS"
                host_mode_str = "FULL" if show_full_hostnames else "TRUNC"
                title = f"AAP Gateway Health Monitor [{mode_str} | {host_mode_str}] (press 'q' to quit)"
                now = time.strftime("%Y-%m-%d %H:%M:%S")
                header = f"{title}  {now}  host:{MONITOR_HOST}"
                stdscr.addstr(0, 0, header[:w - 1], curses.color_pair(5))

                # Legend
                legend = "Legend: GOOD ●   WARN ●   BAD ●   UNKNOWN ●   %NG = non-good (excl. UNKNOWN)"
                stdscr.addstr(1, 0, legend[:w - 1], curses.color_pair(5))
                stdscr.addstr(1, len("Legend: "), "GOOD ●", color_for_class["good"])
                off = len("Legend: GOOD ●   ")
                stdscr.addstr(1, off, "WARN ●", color_for_class["warn"])
                off += len("WARN ●   ")
                stdscr.addstr(1, off, "BAD ●", color_for_class["bad"])
                off += len("BAD ●   ")
                stdscr.addstr(1, off, "UNKNOWN ●", color_for_class["unknown"])

                # Determine dynamic graph start and width based on name_width
                # label = f"{name:{name_width}} [{status:7}] {pct:8}"
                label_width = name_width + 19
                x_start = label_width + 2
                # Graph width limited by screen width and history length
                graph_width = max(10, min(HISTORY_LENGTH, max(0, w - x_start - 1)))

                # Poll endpoints
                if async_requests and executor is not None:
                    future_to_ep = {
                        executor.submit(fetch_status, ep, token, timeout, insecure, use_ping): ep
                        for ep in endpoints
                    }
                    for fut in as_completed(future_to_ep):
                        ep = future_to_ep[fut]
                        try:
                            status_text, extra = fut.result()
                        except Exception as e:
                            status_text, extra = "down", {"error": f"Exception: {e}"}

                        cls = classify_status(status_text)
                        histories[ep].append(cls)
                        if len(histories[ep]) > HISTORY_LENGTH:
                            histories[ep] = histories[ep][-HISTORY_LENGTH:]

                        if cls != "unknown":
                            stats[ep]["known"] += 1
                            if cls != "good":
                                stats[ep]["non_good"] += 1

                        err_msg = extra.get("error")
                        if err_msg:
                            endpoint_errors = error_counts.setdefault(ep, {})
                            endpoint_errors[err_msg] = endpoint_errors.get(err_msg, 0) + 1
                            last_errors[ep] = err_msg
                        else:
                            last_errors[ep] = extra.get("body", "") or ""
                else:
                    for ep in endpoints:
                        status_text, extra = fetch_status(
                            ep, token, timeout=timeout, insecure=insecure, use_ping=use_ping
                        )
                        cls = classify_status(status_text)
                        histories[ep].append(cls)
                        if len(histories[ep]) > HISTORY_LENGTH:
                            histories[ep] = histories[ep][-HISTORY_LENGTH:]

                        if cls != "unknown":
                            stats[ep]["known"] += 1
                            if cls != "good":
                                stats[ep]["non_good"] += 1

                        err_msg = extra.get("error")
                        if err_msg:
                            endpoint_errors = error_counts.setdefault(ep, {})
                            endpoint_errors[err_msg] = endpoint_errors.get(err_msg, 0) + 1
                            last_errors[ep] = err_msg
                        else:
                            last_errors[ep] = extra.get("body", "") or ""

                # Draw per-endpoint rows
                row = 3

                for endpoint in endpoints:
                    if row >= h:
                        break

                    name = labels[endpoint]
                    latest_cls = histories[endpoint][-1] if histories[endpoint] else "unknown"
                    latest_str = latest_cls.upper()

                    st = stats[endpoint]
                    if st["known"] > 0:
                        pct_ng = int(round(100.0 * st["non_good"] / st["known"]))
                        pct_str = f"{pct_ng:3d}% NG"
                    else:
                        pct_str = "  -  "

                    label = f"{name:{name_width}} [{latest_str:7}] {pct_str:8}"
                    stdscr.addstr(row, 0, label[:x_start - 1], curses.color_pair(5))

                    # History graph – NO LEFT PADDING WITH UNKNOWN
                    hist = histories[endpoint][-graph_width:]
                    for i, cls in enumerate(hist):
                        x = x_start + i
                        if x >= w:
                            break
                        style = color_for_class.get(cls, color_for_class["unknown"])
                        stdscr.addstr(row, x, "●", style)

                    row += 1

                    err = last_errors.get(endpoint)
                    if err and row < h:
                        msg = f"  last info: {err}"
                        stdscr.addstr(row, 2, msg[:w - 3], curses.color_pair(5))
                        row += 1

                # Per-endpoint error summary
                any_errors = any(error_counts[ep] for ep in endpoints)
                if any_errors and row < h:
                    stdscr.addstr(row, 0, "Errors seen this session:", curses.color_pair(5))
                    row += 1

                    for ep in endpoints:
                        ep_errors = error_counts.get(ep) or {}
                        if not ep_errors:
                            continue
                        if row >= h:
                            break

                        ep_label_line = f"  {labels[ep]}:"
                        stdscr.addstr(row, 0, ep_label_line[:w - 1], curses.color_pair(5))
                        row += 1

                        for msg, count in sorted(
                            ep_errors.items(), key=lambda kv: kv[1], reverse=True
                        ):
                            if row >= h:
                                break
                            line = f"    [{count:4d}x] {msg}"
                            stdscr.addstr(row, 0, line[:w - 1], curses.color_pair(5))
                            row += 1

                stdscr.refresh()

                # Handle keypress
                remaining = POLL_INTERVAL - (time.time() - start)
                end_wait = time.time() + max(0.0, remaining)
                while time.time() < end_wait:
                    ch = stdscr.getch()
                    if ch in (ord("q"), ord("Q"), 27):  # q or ESC
                        return
                    time.sleep(0.05)
        except KeyboardInterrupt:
            return
    finally:
        if executor is not None:
            executor.shutdown(wait=False)


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
        "--timeout",
        type=float,
        default=5.0,
        help="Request timeout in seconds (default: 5).",
    )
    p.add_argument(
        "--async-requests",
        action="store_true",
        help="Fetch statuses concurrently using worker threads.",
    )
    p.add_argument(
        "--ping",
        action="store_true",
        help="Use /api/gateway/v1/ping/ instead of /api/gateway/v1/status/.",
    )
    p.add_argument(
        "--show-full-hostnames",
        action="store_true",
        help="Display full hostnames (including domain) instead of truncated hostnames.",
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
    try:
        curses.wrapper(
            run_dashboard,
            args.endpoints,
            args.token,
            args.timeout,
            args.insecure,
            args.async_requests,
            args.ping,
            args.show_full_hostnames,
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

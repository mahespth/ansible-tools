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
- Uses only the Python standard library (suitable for typical AAP installs).
- Can optionally fetch all endpoints concurrently using threads.
- By default shows a truncated hostname:
    - FQDN like gw1.example.com -> "gw1"
    - IP addresses like 10.0.0.1 are shown in full.
  Use --show-full-hostnames to show the full hostname (including domain).

Expected API (status mode)
--------------------------
When using the status endpoint, this script assumes it returns JSON. It will:
- Prefer a top-level key "status" if present.
- Otherwise, if "services" is a list, it derives an overall status from
  the services' "status" fields (checking for failures/warnings).

Status classification rules (case-insensitive):
- GOOD    -> "good", "ok", "okay", "healthy", "green"
- WARN    -> any of "warn", "degrad", "yellow"
- BAD     -> any of "bad", "down", "error", "fail", "critical", "red"
- UNKNOWN -> anything else or missing.

Ping mode
---------
When using --ping:
- Calls <base_url>/api/gateway/v1/ping/
- Any successful HTTP response with no exception is treated as "good"
- The response body is stored in extra_info["body"] for display/logging.
- HTTP errors / timeouts are still treated as "down"/BAD.

Non-good percentage
-------------------
For each endpoint, the monitor keeps running stats:
- It counts only samples that are not UNKNOWN.
- % non-good = (WARN + BAD + other non-good) / (GOOD + WARN + BAD) * 100
- This is shown in the row as e.g. " 25% NG".

Usage
-----
    ./aap_gateway_monitor.py \\
        --token 'YOUR_BEARER_TOKEN' \\
        --timeout 5 \\
        --async-requests \\
        https://lb.example.com \\
        https://gw1.example.com \\
        https://gw2.example.com \\
        https://gw3.example.com \\
        https://gw4.example.com

    # Use /api/gateway/v1/ping/ instead of /api/gateway/v1/status/
    ./aap_gateway_monitor.py \\
        --token 'YOUR_BEARER_TOKEN' \\
        --ping \\
        https://gw1.example.com

    # Show full hostnames (gw1.example.com instead of "gw1")
    ./aap_gateway_monitor.py \\
        --token 'YOUR_BEARER_TOKEN' \\
        --show-full-hostnames \\
        https://gw1.example.com https://gw2.example.com

Arguments
---------
Positional:
  endpoints            One or more base URLs, e.g. https://gw1.example.com

Options:
  -t, --token          Bearer token to use for Authorization.
  --timeout            Request timeout in seconds (default: 5).
  --async-requests     Fetch statuses concurrently using worker threads.
  --ping               Use /api/gateway/v1/ping/ instead of /api/gateway/v1/status/.
  --show-full-hostnames
                       Display full hostnames (including domain) instead of
                       truncated hostnames.
  -k, --insecure       Skip TLS certificate verification (self-signed, lab, etc.).

Controls
--------
- Press 'q' or ESC to quit the dashboard.

"""

import argparse
import json
import time
import curses
import ssl
from urllib import request, error
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

POLL_INTERVAL = 1.0         # seconds between polls
HISTORY_LENGTH = 60         # number of points in the graph (seconds)


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
                # Any successful response is considered good.
                extra = {"body": raw}
                overall = "good"
                return overall, extra

            # Status mode: expect JSON
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


def hostname_from_url(u):
    """
    Extract hostname from a URL or return the input if parsing fails.
    """
    try:
        parsed = urlparse(u)
        if parsed.hostname:
            return parsed.hostname
    except Exception:
        pass
    return u


def truncate_hostname(host):
    """
    Truncate a FQDN to just the host part:
    - 'gw1.example.com' -> 'gw1'
    - 'gw1' -> 'gw1'
    - '10.0.0.1' -> '10.0.0.1'  (don't truncate IPs)
    """
    if not host:
        return host

    parts = host.split(".")

    # Detect simple IPv4 like 10.0.0.1
    if all(p.isdigit() for p in parts if p):
        return host  # looks like an IP, keep full

    # For non-IPs, if FQDN, return first label
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
    # stats[ep] = {"non_good": int, "known": int}
    stats = {e: {"non_good": 0, "known": 0} for e in endpoints}

    # Labels: truncated hostname by default, or full hostname if requested
    labels = {}
    for ep in endpoints:
        host = hostname_from_url(ep)
        if show_full_hostnames:
            labels[ep] = host
        else:
            labels[ep] = truncate_hostname(host)

    executor = ThreadPoolExecutor(max_workers=len(endpoints)) if async_requests else None

    try:
        while True:
            start = time.time()
            h, w = stdscr.getmaxyx()
            stdscr.erase()

            # Header
            mode_str = "PING" if use_ping else "STATUS"
            host_mode_str = "FULL" if show_full_hostnames else "TRUNC"
            title = (
                f"AAP Gateway Health Monitor [{mode_str} | {host_mode_str}] "
                "(press 'q' to quit)"
            )
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            header = f"{title}  {now}"
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

            # Poll endpoints (sequential or concurrent)
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

                    # Update stats: ignore UNKNOWN
                    if cls != "unknown":
                        stats[ep]["known"] += 1
                        if cls != "good":
                            stats[ep]["non_good"] += 1

                    last_errors[ep] = extra.get("error") or extra.get("body", "") or ""
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

                    last_errors[ep] = extra.get("error") or extra.get("body", "") or ""

            # Draw per-endpoint rows
            row = 3
            x_start = 45  # where the graph starts
            graph_width = max(10, w - x_start - 1)

            for endpoint in endpoints:
                if row >= h:
                    break  # no more space on screen

                name = labels[endpoint]
                latest_cls = histories[endpoint][-1] if histories[endpoint] else "unknown"
                latest_str = latest_cls.upper()

                # Calculate % non-good (exclude UNKNOWN)
                st = stats[endpoint]
                if st["known"] > 0:
                    pct_ng = int(round(100.0 * st["non_good"] / st["known"]))
                    pct_str = f"{pct_ng:3d}% NG"
                else:
                    pct_str = "  -  "

                # Row label: endpoint label + latest status + % non-good
                label = f"{name:12} [{latest_str:7}] {pct_str:8}"
                stdscr.addstr(row, 0, label[:x_start - 1], curses.color_pair(5))

                # History graph
                hist = histories[endpoint][-graph_width:]
                padding = graph_width - len(hist)
                hist = ["unknown"] * padding + hist  # pad left with unknowns

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
                    msg = f"  last info: {err}"
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


if __name__ == "__main__":
    main()

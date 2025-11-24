#!/usr/bin/env python3
"""
AAP Environment Monitor (Controller Dashboard)
=============================================

Description
-----------
Curses-based terminal dashboard to monitor a Red Hat Ansible Automation Platform
(AAP) Controller environment.

It:
- Connects to an AAP Controller using a Bearer token.
- Polls the Controller every few seconds.
- Shows Controller **topology** (instances) and their health using a colored
  GOOD/WARN/BAD/UNKNOWN scheme.
- Shows **currently running jobs**, including:
    - Job ID
    - Name
    - User who launched it
    - How long it has been running (elapsed)
- Uses only Python standard library modules (suitable for typical AAP installs).

Assumed API Endpoints
---------------------
Base URL example: https://aap-controller.example.com

This script assumes a standard AAP / AWX-style API with:

- Instances (topology):
    GET <base_url>/api/v2/instances/

- Running jobs:
    GET <base_url>/api/v2/jobs/?status=running&order_by=-started&page_size=50

Authentication
--------------
The script expects a Bearer token and sends:

    Authorization: Bearer <YOUR_TOKEN>

If your environment uses a different auth header (e.g. "Token"), you can adjust
the AUTH_SCHEME constant below.

Color / Status Scheme
---------------------
Using the same color meaning as the gateway monitor:

- GOOD (green)
- WARN (yellow)
- BAD (red)
- UNKNOWN (cyan)

Instances:
- GOOD   -> enabled, no (or empty) "errors" field
- WARN   -> enabled but "errors" is present/non-empty, or capacity is 0
- BAD    -> disabled, or a fatal-looking "errors" field
- UNKNOWN -> anything else / unexpected data

Jobs:
- Shows all jobs with status "running" returned by the API.
- Uses the "elapsed" field if present, or falls back to "started" timestamp
  (if available) to compute a rough elapsed time.

Usage
-----
    ./aap_monitor.py \\
        --token 'YOUR_BEARER_TOKEN' \\
        https://aap-controller.example.com

Options
-------
Positional:
  base_url             Base URL of the AAP Controller, e.g. https://aap.example.com

Flags:
  -t, --token          Bearer token for Authorization header.
  --timeout            Request timeout (seconds). Default: 5.
  --poll-interval      Polling interval (seconds). Default: 2.
  --insecure, -k       Skip TLS certificate verification (self-signed/lab).
  --page-size          Max running jobs to fetch (page_size). Default: 50.

Controls
--------
- Press 'q' or ESC to quit the dashboard.
- Press Ctrl-C to exit cleanly (no traceback).

Notes
-----
If your AAP version uses slightly different endpoints or fields
(e.g. alternative instances endpoint), you can tweak API paths in:

    fetch_instances()
    fetch_running_jobs()

"""

import argparse
import curses
import json
import ssl
import socket
import time
from urllib import request, error
from urllib.parse import urljoin, urlencode
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AUTH_SCHEME = "Bearer"  # Change to "Token" if your AAP uses "Authorization: Token <token>"

DEFAULT_TIMEOUT = 5.0
DEFAULT_POLL_INTERVAL = 2.0
DEFAULT_PAGE_SIZE = 50

# How many jobs to display max (even if API returns more)
MAX_JOBS_DISPLAY = 20

# Host running this monitor
MONITOR_HOST = socket.gethostname()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def classify_status_text(status):
    """
    Map arbitrary status text to one of: good, warn, bad, unknown.
    Reused logic from gateway monitor.
    """
    if status is None:
        return "unknown"

    s = str(status).lower()

    if s in ("good", "ok", "okay", "healthy", "green", "running"):
        return "good"

    if any(word in s for word in ("warn", "degrad", "yellow")):
        return "warn"

    if any(word in s for word in ("bad", "down", "error", "fail", "critical", "red")):
        return "bad"

    return "unknown"


def classify_instance(instance):
    """
    Determine GOOD/WARN/BAD/UNKNOWN for a Controller instance.

    Heuristic based on common AAP/AWX instance fields:
    - enabled (bool)
    - capacity (int)
    - errors (string/list/dict)
    - node_state or node_type may be present but are treated as hints.
    """
    if not isinstance(instance, dict):
        return "unknown"

    enabled = instance.get("enabled")
    errors = instance.get("errors")
    capacity = instance.get("capacity")
    node_state = instance.get("node_state")  # may exist on some versions

    # Anything explicitly disabled is BAD.
    if enabled is False:
        return "bad"

    # If errors is a non-empty string/list/dict -> WARN/BAD
    if errors:
        # If it looks very severe, treat as BAD.
        err_str = str(errors).lower()
        if any(word in err_str for word in ("unreachable", "failed", "error", "down", "offline")):
            return "bad"
        return "warn"

    # If capacity is 0 but enabled and no errors: WARN (no capacity).
    if capacity == 0:
        return "warn"

    # If node_state exists, hint from it.
    if node_state:
        cls = classify_status_text(node_state)
        if cls != "unknown":
            return cls

    # Enabled or missing means GOOD if nothing else complains.
    if enabled in (True, None):
        return "good"

    return "unknown"


def parse_iso8601(dt_str):
    """
    Parse an ISO-8601-ish datetime string (AAP's typical format) into a datetime.
    Returns None on failure.
    """
    if not dt_str:
        return None
    try:
        # Many AAP timestamps look like "2025-11-24T13:37:42.123456Z"
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


def format_elapsed(seconds):
    """
    Format elapsed seconds as H:MM:SS.
    """
    if seconds is None:
        return "--:--:--"
    try:
        seconds = int(seconds)
    except Exception:
        return "--:--:--"

    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:d}:{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def build_ssl_context(insecure=False):
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def api_get(base_url, path, token, timeout, insecure=False, query=None):
    """
    Make a GET request to base_url + path, with optional query dict.
    Returns parsed JSON on success.

    Raises HTTPError / URLError on failure.
    """
    base_url = base_url.rstrip("/") + "/"
    url = urljoin(base_url, path.lstrip("/"))
    if query:
        qs = urlencode(query)
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{qs}"

    headers = {
        "Authorization": f"{AUTH_SCHEME} {token}",
        "Accept": "application/json",
    }

    ctx = build_ssl_context(insecure)
    req = request.Request(url, headers=headers)

    with request.urlopen(req, timeout=timeout, context=ctx) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw)


def fetch_instances(base_url, token, timeout, insecure=False):
    """
    Fetch Controller instances (cluster topology).
    Returns a list of instance dicts.
    """
    try:
        data = api_get(base_url, "/api/v2/instances/", token, timeout, insecure)
        # Typical AWX/AAP shape: { "results": [ {instance}, ... ], ... }
        if isinstance(data, dict) and isinstance(data.get("results"), list):
            return data["results"], None
        # If it's already a list, just return it.
        if isinstance(data, list):
            return data, None
        return [], "Unexpected /api/v2/instances/ format"
    except error.HTTPError as e:
        return [], f"HTTP {e.code} on /instances/: {e.reason}"
    except error.URLError as e:
        return [], f"URL error on /instances/: {e.reason}"
    except Exception as e:
        return [], f"Exception on /instances/: {e}"


def fetch_running_jobs(base_url, token, timeout, insecure=False, page_size=DEFAULT_PAGE_SIZE):
    """
    Fetch running jobs from Controller.

    Returns (jobs, error_message_str_or_None)
    """
    query = {
        "status": "running",
        "order_by": "-started",
        "page_size": page_size,
    }
    try:
        data = api_get(base_url, "/api/v2/jobs/", token, timeout, insecure, query=query)
        results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(results, list):
            return [], "Unexpected /api/v2/jobs/ format"
        return results, None
    except error.HTTPError as e:
        return [], f"HTTP {e.code} on /jobs/: {e.reason}"
    except error.URLError as e:
        return [], f"URL error on /jobs/: {e.reason}"
    except Exception as e:
        return [], f"Exception on /jobs/: {e}"


# ---------------------------------------------------------------------------
# Curses dashboard
# ---------------------------------------------------------------------------

def run_dashboard(
    stdscr,
    base_url,
    token,
    timeout,
    poll_interval,
    insecure=False,
    page_size=DEFAULT_PAGE_SIZE,
):
    curses.curs_set(0)
    stdscr.nodelay(True)
    curses.start_color()

    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)   # good
    curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # warn
    curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)     # bad
    curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)    # unknown/info
    curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLACK)   # text

    color_for_class = {
        "good": curses.color_pair(1),
        "warn": curses.color_pair(2),
        "bad": curses.color_pair(3),
        "unknown": curses.color_pair(4),
    }

    instances = []
    inst_error = None
    jobs = []
    jobs_error = None

    executor = ThreadPoolExecutor(max_workers=2)

    try:
        try:
            while True:
                loop_start = time.time()
                h, w = stdscr.getmaxyx()
                stdscr.erase()

                # ------------------------------------------------------------------
                # Fetch data (instances + running jobs), potentially in parallel
                # ------------------------------------------------------------------
                futures = {
                    executor.submit(fetch_instances, base_url, token, timeout, insecure): "instances",
                    executor.submit(fetch_running_jobs, base_url, token, timeout, insecure, page_size): "jobs",
                }

                for fut in as_completed(futures):
                    what = futures[fut]
                    try:
                        result, err = fut.result()
                    except Exception as e:
                        result, err = [], f"Exception while fetching {what}: {e}"

                    if what == "instances":
                        instances, inst_error = result, err
                    else:
                        jobs, jobs_error = result, err

                # ------------------------------------------------------------------
                # Header
                # ------------------------------------------------------------------
                now = time.strftime("%Y-%m-%d %H:%M:%S")
                title = "AAP Environment Monitor (Controller)"
                header = f"{title}  {now}  host:{MONITOR_HOST}"
                stdscr.addstr(0, 0, header[:w - 1], curses.color_pair(5))

                # Summary line
                good_i = warn_i = bad_i = unknown_i = 0
                for inst in instances:
                    cls = classify_instance(inst)
                    if cls == "good":
                        good_i += 1
                    elif cls == "warn":
                        warn_i += 1
                    elif cls == "bad":
                        bad_i += 1
                    else:
                        unknown_i += 1

                running_jobs = len(jobs)
                summary = (
                    f"Instances: G={good_i} W={warn_i} B={bad_i} U={unknown_i}  "
                    f"Running jobs: {running_jobs}"
                )
                stdscr.addstr(1, 0, summary[:w - 1], curses.color_pair(5))

                # Legend
                legend = "Legend: GOOD ●   WARN ●   BAD ●   UNKNOWN ●"
                stdscr.addstr(2, 0, legend[:w - 1], curses.color_pair(5))
                stdscr.addstr(2, len("Legend: "), "GOOD ●", color_for_class["good"])
                off = len("Legend: GOOD ●   ")
                stdscr.addstr(2, off, "WARN ●", color_for_class["warn"])
                off += len("WARN ●   ")
                stdscr.addstr(2, off, "BAD ●", color_for_class["bad"])
                off += len("BAD ●   ")
                stdscr.addstr(2, off, "UNKNOWN ●", color_for_class["unknown"])

                row = 4

                # ------------------------------------------------------------------
                # Topology section (instances)
                # ------------------------------------------------------------------
                if row < h:
                    stdscr.addstr(row, 0, "Topology (instances):", curses.color_pair(5))
                    row += 1

                # Determine name width dynamically
                inst_names = [str(i.get("hostname") or i.get("node") or i.get("id") or "?")
                              for i in instances]
                max_name_len = max((len(n) for n in inst_names), default=4)
                name_width = max(max_name_len, 8)

                for inst, name in zip(instances, inst_names):
                    if row >= h:
                        break
                    cls = classify_instance(inst)
                    status_str = cls.upper()
                    # try to include node_type or node_state if present
                    node_type = inst.get("node_type") or inst.get("type") or ""
                    node_state = inst.get("node_state") or ""
                    extra = node_type or node_state
                    line = f"  {name:{name_width}} [{status_str:7}]"
                    if extra:
                        line += f"  ({extra})"
                    stdscr.addstr(row, 0, line[:w - 1], color_for_class.get(cls, curses.color_pair(5)))
                    row += 1

                if inst_error and row < h:
                    stdscr.addstr(row, 2, f"instances error: {inst_error}"[:w - 3], curses.color_pair(4))
                    row += 1

                # ------------------------------------------------------------------
                # Running jobs section
                # ------------------------------------------------------------------
                if row < h:
                    stdscr.addstr(row, 0, "Running jobs:", curses.color_pair(5))
                    row += 1

                # Table header
                if row < h:
                    header_line = "  ID    Elapsed    User           Status   Name"
                    stdscr.addstr(row, 0, header_line[:w - 1], curses.color_pair(5))
                    row += 1

                # Show up to MAX_JOBS_DISPLAY jobs
                for job in jobs[:MAX_JOBS_DISPLAY]:
                    if row >= h:
                        break

                    jid = job.get("id")
                    status = job.get("status") or "?"
                    elapsed = job.get("elapsed")

                    # if elapsed is 0 or None, try to compute from started timestamp
                    if not elapsed:
                        started = parse_iso8601(job.get("started"))
                        if started:
                            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
                        else:
                            elapsed = None

                    elapsed_str = format_elapsed(elapsed)

                    # user: from summary_fields if available
                    user = "?"
                    sf = job.get("summary_fields") or {}
                    u = sf.get("created_by") or {}
                    user = u.get("username") or u.get("first_name") or user

                    name = job.get("name") or job.get("job_template", "")
                    name = str(name)

                    cls = classify_status_text(status)

                    line = f"  {jid:4}  {elapsed_str:9}  {user:12.12}  {status:7}  {name}"
                    stdscr.addstr(row, 0, line[:w - 1], color_for_class.get(cls, curses.color_pair(5)))
                    row += 1

                if jobs_error and row < h:
                    stdscr.addstr(row, 2, f"jobs error: {jobs_error}"[:w - 3], curses.color_pair(4))
                    row += 1

                stdscr.refresh()

                # ------------------------------------------------------------------
                # Handle keypress and pacing
                # ------------------------------------------------------------------
                remaining = poll_interval - (time.time() - loop_start)
                end_wait = time.time() + max(0.0, remaining)
                while time.time() < end_wait:
                    ch = stdscr.getch()
                    if ch in (ord("q"), ord("Q"), 27):  # q or ESC
                        return
                    time.sleep(0.05)
        except KeyboardInterrupt:
            # clean exit on Ctrl-C
            return
    finally:
        executor.shutdown(wait=False)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="AAP Controller environment monitor (topology + running jobs)."
    )
    p.add_argument(
        "base_url",
        help="Base URL of the AAP Controller (e.g. https://aap.example.com)",
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
        default=DEFAULT_TIMEOUT,
        help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT}).",
    )
    p.add_argument(
        "--poll-interval",
        type=float,
        default=DEFAULT_POLL_INTERVAL,
        help=f"Polling interval in seconds (default: {DEFAULT_POLL_INTERVAL}).",
    )
    p.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help=f"Max running jobs to request from API (default: {DEFAULT_PAGE_SIZE}).",
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
            args.base_url,
            args.token,
            args.timeout,
            args.poll_interval,
            args.insecure,
            args.page_size,
        )
    except KeyboardInterrupt:
        # Extra guard; avoid traceback on Ctrl-C.
        pass


if __name__ == "__main__":
    main()

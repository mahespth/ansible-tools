#!/usr/bin/env python3
"""
AAP Environment Monitor (Controller Dashboard)
=============================================

Description
-----------
Curses-based terminal dashboard to monitor a Red Hat Ansible Automation Platform
(AAP) 2.5 Controller environment (via Automation Gateway or directly).

It:
- Connects to an AAP Controller using a Bearer token.
- Polls the Controller every few seconds.
- Shows Controller topology (instances) and their health using a colored
  GOOD/WARN/BAD/UNKNOWN scheme, including:
    - Node type/state
    - Memory
    - Number of forks
    - Last health check time (when available)
    - Error reason if an instance reports errors (e.g. "Failed to connect to redis")
- Shows the last N jobs (configurable) including:
    - Job ID
    - Name
    - User who launched them
    - How long they have been running / ran for
- Keeps recent jobs on screen even after they finish; their colour/status
  changes as they complete:
    - Running jobs: highlighted with reverse video.
    - Successful/completed jobs: dimmed grey.
    - Failed/error jobs: red.
- Jobs are displayed from newest to oldest by job ID.
- Uses only Python standard library modules (suitable for typical AAP installs).

Assumed API Endpoints (AAP 2.5)
-------------------------------
Base URL example (usually the Gateway):

    https://<gateway server name>/

Controller endpoints:

- Instances (topology):
    GET /api/controller/v2/instances/

- Recent jobs (all statuses):
    GET /api/controller/v2/jobs/?order_by=-started&page_size=N

Authentication
--------------
The script expects a Bearer token and sends:

    Authorization: Bearer <YOUR_TOKEN>

If your environment uses a different auth header (e.g. "Token"), adjust
AUTH_SCHEME below.

Color / Status Scheme
---------------------
Instances:
- GOOD   (green)   -> enabled, no (or empty) "errors" field
- WARN   (yellow)  -> enabled but "errors" is present/non-empty, or capacity is 0
- BAD    (red)     -> disabled, or a fatal-looking "errors" field
- UNKNOWN (cyan)   -> anything else / unexpected data

Jobs:
- GOOD   (green)   -> generic good state
- BAD    (red)     -> any status containing "fail" or "error"
- Running jobs: GOOD colour + reverse video (highlighted).
- Successful/completed: dim grey (white + DIM).
- WARN / UNKNOWN   -> available if you extend mappings.

Usage
-----
    ./aap_monitor.py \
        --token 'YOUR_BEARER_TOKEN' \
        https://gateway.example.com

Options
-------
Positional:
  base_url             Base URL of the AAP Gateway/Controller,
                       e.g. https://gateway.example.com

Flags:
  -t, --token          Bearer token for Authorization header.
  --timeout            Request timeout (seconds). Default: 5.
  --poll-interval      Polling interval (seconds). Default: 2.
  --insecure, -k       Skip TLS certificate verification (self-signed/lab).
  --page-size          How many recent jobs to fetch (and keep on screen).
                       Default: 50 (displayed up to MAX_JOBS_DISPLAY rows).

Controls
--------
- Press 'q' or ESC to quit the dashboard.
- Press Ctrl-C to exit cleanly (no traceback).

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
    Map arbitrary *job* or *generic* status text to one of:
    good, warn, bad, unknown.
    """
    if status is None:
        return "unknown"

    s = str(status).lower()

    # Clearly good / healthy / running / done
    if s in (
        "good", "ok", "okay", "healthy", "green",
        "running", "successful", "completed", "finished"
    ):
        return "good"

    # Warnings / degraded
    if any(word in s for word in ("warn", "degrad", "yellow")):
        return "warn"

    # Failures / errors
    if any(word in s for word in ("bad", "down", "error", "fail", "failed", "critical", "red")):
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

    # Explicitly disabled -> BAD
    if enabled is False:
        return "bad"

    # Non-empty errors -> WARN/BAD
    if errors:
        err_str = str(errors).lower()
        if any(word in err_str for word in ("unreachable", "failed", "error", "down", "offline")):
            return "bad"
        return "warn"

    # Capacity 0 but enabled -> WARN
    if capacity == 0:
        return "warn"

    # If node_state exists, use it as a hint
    if node_state:
        cls = classify_status_text(node_state)
        if cls != "unknown":
            return cls

    # Enabled or unknown but no errors -> GOOD
    if enabled in (True, None):
        return "good"

    return "unknown"


def parse_iso8601(dt_str):
    """
    Parse an ISO-8601-ish datetime string into a datetime.
    Returns None on failure.
    """
    if not dt_str:
        return None
    try:
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

    AAP 2.5 (via Gateway) endpoint:
      GET /api/controller/v2/instances/

    Returns (instances_list, error_str_or_None)
    """
    try:
        data = api_get(base_url, "/api/controller/v2/instances/", token, timeout, insecure)
        if isinstance(data, dict) and isinstance(data.get("results"), list):
            return data["results"], None
        if isinstance(data, list):
            return data, None
        return [], "Unexpected /api/controller/v2/instances/ format"
    except error.HTTPError as e:
        return [], f"HTTP {e.code} on /instances/: {e.reason}"
    except error.URLError as e:
        return [], f"URL error on /instances/: {e.reason}"
    except Exception as e:
        return [], f"Exception on /instances/: {e}"


def fetch_recent_jobs(base_url, token, timeout, insecure=False, page_size=DEFAULT_PAGE_SIZE):
    """
    Fetch recent jobs (all statuses) from Controller.

    AAP 2.5 (via Gateway) endpoint:
      GET /api/controller/v2/jobs/?order_by=-started&page_size=...

    Returns (jobs_list, error_str_or_None)
    """
    query = {
        "order_by": "-started",
        "page_size": page_size,
    }
    try:
        data = api_get(base_url, "/api/controller/v2/jobs/", token, timeout, insecure, query=query)
        results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(results, list):
            return [], "Unexpected /api/controller/v2/jobs/ format"
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
    curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLACK)   # text / grey-ish

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
                # Fetch data (instances + recent jobs), in parallel
                # ------------------------------------------------------------------
                futures = {
                    executor.submit(fetch_instances, base_url, token, timeout, insecure): "instances",
                    executor.submit(fetch_recent_jobs, base_url, token, timeout, insecure, page_size): "jobs",
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

                running_jobs = sum(
                    1 for j in jobs
                    if str(j.get("status", "")).lower() == "running"
                )
                failed_jobs = sum(
                    1 for j in jobs
                    if classify_status_text(j.get("status")) == "bad"
                )

                summary = (
                    f"Instances: G={good_i} W={warn_i} B={bad_i} U={unknown_i}  "
                    f"Recent jobs: {len(jobs)}  running={running_jobs}  failed={failed_jobs}"
                )
                stdscr.addstr(1, 0, summary[:w - 1], curses.color_pair(5))

                row = 3

                # ------------------------------------------------------------------
                # Topology section (instances)
                # ------------------------------------------------------------------
                if row < h:
                    stdscr.addstr(row, 0, "Topology (instances):", curses.color_pair(5))
                    row += 1

                inst_names = [
                    str(i.get("hostname") or i.get("node") or i.get("id") or "?")
                    for i in instances
                ]
                max_name_len = max((len(n) for n in inst_names), default=4)
                name_width = max(max_name_len, 8)

                for inst, name in zip(instances, inst_names):
                    if row >= h:
                        break

                    cls = classify_instance(inst)
                    status_str = cls.upper()
                    node_type = inst.get("node_type") or inst.get("type") or ""
                    node_state = inst.get("node_state") or ""

                    # First line: name, status, type/state
                    extra_bits = []
                    if node_type:
                        extra_bits.append(node_type)
                    if node_state:
                        extra_bits.append(node_state)
                    extra = ", ".join(extra_bits)

                    line = f"  {name:{name_width}} [{status_str:7}]"
                    if extra:
                        line += f"  ({extra})"
                    stdscr.addstr(
                        row, 0, line[:w - 1],
                        color_for_class.get(cls, curses.color_pair(5))
                    )
                    row += 1

                    # Second line: memory / forks / last health check
                    if row >= h:
                        break

                    memory = inst.get("memory") or inst.get("mem")
                    forks = inst.get("forks")
                    if forks is None:
                        # capacity is often "number of forks" equivalent
                        forks = inst.get("capacity")
                    last_health = (
                        inst.get("last_health_check")
                        or inst.get("heartbeat")
                        or inst.get("last_isolated_check")
                    )

                    details = []
                    if memory is not None:
                        details.append(f"mem={memory}")
                    if forks is not None:
                        details.append(f"forks={forks}")
                    if last_health:
                        last_str = str(last_health)
                        if len(last_str) > 32:
                            last_str = last_str[:29] + "..."
                        details.append(f"last={last_str}")

                    if details:
                        det_line = "    " + "  ".join(details)
                        stdscr.addstr(
                            row, 0,
                            det_line[:w - 1],
                            color_for_class.get(cls, curses.color_pair(5)),
                        )
                        row += 1

                    # Third line: error reason from instance.errors
                    errors_field = inst.get("errors")
                    if errors_field and row < h:
                        err_str = str(errors_field)
                        # Normalise whitespace and trim to fit
                        err_str = " ".join(err_str.split())
                        max_err_width = max(10, w - 8)
                        if len(err_str) > max_err_width:
                            err_str = err_str[: max_err_width - 3] + "..."
                        err_line = f"    error: {err_str}"
                        stdscr.addstr(
                            row, 0,
                            err_line[:w - 1],
                            color_for_class.get(cls, curses.color_pair(5)),
                        )
                        row += 1

                if inst_error and row < h:
                    stdscr.addstr(
                        row, 2,
                        f"instances error: {inst_error}"[:w - 3],
                        curses.color_pair(4),
                    )
                    row += 1

                # ------------------------------------------------------------------
                # Recent jobs section (last N by job ID, newest first)
                # ------------------------------------------------------------------
                if row < h:
                    stdscr.addstr(
                        row, 0,
                        f"Recent jobs (last {min(page_size, MAX_JOBS_DISPLAY)} shown, newest first by ID):",
                        curses.color_pair(5),
                    )
                    row += 1

                if row < h:
                    header_line = "  ID    Elapsed    User           Status   Name"
                    stdscr.addstr(row, 0, header_line[:w - 1], curses.color_pair(5))
                    row += 1

                # Sort jobs by integer ID descending so newest IDs are first
                def job_sort_key(j):
                    try:
                        return int(j.get("id", 0))
                    except Exception:
                        return 0

                jobs_sorted = sorted(jobs, key=job_sort_key, reverse=True)

                for job in jobs_sorted[:MAX_JOBS_DISPLAY]:
                    if row >= h:
                        break

                    jid = job.get("id")
                    status = job.get("status") or "?"
                    status_str = str(status)
                    status_lower = status_str.lower()
                    elapsed = job.get("elapsed")

                    # For running jobs, elapsed may be 0; compute from started if needed
                    try:
                        elapsed_val = float(elapsed) if elapsed is not None else 0.0
                    except Exception:
                        elapsed_val = 0.0

                    if elapsed is None or elapsed_val <= 0.0:
                        started = parse_iso8601(job.get("started"))
                        if started:
                            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
                        else:
                            elapsed = None

                    elapsed_str = format_elapsed(elapsed)

                    sf = job.get("summary_fields") or {}
                    created_by = sf.get("created_by") or {}
                    user = created_by.get("username") or created_by.get("first_name") or "?"

                    name = str(job.get("name") or job.get("job_template", ""))

                    cls = classify_status_text(status_str)
                    base_style = color_for_class.get(cls, curses.color_pair(5))

                    # Style tweaks:
                    # - Running: reverse video highlight
                    # - Successful/completed: dim grey (white + DIM)
                    # - Failed/error: red (cls == 'bad')
                    if status_lower == "running":
                        style = color_for_class["good"] | curses.A_REVERSE
                    elif status_lower in ("successful", "completed", "finished"):
                        style = curses.color_pair(5) | curses.A_DIM
                    elif cls == "bad":
                        style = color_for_class["bad"]
                    else:
                        style = base_style

                    line = f"  {jid:4}  {elapsed_str:9}  {user:12.12}  {status_str:7}  {name}"
                    stdscr.addstr(
                        row, 0,
                        line[:w - 1],
                        style,
                    )
                    row += 1

                if jobs_error and row < h:
                    stdscr.addstr(
                        row, 2,
                        f"jobs error: {jobs_error}"[:w - 3],
                        curses.color_pair(4),
                    )
                    row += 1

                stdscr.refresh()

                # ------------------------------------------------------------------
                # Key handling / pacing
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
        description="AAP Controller environment monitor (topology + recent jobs)."
    )
    p.add_argument(
        "base_url",
        help="Base URL of the AAP Gateway/Controller (e.g. https://gateway.example.com)",
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
        help=f"How many recent jobs to fetch (default: {DEFAULT_PAGE_SIZE}).",
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
        # avoid traceback on Ctrl-C
        pass


if __name__ == "__main__":
    main()

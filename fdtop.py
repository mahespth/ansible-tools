#!/usr/bin/env python3

"""
  Monitor the number of fds of processes
  Steve Maher
"""

import argparse
import os
import sys
import time
from datetime import datetime


PROC_DIR = "/proc"


def is_pid(name):
    return name.isdigit()


def read_exe(pid):
    exe_path = os.path.join(PROC_DIR, pid, "exe")

    try:
        return os.readlink(exe_path)
    except PermissionError:
        return "[permission denied]"
    except FileNotFoundError:
        return "[exited]"
    except OSError as e:
        return f"[error: {e.strerror}]"


def count_fds(pid):
    fd_path = os.path.join(PROC_DIR, pid, "fd")

    try:
        return len(os.listdir(fd_path))
    except PermissionError:
        return None
    except FileNotFoundError:
        return None
    except OSError:
        return None


def get_process_fd_counts():
    results = []

    try:
        proc_entries = os.listdir(PROC_DIR)
    except OSError as e:
        print(f"Unable to read {PROC_DIR}: {e}", file=sys.stderr)
        sys.exit(1)

    for pid in proc_entries:
        if not is_pid(pid):
            continue

        fd_count = count_fds(pid)
        if fd_count is None:
            continue

        exe = read_exe(pid)

        results.append({
            "pid": int(pid),
            "fd_count": fd_count,
            "exe": exe,
        })

    results.sort(key=lambda x: x["fd_count"], reverse=True)
    return results


def trend_symbol(pid, current_count, previous_counts):
    previous = previous_counts.get(pid)

    if previous is None:
        return "+"

    if previous == 0:
        if current_count > 0:
            return ">>"
        return "="

    diff = current_count - previous
    pct_change = abs(diff) / previous

    if diff > 0:
        return ">>" if pct_change > 0.05 else ">"
    if diff < 0:
        return "<<" if pct_change > 0.05 else "<"

    return "="


def clear_screen():
    # ANSI clear screen + cursor home
    print("\033[2J\033[H", end="")


def truncate(value, width):
    value = str(value)
    if len(value) <= width:
        return value

    if width <= 3:
        return value[:width]

    return value[:width - 3] + "..."


def print_table(rows, previous_counts, top_n, delay):
    clear_screen()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"FD top - {now} | delay={delay}s | top={top_n}")
    print("-" * 120)
    print(f"{'PID':>8}  {'FDS':>8}  {'TREND':>5}  EXECUTABLE")
    print("-" * 120)

    for row in rows[:top_n]:
        pid = row["pid"]
        fd_count = row["fd_count"]
        exe = row["exe"]
        trend = trend_symbol(pid, fd_count, previous_counts)

        print(
            f"{pid:>8}  "
            f"{fd_count:>8}  "
            f"{trend:>5}  "
            f"{truncate(exe, 90)}"
        )

    print("-" * 120)
    print("Trend: + new | = same | > more | < less | >> more than 5% increase | << more than 5% decrease")
    print("Press Ctrl+C to quit.")


def main():
    parser = argparse.ArgumentParser(
        description="Show top Linux processes by number of open file descriptors."
    )

    parser.add_argument(
        "-d",
        "--delay",
        type=float,
        default=2.0,
        help="Refresh delay in seconds. Default: 2.0"
    )

    parser.add_argument(
        "-n",
        "--top",
        type=int,
        default=20,
        help="Number of processes to show. Default: 20"
    )

    args = parser.parse_args()

    if args.delay <= 0:
        print("Delay must be greater than zero.", file=sys.stderr)
        sys.exit(2)

    if args.top <= 0:
        print("Top value must be greater than zero.", file=sys.stderr)
        sys.exit(2)

    previous_counts = {}

    try:
        while True:
            rows = get_process_fd_counts()

            print_table(
                rows=rows,
                previous_counts=previous_counts,
                top_n=args.top,
                delay=args.delay,
            )

            previous_counts = {
                row["pid"]: row["fd_count"]
                for row in rows
            }

            time.sleep(args.delay)

    except KeyboardInterrupt:
        clear_screen()
        print("Stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()

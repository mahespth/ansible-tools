#!/usr/bin/env python3

"""
 sshaskpass.py: Steve Maher, sshaskpass clone for debugging where I cant install the original pacakge.
"""
import argparse
import os
import pty
import re
import select
import signal
import sys

DEFAULT_PROMPT = r"[Pp]assword[: ]*$"


def die(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    sys.exit(code)


def read_password(args: argparse.Namespace) -> str:
    sources = sum(
        1 for x in (args.password is not None, args.env is True, args.file is not None, args.fd is not None)
        if x
    )
    if sources != 1:
        die("Exactly one of -p, -e, -f, or -d must be supplied")

    if args.password is not None:
        return args.password

    if args.env:
        pw = os.environ.get("SSHPASS")
        if pw is None:
            die("SSHPASS environment variable is not set")
        return pw

    if args.file is not None:
        try:
            with open(args.file, "r", encoding="utf-8", errors="replace") as f:
                return f.readline().rstrip("\r\n")
        except OSError as exc:
            die(f"Failed to read password file: {exc}")

    if args.fd is not None:
        try:
            with os.fdopen(args.fd, "r", encoding="utf-8", errors="replace", closefd=False) as f:
                return f.readline().rstrip("\r\n")
        except OSError as exc:
            die(f"Failed to read password from fd {args.fd}: {exc}")

    die("No password source provided")
    return ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pysshpass",
        add_help=True,
        description="Minimal sshpass-like wrapper in Python"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-p", dest="password", help="Password on command line")
    group.add_argument("-e", dest="env", action="store_true", help="Read password from SSHPASS env var")
    group.add_argument("-f", dest="file", help="Read password from file")
    group.add_argument("-d", dest="fd", type=int, help="Read password from file descriptor")

    parser.add_argument(
        "-P",
        dest="prompt",
        default=DEFAULT_PROMPT,
        help=f"Prompt regex to match (default: {DEFAULT_PROMPT!r})"
    )
    parser.add_argument(
        "-v",
        dest="verbose",
        action="store_true",
        help="Verbose logging to stderr"
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command to execute"
    )

    args = parser.parse_args()

    if not args.command:
        die("No command specified")

    if args.command and args.command[0] == "--":
        args.command = args.command[1:]

    if not args.command:
        die("No command specified after --")

    return args


def debug(enabled: bool, msg: str) -> None:
    if enabled:
        print(f"[pysshpass] {msg}", file=sys.stderr)


def main() -> int:
    args = parse_args()
    password = read_password(args)
    prompt_re = re.compile(args.prompt.encode())

    pid, master_fd = pty.fork()

    if pid == 0:
        try:
            os.execvp(args.command[0], args.command)
        except OSError as exc:
            print(f"exec failed: {exc}", file=sys.stderr)
            os._exit(127)

    sent_password = False
    buffered = b""

    def forward_signal(signum, _frame):
        try:
            os.kill(pid, signum)
        except ProcessLookupError:
            pass

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT):
        signal.signal(sig, forward_signal)

    try:
        while True:
            rlist, _, _ = select.select([master_fd], [], [], 0.2)

            if master_fd in rlist:
                try:
                    data = os.read(master_fd, 4096)
                except OSError:
                    data = b""

                if not data:
                    break

                try:
                    os.write(sys.stdout.fileno(), data)
                except OSError:
                    pass

                buffered = (buffered + data)[-8192:]

                if not sent_password and prompt_re.search(buffered):
                    debug(args.verbose, "Password prompt detected, sending password")
                    os.write(master_fd, password.encode() + b"\n")
                    sent_password = True

            ended_pid, status = os.waitpid(pid, os.WNOHANG)
            if ended_pid == pid:
                if os.WIFEXITED(status):
                    return os.WEXITSTATUS(status)
                if os.WIFSIGNALED(status):
                    return 128 + os.WTERMSIG(status)
                return 1

        _, status = os.waitpid(pid, 0)
        if os.WIFEXITED(status):
            return os.WEXITSTATUS(status)
        if os.WIFSIGNALED(status):
            return 128 + os.WTERMSIG(status)
        return 1

    finally:
        try:
            os.close(master_fd)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())

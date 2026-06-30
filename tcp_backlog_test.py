#!/usr/bin/env python3

"""
  tcp backlog tester
  Steve Maher
  
"""
import argparse
import errno
import socket
import sys
import time
from collections import Counter


def make_socket(host, port, timeout):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)

    # Keep the socket open and make drops easier to detect later
    s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

    try:
        s.connect((host, port))
        s.setblocking(False)
        return s, None
    except Exception as e:
        try:
            s.close()
        except Exception:
            pass
        return None, e


def socket_is_alive(s):
    """
    Non-destructive liveness check.
    Returns False if the peer has closed/reset the connection.
    """
    try:
        data = s.recv(1, socket.MSG_PEEK | socket.MSG_DONTWAIT)
        if data == b"":
            return False
        return True

    except BlockingIOError:
        return True

    except socket.error as e:
        if e.errno in (
            errno.EAGAIN,
            errno.EWOULDBLOCK,
        ):
            return True
        return False

    except Exception:
        return False


def progress_bar(current, target, width=40):
    pct = 0 if target == 0 else current / target
    filled = int(width * pct)
    bar = "#" * filled + "-" * (width - filled)
    return f"[{bar}] {pct * 100:6.2f}%  {current}/{target}"


def print_status(live, target, attempts, successes, drops, errors, last_error=None):
    msg = (
        f"\r{progress_bar(live, target)}  "
        f"attempts={attempts} "
        f"ok={successes} "
        f"drops={drops} "
        f"errors={sum(errors.values())}"
    )

    if last_error:
        msg += f"  last_error={last_error}"

    sys.stdout.write(msg)
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(
        description="Open and hold TCP connections until a target live connection count is reached."
    )

    parser.add_argument("host", help="Target host or IP")
    parser.add_argument("port", type=int, help="Target TCP port")
    parser.add_argument("count", type=int, help="Required number of live TCP connections")

    parser.add_argument(
        "--timeout",
        type=float,
        default=0.2,
        help="TCP connect timeout in seconds. Default: 0.2",
    )

    parser.add_argument(
        "--retry-delay",
        type=float,
        default=0.05,
        help="Delay between failed connection attempts. Default: 0.05",
    )

    parser.add_argument(
        "--check-every",
        type=int,
        default=25,
        help="Check existing sockets for drops every N attempts. Default: 25",
    )

    parser.add_argument(
        "--hold",
        action="store_true",
        help="After reaching the requested count, keep the sockets open until Ctrl-C.",
    )

    args = parser.parse_args()

    connections = []
    errors = Counter()

    attempts = 0
    successes = 0
    drops = 0
    last_error = None

    print(
        f"Target: {args.host}:{args.port}, required live connections: {args.count}, "
        f"timeout: {args.timeout}s"
    )

    try:
        while len(connections) < args.count:
            attempts += 1

            s, err = make_socket(args.host, args.port, args.timeout)

            if s is not None:
                connections.append(s)
                successes += 1
                last_error = None
            else:
                err_name = type(err).__name__
                err_text = str(err) or err_name
                errors[err_text] += 1
                last_error = err_text
                time.sleep(args.retry_delay)

            if attempts % args.check_every == 0:
                alive = []
                for conn in connections:
                    if socket_is_alive(conn):
                        alive.append(conn)
                    else:
                        drops += 1
                        try:
                            conn.close()
                        except Exception:
                            pass

                connections = alive

            print_status(
                live=len(connections),
                target=args.count,
                attempts=attempts,
                successes=successes,
                drops=drops,
                errors=errors,
                last_error=last_error,
            )

        print()
        print(f"Reached required live connection count: {len(connections)}/{args.count}")

        if args.hold:
            print("Holding connections open. Press Ctrl-C to stop.")
            while True:
                alive = []
                for conn in connections:
                    if socket_is_alive(conn):
                        alive.append(conn)
                    else:
                        drops += 1
                        try:
                            conn.close()
                        except Exception:
                            pass

                connections = alive

                print_status(
                    live=len(connections),
                    target=args.count,
                    attempts=attempts,
                    successes=successes,
                    drops=drops,
                    errors=errors,
                    last_error=None,
                )

                time.sleep(1)

                # If any sockets dropped during hold mode, reconnect them
                while len(connections) < args.count:
                    attempts += 1
                    s, err = make_socket(args.host, args.port, args.timeout)

                    if s is not None:
                        connections.append(s)
                        successes += 1
                    else:
                        err_text = str(err) or type(err).__name__
                        errors[err_text] += 1
                        last_error = err_text
                        time.sleep(args.retry_delay)

                    print_status(
                        live=len(connections),
                        target=args.count,
                        attempts=attempts,
                        successes=successes,
                        drops=drops,
                        errors=errors,
                        last_error=last_error,
                    )

    except KeyboardInterrupt:
        print()
        print("Interrupted.")

    finally:
        for s in connections:
            try:
                s.close()
            except Exception:
                pass

        print()
        print("Summary")
        print("-------")
        print(f"Attempts:       {attempts}")
        print(f"Successful:     {successes}")
        print(f"Dropped:        {drops}")
        print(f"Live at finish: {len(connections)}")

        if errors:
            print()
            print("Errors:")
            for err, count in errors.most_common():
                print(f"  {count:6d}  {err}")


if __name__ == "__main__":
    main()

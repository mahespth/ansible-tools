
#!/usr/bin/env python3

"""
author: Steve Maher

IOS log filter take ios logs as input and translate to the hostname from hosts / services files.

"""

import argparse
import ipaddress
import re
import sys
from contextlib import nullcontext


def load_hosts(filename):
    """Load IP-to-hostname mappings from /etc/hosts format."""
    hosts = {}

    with open(filename, encoding="utf-8") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()

            if not line:
                continue

            fields = line.split()
            if len(fields) < 2:
                continue

            try:
                ip = str(ipaddress.ip_address(fields[0]))
            except ValueError:
                continue

            # First hostname is canonical
            hosts[ip] = fields[1]

    return hosts


def load_services(filename):
    """Load port-to-service mappings from /etc/services format."""
    services = {}

    with open(filename, encoding="utf-8") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()

            if not line:
                continue

            fields = line.split()
            if len(fields) < 2:
                continue

            name = fields[0]
            port_proto = fields[1].split("/", 1)

            if len(port_proto) != 2:
                continue

            port, protocol = port_proto
            if port.isdigit():
                services[(port, protocol.lower())] = name

    return services


# Cisco IOS IP(port) pattern
PATTERN = re.compile(
    r"(?<![\w.])"
    r"(?P<ip>(?:\d{1,3}\.){3}\d{1,3})"
    r"\((?P<port>\d+)\)"
)


def main():
    parser = argparse.ArgumentParser(
        description="Translate Cisco IOS IPs and ports"
    )

    parser.add_argument(
        "-H", "--hosts",
        default="/etc/hosts",
        help="Hosts file (default: /etc/hosts)"
    )

    parser.add_argument(
        "-S", "--services",
        default="/etc/services",
        help="Services file (default: /etc/services)"
    )

    parser.add_argument(
        "-f", "--file",
        help="Read logs from file instead of stdin"
    )

    args = parser.parse_args()

    try:
        hosts = load_hosts(args.hosts)
        services = load_services(args.services)

        source = (
            open(args.file, encoding="utf-8", errors="replace")
            if args.file else nullcontext(sys.stdin)
        )

        with source as lines:
            for line in lines:
                # IOS ACL protocol, e.g. "denied tcp"
                proto_match = re.search(
                    r"\b(tcp|udp)\b", line, re.IGNORECASE
                )
                protocol = (
                    proto_match.group(1).lower()
                    if proto_match else None
                )

                def replace_match(match):
                    ip = match.group("ip")
                    port = match.group("port")

                    hostname = hosts.get(ip, ip)

                    if protocol:
                        service = services.get(
                            (port, protocol), port
                        )
                    else:
                        service = port

                    return f"{hostname}({service})"

                sys.stdout.write(PATTERN.sub(replace_match, line))

    except (OSError, UnicodeError) as e:
        parser.exit(1, f"Error: {e}\n")


if __name__ == "__main__":
    main()

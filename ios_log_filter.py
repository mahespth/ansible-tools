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


ICMP_TYPES = {
    (0, 0): "echo-reply",
    (3, 0): "network-unreachable",
    (3, 1): "host-unreachable",
    (3, 2): "protocol-unreachable",
    (3, 3): "port-unreachable",
    (3, 4): "fragmentation-needed",
    (3, 5): "source-route-failed",
    (5, 0): "redirect-network",
    (5, 1): "redirect-host",
    (8, 0): "echo-request",
    (9, 0): "router-advertisement",
    (10, 0): "router-solicitation",
    (11, 0): "ttl-exceeded",
    (11, 1): "fragment-reassembly-time-exceeded",
    (12, 0): "parameter-problem",
    (13, 0): "timestamp-request",
    (14, 0): "timestamp-reply",
    (17, 0): "address-mask-request",
    (18, 0): "address-mask-reply",
}


def load_hosts(filename):
    hosts = {}

    with open(filename, encoding="utf-8") as f:
        for line in f:
            fields = line.split("#", 1)[0].split()

            if len(fields) < 2:
                continue

            try:
                ip = str(ipaddress.ip_address(fields[0]))
            except ValueError:
                continue

            hosts[ip] = fields[1]

    return hosts


def load_services(filename):
    services = {}

    with open(filename, encoding="utf-8") as f:
        for line in f:
            fields = line.split("#", 1)[0].split()

            if len(fields) < 2 or "/" not in fields[1]:
                continue

            port, protocol = fields[1].split("/", 1)

            if port.isdigit():
                services[(port, protocol.lower())] = fields[0]

    return services


# Match IPv4 address with optional (port) or (type/code)
IP_PATTERN = re.compile(
    r"(?<![\w.])"
    r"(?P<ip>(?:\d{1,3}\.){3}\d{1,3})"
    r"(?:\((?P<value>\d+(?:/\d+)?)\))?"
    r"(?![\w.])"
)

PROTOCOL_PATTERN = re.compile(
    r"\b(tcp|udp|icmp)\b",
    re.IGNORECASE
)


def translate(line, hosts, services):
    proto_match = PROTOCOL_PATTERN.search(line)
    protocol = proto_match.group(1).lower() if proto_match else None

    def replace(match):
        ip = match.group("ip")
        value = match.group("value")

        try:
            ip = str(ipaddress.IPv4Address(ip))
        except ipaddress.AddressValueError:
            return match.group(0)

        hostname = hosts.get(ip, ip)

        if value is None:
            return hostname

        if protocol in ("tcp", "udp"):
            service = services.get((value, protocol), value)
            return f"{hostname}({service})"

        if protocol == "icmp":
            if "/" in value:
                icmp_type, icmp_code = map(int, value.split("/"))
            else:
                icmp_type, icmp_code = int(value), 0

            name = ICMP_TYPES.get(
                (icmp_type, icmp_code),
                f"{icmp_type}/{icmp_code}"
            )

            return f"{hostname}({name})"

        return f"{hostname}({value})"

    return IP_PATTERN.sub(replace, line)


def main():
    parser = argparse.ArgumentParser(
        description="Translate Cisco IOS TCP/UDP/ICMP ACL logs"
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
        help="Input log file (default: stdin)"
    )

    args = parser.parse_args()

    try:
        hosts = load_hosts(args.hosts)
        services = load_services(args.services)

        source = (
            open(args.file, encoding="utf-8", errors="replace")
            if args.file
            else nullcontext(sys.stdin)
        )

        with source as lines:
            for line in lines:
                sys.stdout.write(
                    translate(line, hosts, services)
                )

    except (OSError, UnicodeError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()


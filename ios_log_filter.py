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
    (5, 2): "redirect-tos-network",
    (5, 3): "redirect-tos-host",
    (8, 0): "echo-request",
    (9, 0): "router-advertisement",
    (10, 0): "router-solicitation",
    (11, 0): "ttl-exceeded",
    (11, 1): "fragment-reassembly-time-exceeded",
    (12, 0): "parameter-problem",
    (13, 0): "timestamp-request",
    (14, 0): "timestamp-reply",
    (15, 0): "information-request",
    (16, 0): "information-reply",
    (17, 0): "address-mask-request",
    (18, 0): "address-mask-reply",
}


IP_RE = re.compile(
    r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])"
)

ENDPOINT_RE = re.compile(
    r"(?<![\w.])"
    r"(?P<ip>(?:\d{1,3}\.){3}\d{1,3})"
    r"\((?P<port>\d+)\)"
    r"(?![\w.])"
)

TCP_UDP_RE = re.compile(
    ENDPOINT_RE.pattern + "|" + IP_RE.pattern
)

ICMP_RE = re.compile(
    r"(?P<prefix>\s*)"
    r"\((?P<type>\d{1,3})"
    r"(?:/(?P<code>\d{1,3}))?\)"
)

PROTO_RE = re.compile(
    r"\b(tcp|udp|icmp)\b", re.IGNORECASE
)


def debug(message, enabled):
    if enabled:
        print(f"DEBUG: {message}", file=sys.stderr)


def load_hosts(filename, debug_enabled=False):
    hosts = {}

    with open(filename, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            fields = line.split("#", 1)[0].split()

            if len(fields) < 2:
                continue

            try:
                ip = str(ipaddress.IPv4Address(fields[0]))
            except ipaddress.AddressValueError:
                debug(
                    f"{filename}:{lineno}: invalid host IP "
                    f"{fields[0]!r}",
                    debug_enabled
                )
                continue

            hosts[ip] = fields[1]

    debug(
        f"Loaded {len(hosts)} hosts from {filename}",
        debug_enabled
    )

    for ip, hostname in hosts.items():
        debug(
            f"HOST: {ip} -> {hostname}",
            debug_enabled
        )

    return hosts


def load_services(filename, debug_enabled=False):
    services = {}

    with open(filename, encoding="utf-8") as f:
        for line in f:
            fields = line.split("#", 1)[0].split()

            if len(fields) < 2 or "/" not in fields[1]:
                continue

            port, protocol = fields[1].split("/", 1)

            if port.isdigit():
                services.setdefault(
                    (port, protocol.lower()),
                    fields[0]
                )

    debug(
        f"Loaded {len(services)} services from {filename}",
        debug_enabled
    )

    return services


def translate(line, hosts, services, debug_enabled=False):
    proto_match = PROTO_RE.search(line)
    protocol = (
        proto_match.group(1).lower()
        if proto_match else None
    )

    def resolve_ip(ip):
        try:
            ip = str(ipaddress.IPv4Address(ip))
        except ipaddress.AddressValueError:
            debug(
                f"INVALID IP: {ip}",
                debug_enabled
            )
            return ip

        hostname = hosts.get(ip)

        if hostname is None:
            debug(
                f"NO HOST MATCH: {ip}",
                debug_enabled
            )
            return ip

        debug(
            f"HOST MATCH: {ip} -> {hostname}",
            debug_enabled
        )
        return hostname

    def replace_ip(match):
        return resolve_ip(match.group(0))

    if protocol in ("tcp", "udp"):

        def replace_tcp_udp(match):
            if match.group("ip") is not None:
                ip = match.group("ip")
                port = match.group("port")

                hostname = resolve_ip(ip)
                service = services.get(
                    (port, protocol), port
                )

                if service != port:
                    debug(
                        f"SERVICE MATCH: "
                        f"{port}/{protocol} -> {service}",
                        debug_enabled
                    )

                return f"{hostname}({service})"

            return replace_ip(match)

        return TCP_UDP_RE.sub(replace_tcp_udp, line)

    if protocol == "icmp":
        line = IP_RE.sub(replace_ip, line)

        def replace_icmp(match):
            type_num = int(match.group("type"))
            code_num = (
                int(match.group("code"))
                if match.group("code") is not None
                else 0
            )

            if type_num > 255 or code_num > 255:
                return match.group(0)

            name = ICMP_TYPES.get(
                (type_num, code_num)
            )

            if name is None:
                debug(
                    f"UNKNOWN ICMP: {type_num}/{code_num}",
                    debug_enabled
                )
                return match.group(0)

            debug(
                f"ICMP MATCH: {type_num}/{code_num} -> {name}",
                debug_enabled
            )

            return f'{match.group("prefix")}({name})'

        return ICMP_RE.sub(replace_icmp, line)

    return IP_RE.sub(replace_ip, line)


def main():
    parser = argparse.ArgumentParser(
        description="Cisco IOS TCP/UDP/ICMP log filter"
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

    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        help="Show hostname and service lookup debugging"
    )

    args = parser.parse_args()

    try:
        hosts = load_hosts(args.hosts, args.debug)
        services = load_services(args.services, args.debug)

        source = (
            open(args.file, encoding="utf-8", errors="replace")
            if args.file
            else nullcontext(sys.stdin)
        )

        with source as lines:
            for line in lines:
                sys.stdout.write(
                    translate(
                        line, hosts, services, args.debug
                    )
                )

    except (OSError, UnicodeError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()


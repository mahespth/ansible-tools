#!/usr/bin/env python3

"""
sssd_dns_probe_nopip.py — Looping DNS probe for AD DC SRV records using only system tools (no pip deps).

It prefers `dig`, then `host`, then `resolvectl`, then `nslookup`.
Works in air-gapped environments as long as one of those tools is installed.

Examples:
  python3 sssd_dns_probe_nopip.py --domain example.corp --interval 5
  python3 sssd_dns_probe_nopip.py --domain example.corp --nameserver 10.0.0.10 --nameserver 10.0.0.11 --tcp-fallback --dump-addrs
  python3 sssd_dns_probe_nopip.py --domain example.corp --once --log /var/log/sssd_dns_probe.log

Exit codes with --once: 0 success, 2 failure.
"""

import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import List, Tuple, Optional


def find_tool() -> str:
    for tool in ("dig", "host", "resolvectl", "systemd-resolve", "nslookup"):
        if shutil.which(tool):
            return tool
    return ""


def build_srv_name(domain: str) -> str:
    domain = domain.strip(".")
    return f"_ldap._tcp.dc._msdcs.{domain}."


def run(cmd: List[str], timeout: float) -> Tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def parse_srv_from_dig_short(text: str) -> List[Tuple[str, int, int, int]]:
    # lines like: "0 100 389 dc1.example.corp."
    out = []
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) == 4 and parts[3].endswith("."):
            try:
                prio = int(parts[0]); weight = int(parts[1]); port = int(parts[2])
                target = parts[3].rstrip(".")
                out.append((target, port, prio, weight))
            except ValueError:
                continue
    return out


def query_srv_with_dig(qname: str, ns: Optional[str], timeout: float, tcp: bool) -> List[Tuple[str, int, int, int]]:
    cmd = ["dig", "+time={}".format(int(max(1, timeout))), "+tries=1", "+nocmd", "+noquestion", "+nocomments", "+nostats", "+short"]
    if tcp:
        cmd.append("+tcp")
    if ns:
        cmd.append("@{}".format(ns))
    cmd += ["-t", "SRV", qname]
    rc, out, err = run(cmd, timeout=timeout+1.0)
    if rc != 0:
        raise RuntimeError(f"dig rc={rc} err={err.strip()}")
    recs = parse_srv_from_dig_short(out)
    if not recs:
        # try full output parse fallback (rarely needed)
        recs = []
    return recs


def parse_srv_from_host(text: str) -> List[Tuple[str, int, int, int]]:
    # lines like: "_ldap._tcp.dc._msdcs.example.corp has SRV record 0 100 389 dc1.example.corp."
    out = []
    for line in text.splitlines():
        line = line.strip()
        if " has SRV record " in line:
            try:
                left, right = line.split(" has SRV record ", 1)
                parts = right.split()
                if len(parts) >= 4:
                    prio = int(parts[0]); weight = int(parts[1]); port = int(parts[2]); target = parts[3].rstrip(".")
                    out.append((target, port, prio, weight))
            except Exception:
                continue
    return out


def query_srv_with_host(qname: str, ns: Optional[str], timeout: float) -> List[Tuple[str, int, int, int]]:
    cmd = ["host", "-t", "SRV", qname]
    if ns:
        cmd.append(ns)  # host allows "host name server"
    rc, out, err = run(cmd, timeout=timeout+1.0)
    if rc != 0:
        raise RuntimeError(f"host rc={rc} err={err.strip()}")
    recs = parse_srv_from_host(out)
    return recs


def parse_srv_from_resolvectl(text: str) -> List[Tuple[str, int, int, int]]:
    # Example lines: "SRV 0 100 389 dc1.example.corp."
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("SRV "):
            parts = line.split()
            if len(parts) >= 5:
                try:
                    prio = int(parts[1]); weight = int(parts[2]); port = int(parts[3]); target = parts[4].rstrip(".")
                    out.append((target, port, prio, weight))
                except ValueError:
                    continue
    return out


def query_srv_with_resolvectl(qname: str, ns: Optional[str], timeout: float, tool: str) -> List[Tuple[str, int, int, int]]:
    base = tool  # "resolvectl" or "systemd-resolve"
    cmd = [base, "query", qname, "--type=SRV"]
    if ns and base == "resolvectl":
        cmd.append(f"--server={ns}")
    rc, out, err = run(cmd, timeout=timeout+1.0)
    if rc != 0:
        raise RuntimeError(f"{base} rc={rc} err={err.strip()}")
    recs = parse_srv_from_resolvectl(out)
    return recs


def parse_srv_from_nslookup(text: str) -> List[Tuple[str, int, int, int]]:
    # nslookup output varies; look for lines like: "priority = 0, weight = 100, port = 389, target = dc1.example.corp"
    out = []
    for line in text.splitlines():
        line = line.strip()
        if ("priority" in line and "weight" in line and "port" in line):
            try:
                # crude parse that works across common nslookup variants
                prio = int(line.split("priority")[1].split("=")[1].split(",")[0])
                weight = int(line.split("weight")[1].split("=")[1].split(",")[0])
                port = int(line.split("port")[1].split("=")[1].split(",")[0])
                target = line.split("target")[1].split("=")[1].strip().rstrip(".")
                out.append((target, port, prio, weight))
            except Exception:
                continue
    return out


def query_srv_with_nslookup(qname: str, ns: Optional[str], timeout: float) -> List[Tuple[str, int, int, int]]:
    cmd = ["nslookup", "-type=SRV", qname]
    if ns:
        cmd.append(ns)
    rc, out, err = run(cmd, timeout=timeout+1.0)
    if rc != 0:
        raise RuntimeError(f"nslookup rc={rc} err={err.strip()}")
    recs = parse_srv_from_nslookup(out)
    return recs


def query_a_aaaa_with_dig(name: str, ns: Optional[str], timeout: float) -> Tuple[List[str], List[str]]:
    a, aaaa = [], []
    for rrtype, dest in (("A", a), ("AAAA", aaaa)):
        cmd = ["dig", "+time={}".format(int(max(1, timeout))), "+tries=1", "+nocmd", "+noquestion", "+nocomments", "+nostats", "+short"]
        if ns:
            cmd.append("@{}".format(ns))
        cmd += ["-t", rrtype, name]
        rc, out, err = run(cmd, timeout=timeout+1.0)
        if rc == 0:
            for line in out.splitlines():
                ip = line.strip()
                if ip:
                    dest.append(ip)
    return a, aaaa


def query_a_aaaa_system(name: str) -> Tuple[List[str], List[str]]:
    a, aaaa = [], []
    try:
        for res in socket.getaddrinfo(name, None, family=socket.AF_INET, type=socket.SOCK_STREAM):
            a.append(res[4][0])
    except Exception:
        pass
    try:
        for res in socket.getaddrinfo(name, None, family=socket.AF_INET6, type=socket.SOCK_STREAM):
            aaaa.append(res[4][0])
    except Exception:
        pass
    # dedupe
    a = sorted(list(dict.fromkeys(a)))
    aaaa = sorted(list(dict.fromkeys(aaaa)))
    return a, aaaa


def setup_logger(path: str, verbose: bool) -> logging.Logger:
    log = logging.getLogger("sssd_dns_probe")
    log.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)sZ %(levelname)s %(message)s")
    stream = logging.StreamHandler(sys.stdout)
    stream.setLevel(logging.DEBUG if verbose else logging.INFO)
    stream.setFormatter(fmt)
    log.addHandler(stream)
    if path:
        handler = RotatingFileHandler(path, maxBytes=5*1024*1024, backupCount=5)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(fmt)
        log.addHandler(handler)
    return log


def main():
    p = argparse.ArgumentParser(description="Looping DNS probe for AD DC SRV records (no external deps)")
    p.add_argument("--domain", required=True, help="AD domain (e.g., example.corp)")
    p.add_argument("--nameserver", action="append", default=[], help="DNS server IP to query (repeatable). If omitted, system resolver is used.")
    p.add_argument("--interval", type=int, default=10, help="Seconds between probes (default: 10)")
    p.add_argument("--timeout", type=float, default=2.0, help="Per-try timeout seconds (default: 2.0)")
    p.add_argument("--retries", type=int, default=2, help="Retries per probe (default: 2)")
    p.add_argument("--tcp-fallback", action="store_true", help="With dig present, retry SRV over TCP if UDP attempts fail")
    p.add_argument("--log", default="", help="Optional log file path (also logs to stdout)")
    p.add_argument("--once", action="store_true", help="Run one probe and exit")
    p.add_argument("--dump-addrs", action="store_true", help="Also resolve A/AAAA for SRV targets and log them")
    p.add_argument("--tag", default="", help="Optional tag to include in logs (e.g., site/hostname)")
    args = p.parse_args()

    log = setup_logger(args.log, verbose=True)
    qname = build_srv_name(args.domain)

    tool = find_tool()
    if not tool:
        log.error("No resolver tool found. Install one of: dig (bind-utils), host, resolvectl/systemd-resolve, or nslookup.")
        sys.exit(2)
    log.info(f"Using resolver tool: {tool}")

    def query_srv(ns: Optional[str], tcp: bool) -> List[Tuple[str, int, int, int]]:
        if tool == "dig":
            return query_srv_with_dig(qname, ns, args.timeout, tcp=tcp)
        elif tool == "host":
            return query_srv_with_host(qname, ns, args.timeout)
        elif tool in ("resolvectl", "systemd-resolve"):
            return query_srv_with_resolvectl(qname, ns, args.timeout, tool=tool)
        elif tool == "nslookup":
            return query_srv_with_nslookup(qname, ns, args.timeout)
        else:
            return []

    def query_addrs(name: str, ns: Optional[str]) -> Tuple[List[str], List[str]]:
        if tool == "dig":
            return query_a_aaaa_with_dig(name, ns, args.timeout)
        else:
            # fallback to system resolver
            return query_a_aaaa_system(name)

    log.info(f"Starting SRV probe for {qname} interval={args.interval}s retries={args.retries} nameservers={args.nameserver or 'system'} tcp_fallback={args.tcp_fallback}")
    if args.tag:
        log.info(f"Tag: {args.tag}")

    def probe_once() -> bool:
        servers = args.nameserver or [None]  # None => system
        last_err = None
        for ns in servers:
            # UDP/default attempts
            for i in range(1, args.retries + 1):
                start = time.perf_counter()
                try:
                    recs = query_srv(ns, tcp=False)
                    elapsed_ms = int((time.perf_counter() - start) * 1000)
                    if not recs:
                        raise RuntimeError("no SRV records returned")
                    log.info(f"SRV OK via {ns or 'system'} in {elapsed_ms}ms: {len(recs)} record(s)")
                    for t, port, prio, weight in sorted(recs, key=lambda x: (x[2], -x[3], x[0])):
                        log.debug(f"  target={t} port={port} priority={prio} weight={weight}")
                        if args.dump-addrs:
                            a, aaaa = query_addrs(t, ns)
                            if a:
                                log.debug(f"    A: {', '.join(a)}")
                            if aaaa:
                                log.debug(f"    AAAA: {', '.join(aaaa)}")
                    return True
                except Exception as e:
                    last_err = str(e)
                    log.warning(f"Attempt {i}/{args.retries} failed via {ns or 'system'}: {e}")
            # Optional TCP fallback
            if args.tcp_fallback and tool == "dig":
                for i in range(1, max(1, args.retries) + 1):
                    try:
                        recs = query_srv(ns, tcp=True)
                        elapsed_ms = int((time.perf_counter() - start) * 1000)
                        if not recs:
                            raise RuntimeError("no SRV records returned (TCP)")
                        log.info(f"SRV OK via {ns or 'system'} over TCP in {elapsed_ms}ms: {len(recs)} record(s)")
                        for t, port, prio, weight in sorted(recs, key=lambda x: (x[2], -x[3], x[0])):
                            log.debug(f"  target={t} port={port} priority={prio} weight={weight}")
                            if args.dump-addrs:
                                a, aaaa = query_addrs(t, ns)
                                if a:
                                    log.debug(f"    A: {', '.join(a)}")
                                if aaaa:
                                    log.debug(f"    AAAA: {', '.join(aaaa)}")
                        return True
                    except Exception as e:
                        last_err = str(e)
                        log.warning(f"TCP attempt {i} failed via {ns or 'system'}: {e}")
        if last_err:
            log.error(f"SRV probe FAILED: {last_err}")
        else:
            log.error("SRV probe FAILED: unknown error")
        return False

    while True:
        success = probe_once()
        if args.once:
            sys.exit(0 if success else 2)
        time.sleep(max(1, args.interval))


if __name__ == "__main__":
    main()
ss

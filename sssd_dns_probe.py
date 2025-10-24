#!/usr/bin/env python3

"""
sssd_dns_probe.py — Looping DNS probe for AD DC SRV records with robust logging.

Examples:
  python3 sssd_dns_probe.py --domain example.corp --nameserver 10.0.0.10 --interval 5
  python3 sssd_dns_probe.py --domain example.corp --nameserver 10.0.0.10 --nameserver 10.0.0.11 --log /var/log/sssd_dns_probe.log
  python3 sssd_dns_probe.py --domain example.corp --tcp-fallback

Requires: dnspython (pip install dnspython)
"""

import argparse
import logging
from logging.handlers import RotatingFileHandler
import sys
import time
from datetime import datetime, timezone
from typing import List, Tuple

try:
    import dns.resolver
    import dns.exception
    import dns.name
    import dns.rdatatype
    import dns.flags
except Exception as e:
    print("This script requires the 'dnspython' package. Install with: pip install dnspython", file=sys.stderr)
    raise


def build_srv_name(domain: str) -> str:
    # Active Directory Domain Controller locator record per MS docs
    # _ldap._tcp.dc._msdcs.<ForestRootDomain>
    domain = domain.strip(".")
    return f"_ldap._tcp.dc._msdcs.{domain}."


def resolve_srv_targets(resolver: dns.resolver.Resolver, qname: str) -> List[Tuple[str, int, int, int]]:
    """
    Returns list of (target, port, priority, weight) from SRV answer.
    Raises exceptions on failure.
    """
    answer = resolver.resolve(qname, "SRV")
    records = []
    for r in answer:
        records.append((str(r.target).rstrip("."), int(r.port), int(r.priority), int(r.weight)))
    return records


def resolve_host_addrs(resolver: dns.resolver.Resolver, host: str) -> Tuple[List[str], List[str]]:
    a, aaaa = [], []
    try:
        for ans in resolver.resolve(host, "A"):
            a.append(ans.to_text())
    except Exception:
        pass
    try:
        for ans in resolver.resolve(host, "AAAA"):
            aaaa.append(ans.to_text())
    except Exception:
        pass
    return a, aaaa


def make_resolver(servers: List[str], timeout: float, lifetime: float, use_tcp: bool) -> dns.resolver.Resolver:
    r = dns.resolver.Resolver(configure=(len(servers) == 0))
    if servers:
        r.nameservers = servers
    r.timeout = timeout
    r.lifetime = lifetime
    r.use_edns(0, dns.flags.DO, 1232)  # modern EDNS buffer, helps with large SRV responses
    r.retry_servfail = True
    # dnspython uses UDP first by default, then TCP on truncation. We'll optionally force TCP fallback attempts.
    # We'll handle forced TCP within the query loop by setting 'tcp' on each call when needed.
    return r


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
    p = argparse.ArgumentParser(description="Looping DNS probe for AD DC SRV records")
    p.add_argument("--domain", required=True, help="AD domain (e.g., example.corp)")
    p.add_argument("--nameserver", action="append", default=[], help="DNS server IP to query (repeatable). Defaults to system resolv.conf if omitted.")
    p.add_argument("--interval", type=int, default=10, help="Seconds between probes (default: 10)")
    p.add_argument("--timeout", type=float, default=2.0, help="Per-try socket timeout in seconds (default: 2.0)")
    p.add_argument("--lifetime", type=float, default=4.0, help="Overall query lifetime in seconds (default: 4.0)")
    p.add_argument("--retries", type=int, default=2, help="Number of retries per probe (default: 2)")
    p.add_argument("--tcp-fallback", action="store_true", help="If UDP fails or times out, retry with TCP")
    p.add_argument("--log", default="", help="Path to log file (optional). Also logs to stdout.")
    p.add_argument("--once", action="store_true", help="Run one probe and exit (useful for cron/systemd health checks)")
    p.add_argument("--qname", default="", help="Override the SRV qname. If unset, uses _ldap._tcp.dc._msdcs.<domain>.")
    p.add_argument("--dump-addrs", action="store_true", help="Also resolve A/AAAA for each SRV target and log them.")
    p.add_argument("--tag", default="", help="Optional tag to include in log lines (e.g., hostname/site).")
    p.add_argument("--warn-latency-ms", type=int, default=250, help="Warn if query exceeds this latency (ms).")
    args = p.parse_args()

    log = setup_logger(args.log, verbose=True)

    qname = args.qname if args.qname else build_srv_name(args.domain)
    resolver = make_resolver(args.nameserver, args.timeout, args.lifetime, use_tcp=False)

    log.info(f"Starting DNS probe for SRV {qname} (domain={args.domain}) nameservers={args.nameserver or 'system'} interval={args.interval}s retries={args.retries} tcp_fallback={args.tcp_fallback}")
    if args.tag:
        log.info(f"Tag: {args.tag}")

    def probe(tcp: bool = False) -> bool:
        start = time.perf_counter()
        try:
            # dnspython supports tcp=bool per resolve()
            targets = resolve_srv_targets(resolver, qname) if not tcp else dns.resolver.resolve(qname, "SRV", lifetime=args.lifetime, tcp=True, raise_on_no_answer=True)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            if elapsed_ms > args.warn_latency_ms:
                log.warning(f"SRV query latency high: {elapsed_ms}ms (tcp={tcp})")
            # Normalize result structure in case of TCP path
            if tcp:
                norm = []
                for r in targets:
                    norm.append((str(r.target).rstrip("."), int(r.port), int(r.priority), int(r.weight)))
                targets = norm
            log.info(f"SRV OK ({elapsed_ms}ms): {len(targets)} records")
            for t, port, prio, weight in sorted(targets, key=lambda x: (x[2], -x[3], x[0])):
                log.debug(f"  target={t} port={port} priority={prio} weight={weight}")
                if args.dump-addrs:
                    a, aaaa = resolve_host_addrs(resolver, t)
                    if a:
                        log.debug(f"    A: {', '.join(a)}")
                    if aaaa:
                        log.debug(f"    AAAA: {', '.join(aaaa)}")
            return True
        except dns.exception.Timeout:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            log.error(f"TIMEOUT after {elapsed_ms}ms (tcp={tcp}) for {qname}")
            return False
        except dns.resolver.NXDOMAIN:
            log.error(f"NXDOMAIN for {qname} (name does not exist)")
            return False
        except dns.resolver.NoAnswer:
            log.error(f"NoAnswer for {qname} (empty response)")
            return False
        except dns.resolver.NoNameservers as e:
            log.error(f"NoNameservers usable for query: {e}")
            return False
        except Exception as e:
            log.exception(f"Unexpected error during query: {e}")
            return False

    def one_cycle() -> bool:
        # Try UDP first with retries
        for i in range(1, args.retries + 1):
            ok = probe(tcp=False)
            if ok:
                return True
            else:
                log.warning(f"Attempt {i}/{args.retries} failed (UDP)")
        if args.tcp_fallback:
            log.info("Trying TCP fallback")
            for i in range(1, max(1, args.retries) + 1):
                ok = probe(tcp=True)
                if ok:
                    return True
                else:
                    log.warning(f"Attempt {i}/{args.retries} failed (TCP)")
        return False

    while True:
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        success = one_cycle()
        if not success:
            log.error(f"SRV probe FAILED for {qname}")
        else:
            log.debug("Probe succeeded")
        if args.once:
            sys.exit(0 if success else 2)
        time.sleep(max(1, args.interval))


if __name__ == "__main__":
    main()

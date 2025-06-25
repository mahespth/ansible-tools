#!/usr/bin/python

# -*- coding: utf-8 -*-

"""
Ansible module to send a single syslog message to one or more remote syslog
servers over UDP or TCP.

Author: Steve Maher (@mahespth)
# Stephen Maher, AIXtreme Research Ltd.
# (c) 2025 AIXTreme Research Ltd Licensed under the MIT License

"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
module: syslog_multisend
short_description: Send a syslog message to multiple servers over UDP or TCP
version_added: "1.1.1"
author:
  - Steve (@your-github-handle)
description:
  - "Sends a single RFC 3164‑style syslog packet (PRI + message, newline‑delimited) to one or more remote collectors."
  - "Supports UDP or TCP transports and accepts the *facility* either as an integer 0‑23 or the standard mnemonic string (e.g. user, local0)."
options:
  msg:
    description:
      - "The syslog message body to send."
      - "The module automatically prepends the calculated PRI value (based on *facility* and *priority*) as required by RFC 3164."
    type: str
    required: true
  servers:
    description:
      - "List of syslog collector hostnames or IP addresses."
    type: list
    elements: str
    required: true
  port:
    description:
      - "Destination port on the collectors."
    type: int
    default: 514
  protocol:
    description:
      - "Transport protocol to use."
    type: str
    choices:
      - udp
      - tcp
    default: udp
  facility:
    description:
      - "Syslog facility — numeric code 0‑23 *or* one of the standard names: kern, user, mail, daemon, auth, syslog, lpr, news, uucp, cron, authpriv, ftp, ntp, security, console, solaris‑cron, local0…local7."
    type: raw
    default: user
  priority:
    description:
      - "Syslog severity/priority 0‑7 (or name: emerg, alert, crit, err, warning, notice, info, debug)."
    type: raw
    default: info
  timeout:
    description:
      - "Socket connect/send timeout in seconds."
    type: int
    default: 3
requirements: []
"""

EXAMPLES = r"""
- name: Send an informational event with facility by name
  syslog_multisend:
    msg: "App deployed successfully on {{ inventory_hostname }}"
    servers:
      - log01.example.com
      - log02.example.com
    facility: user
    priority: info

- name: Critical alert over TCP/6514 with numeric facility
  syslog_multisend:
    msg: "CRIT: disk full on {{ inventory_hostname }}"
    servers: [ "logs.example.com" ]
    protocol: tcp
    port: 6514
    facility: 16   # local0
    priority: 2    # critical
"""

RETURN = r"""
sent:
  description: List of collectors that accepted the packet.
  type: list
failed:
  description: Mapping of collectors that failed and the associated error message.
  type: dict
sent_count:
  description: Number of successful sends.
  type: int
failed_count:
  description: Number of failed sends.
  type: int
changed:
  description: Always C(true) when at least one packet was delivered.
  type: bool
"""

import socket
from typing import List, Dict, Tuple, Union
from ansible.module_utils.basic import AnsibleModule

# Mapping of mnemonic facility names to numbers (RFC 3164)
FACILITY_MAP = {
    "kern": 0,
    "user": 1,
    "mail": 2,
    "daemon": 3,
    "auth": 4,
    "syslog": 5,
    "lpr": 6,
    "news": 7,
    "uucp": 8,
    "cron": 9,
    "authpriv": 10,
    "ftp": 11,
    "ntp": 12,
    "security": 13,
    "console": 14,
    "solaris-cron": 15,
    "local0": 16,
    "local1": 17,
    "local2": 18,
    "local3": 19,
    "local4": 20,
    "local5": 21,
    "local6": 22,
    "local7": 23,
}

SEVERITY_MAP = {
    "emerg": 0,
    "alert": 1,
    "crit": 2,
    "err": 3,
    "warning": 4,
    "notice": 5,
    "info": 6,
    "debug": 7,
}


def _parse_facility(module: AnsibleModule, facility: Union[int, str]) -> int:
    """Convert the facility parameter to its numeric code or fail the module."""
    if isinstance(facility, int):
        if 0 <= facility <= 23:
            return facility
        module.fail_json(msg=f"facility int out of range (0‑23): {facility}")
    if isinstance(facility, str):
        f = facility.strip().lower()
        if f.isdigit():
            num = int(f)
            if 0 <= num <= 23:
                return num
            module.fail_json(msg=f"facility numeric string out of range (0‑23): {facility}")
        if f in FACILITY_MAP:
            return FACILITY_MAP[f]
        module.fail_json(msg=f"unknown facility name: {facility}")
    module.fail_json(msg="facility must be int 0‑23 or one of the standard names")


def _parse_severity(module: AnsibleModule, priority: Union[int, str]) -> int:
    """Allow severity by name or number (0‑7)."""
    if isinstance(priority, int):
        if 0 <= priority <= 7:
            return priority
        module.fail_json(msg=f"priority int out of range (0‑7): {priority}")
    if isinstance(priority, str):
        p = priority.strip().lower()
        if p.isdigit():
            num = int(p)
            if 0 <= num <= 7:
                return num
            module.fail_json(msg=f"priority numeric string out of range (0‑7): {priority}")
        if p in SEVERITY_MAP:
            return SEVERITY_MAP[p]
        module.fail_json(msg=f"unknown priority name: {priority}")
    module.fail_json(msg="priority must be int 0‑7 or a standard severity name")


def build_syslog_message(msg: str, facility_num: int, priority_num: int) -> bytes:
    """Construct a simple RFC 3164‑style message: <PRI>MESSAGE\n"""
    pri = facility_num * 8 + priority_num
    return f"<{pri}>{msg}\n".encode("utf-8")


def send_udp(packet: bytes, host: str, port: int, timeout: int) -> Tuple[bool, str]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(packet, (host, port))
        return True, "sent"
    except Exception as exc:
        return False, str(exc)
    finally:
        sock.close()


def send_tcp(packet: bytes, host: str, port: int, timeout: int) -> Tuple[bool, str]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        sock.sendall(packet)
        return True, "sent"
    except Exception as exc:
        return False, str(exc)
    finally:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        sock.close()


def run_module():
    module_args = dict(
        msg=dict(type="str", required=True),
        servers=dict(type="list", elements="str", required=True),
        port=dict(type="int", default=514),
        protocol=dict(type="str", choices=["udp", "tcp"], default="udp"),
        facility=dict(type="raw", default="user"),
        priority=dict(type="raw", default="info"),
        timeout=dict(type="int", default=3),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=False)

    msg = module.params["msg"]
    servers: List[str] = module.params["servers"]
    port: int = module.params["port"]
    protocol: str = module.params["protocol"]
    facility_param = module.params["facility"]
    priority_param = module.params["priority"]
    timeout: int = module.params["timeout"]

    facility_num = _parse_facility(module, facility_param)
    severity_num = _parse_severity(module, priority_param)

    packet = build_syslog_message(msg, facility_num, severity_num)

    sent: List[str] = []
    failed: Dict[str, str] = {}

    sender = send_udp if protocol == "udp" else send_tcp

    for host in servers:
        ok, info = sender(packet, host, port, timeout)
        if ok:
            sent.append(host)
        else:
            failed[host] = info

    result = dict(
        changed=bool(sent),
        sent=sent,
        failed=failed,
        sent_count=len(sent),
        failed_count=len(failed),
    )

    if failed:
        module.fail_json(msg="Failed to send to one or more collectors", **result)
    else:
        module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()

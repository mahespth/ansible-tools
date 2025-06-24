"""
Ansible module to send a single syslog message to one or more remote syslog
servers over UDP or TCP.

Author: Steve Maher (@mahespth)
Copyright: (c) 2025, AIXTreme Research Ltd
License: GPLv3+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
module: syslog_multisend
short_description: Send a syslog message to multiple servers over UDP or TCP
version_added: "1.0.0"
author:
  - Steve Maher (@mahespth)
description:
  - Sends a single RFC3164‑style syslog packet (PRI + message, newline‑delimited)
    to a list of remote collectors.
  - Supports UDP or TCP transports and per‑task selection of facility/priority.
options:
  msg:
    description:
      - The syslog message text/body.
      - The module automatically prepends the calculated PRI value (based on
        facility and priority) as required by RFC3164.
    type: str
    required: true
  servers:
    description:
      - List of hostnames or IP addresses of the syslog collectors.
    type: list
    elements: str
    required: true
  port:
    description:
      - Destination port on the collectors.
    type: int
    default: 514
  protocol:
    description:
      - Transport protocol to use.
    type: str
    choices: [ udp, tcp ]
    default: udp
  facility:
    description:
      - Syslog facility number (0‑23) used to calculate PRI.
    type: int
    default: 1  # user‑level messages
  priority:
    description:
      - Syslog severity/priority number (0‑7) used to calculate PRI.
    type: int
    default: 6  # informational
  timeout:
    description:
      - Connect/send timeout in seconds.
    type: int
    default: 3
requirements: []
"""

EXAMPLES = r"""
- name: Send an informational event to two collectors over UDP
  syslog_multisend:
    msg: "App deployed successfully on {{ inventory_hostname }}"
    servers:
      - log01.example.com
      - log02.example.com
    facility: 1   # user
    priority: 6   # info

- name: Send a critical alert to a collector on TCP/6514 (Syslog over TLS‑terminating LB)
  syslog_multisend:
    msg: "CRIT: disk full on {{ inventory_hostname }}"
    servers: [ "logs.example.com" ]
    protocol: tcp
    port: 6514
    priority: 2     # critical
"""

RETURN = r"""
sent:
  description: List of collectors that accepted the packet.
  type: list
  returned: always
failed:
  description: Mapping of collectors that failed and the associated error.
  type: dict
  returned: always
sent_count:
  description: Number of successful sends.
  type: int
  returned: always
failed_count:
  description: Number of failed sends.
  type: int
  returned: always
changed:
  description: Always C(true) when at least one packet was delivered.
  type: bool
  returned: always
"""

import socket
from typing import List, Dict, Tuple
from ansible.module_utils.basic import AnsibleModule


def build_syslog_message(msg: str, facility: int, priority: int) -> bytes:
    """Construct a simple RFC3164‑style message: <PRI>MESSAGE\n"""
    pri = facility * 8 + priority
    return f"<{pri}>{msg}\n".encode("utf‑8")


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
        facility=dict(type="int", default=1),
        priority=dict(type="int", default=6),
        timeout=dict(type="int", default=3),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=False)

    msg = module.params["msg"]
    servers: List[str] = module.params["servers"]
    port: int = module.params["port"]
    protocol: str = module.params["protocol"]
    facility: int = module.params["facility"]
    priority: int = module.params["priority"]
    timeout: int = module.params["timeout"]

    packet = build_syslog_message(msg, facility, priority)

    sent: List[str] = []
    failed: Dict[str, str] = {}

    for host in servers:
        ok, info = (send_udp if protocol == "udp" else send_tcp)(packet, host, port, timeout)
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

# DRBD Volume Playbook – Usage Guide

This document describes how to use the DRBD Ansible playbook to install and configure a replicated block device between two RHEL 9 nodes.

The playbook:

- Installs **DRBD 9** (kernel module + utils) from **ELRepo**.
- Configures a **single DRBD resource** (`r0`) in **asynchronous** mode (protocol `A`).
- Creates `/dev/drbd0`, formats it, and mounts it on the **primary** node.

---

## 1. Prerequisites

### OS / Platform

- RHEL 9 (or compatible) on both nodes.
- Both nodes reachable over the network (TCP, default DRBD port: `7788`).
- Ansible 2.9+ or AAP (tested on AAP 2.x).

### Storage

On **each DRBD node**:

- One **dedicated block device** for DRBD (e.g. `/dev/sdb`).
  - **Must be empty**. Any existing data will be destroyed on first run (`drbdadm create-md`).

### Repository Layout (suggested)

```text
.
├─ inventory/
│  └─ hosts.ini
├─ playbooks/
│  └─ drbd.yml
└─ templates/
   └─ drbd-resource.res.j2

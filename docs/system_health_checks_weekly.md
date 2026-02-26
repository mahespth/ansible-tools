# Weekly Systems Health Check Runbook

## Overview

This runbook defines a Monday to Friday health check routine for a systems administrator responsible for a large mixed estate including:

- AIX legacy systems
- VIOS infrastructure
- RHEL 6, 7, and 8 Linux systems
- VMware ESX/ESXi and physical hosts
- Ansible Automation Platform (AAP)
- GitLab
- Red Hat Satellite

The environment contains hundreds of systems, so this routine is designed to be:

- Dashboard and alert driven
- Exception based
- Sample based where full manual review is impractical
- Backed by automation and reporting where possible

## Operating Principles

1. Do not manually log into every host each day.
2. Prioritize critical alerts, failed jobs, non-reporting systems, and fast-growing capacity risks.
3. Use automation to produce daily exception reports.
4. Review Tier 1 systems more deeply than lower-priority legacy systems.
5. Record findings daily and escalate unresolved risks quickly.

## Suggested Daily Baseline

These tasks should be performed every working day before the weekday-specific checks.

| Task | What to check | Estimated time |
|---|---|---:|
| Review monitoring and alert dashboards | Critical and warning alerts, flapping alerts, host and service availability, storage, network, hypervisor and management platform issues | 20-30 min |
| Review incident and ticket queues | New incidents, recurring issues, aging tickets, change-related follow-up items | 10-15 min |
| Verify backup status | Overnight backups, failed jobs, retries needed, backup capacity warnings, platform backup status | 15-20 min |
| Check capacity hotspots | CPU, memory, disk, swap, paging, datastores, filesystem growth | 15-20 min |
| Review security and access anomalies | Failed logins, unusual privileged access, expired credentials, certificate warnings, service-account lockouts | 10-15 min |
| Quick platform health review | AAP, GitLab, Satellite UI and service status, queue health, worker failures, disk and DB pressure | 20-30 min |
| Record findings and handover notes | Summary of failures, remediation, escalation items, and day risks | 10-15 min |

**Daily baseline total:** approximately **1 hr 40 min to 2 hr 25 min**

---

# Monday - Weekend Review and Stability

## Objectives

- Review weekend events and hidden instability
- Validate AIX, VIOS, ESX, and physical infrastructure health
- Clear carryover tasks from the previous week

## Monday task list

| Task | What to check | Estimated time |
|---|---|---:|
| Weekend incident and alert trend review | Saturday and Sunday incidents, repeat failures, auto-recovered issues, unexpected reboots, failed weekend jobs | 20-30 min |
| AIX fleet health summary | Reachability, CPU exceptions, paging usage, filesystem thresholds, errpt errors, NTP drift, syslog forwarding | 30-45 min |
| VIOS health check | SEA status, adapter health, FC and vSCSI path status, rootvg free space, errlog events, config backup results | 30-45 min |
| VMware and ESX weekend review | Host disconnects, HA and DRS events, datastore growth, snapshots, hardware alarms, vCenter alarms, VMware Tools issues | 25-40 min |
| Physical host review | iLO or iDRAC alerts, RAID warnings, fan and PSU faults, out-of-band access status, firmware-related alarms | 20-30 min |
| Weekly housekeeping kickoff | Carryover items, monitoring exclusions, patch follow-up, high-risk systems list, actions for the week | 20-30 min |

**Monday total including baseline:** approximately **3 hr 45 min to 5 hr 25 min**

---

# Tuesday - Linux Deep Health Review

## Objectives

- Review Linux estate health in more detail
- Check service reliability and operating system exceptions
- Validate Satellite client registration and content access

## Tuesday task list

| Task | What to check | Estimated time |
|---|---|---:|
| RHEL estate segmentation review | Reporting coverage by RHEL version, non-reporting systems, stale inventory, unsupported legacy host risks | 15-25 min |
| Linux OS health exceptions | Load, memory pressure, OOM events, swap, I/O wait, filesystem usage, inodes, mount failures, kernel errors | 30-45 min |
| Critical service review on Linux | sshd, crond, rsyslog, application services, failed systemd units, SysV issues, missed cron jobs, NTP status | 25-35 min |
| Log review | Authentication failures, sudo anomalies, kernel warnings, storage errors, NIC flaps, SELinux denials, yum or dnf errors | 25-40 min |
| Satellite client and content health | Registration failures, entitlement issues, repo access failures, stale check-ins, remote execution failures | 20-35 min |
| Automation candidate review | Repetitive manual checks, recurring alerts, new AAP automation opportunities | 15-20 min |

**Tuesday total including baseline:** approximately **3 hr 50 min to 5 hr 5 min**

---

# Wednesday - Virtualization, Hardware, and Capacity

## Objectives

- Review VMware and hardware health in detail
- Check datastores, snapshots, and physical alerts
- Identify near-term capacity risks

## Wednesday task list

| Task | What to check | Estimated time |
|---|---|---:|
| vCenter and ESX host deep health review | Host alarms, hardware sensors, vmnic issues, vSwitch issues, management agent problems, maintenance state, NTP | 30-45 min |
| VM hygiene review | Stale snapshots, powered-off VM review, low disk alarms, VMware Tools state, guest heartbeat, backup or consolidation failures | 25-40 min |
| Datastore and storage review | Free space thresholds, latency spikes, thin provisioning risk, adapter warnings, congestion, path redundancy issues | 25-35 min |
| Physical hardware and out-of-band review | iLO or iDRAC alarms, RAID degradation, predictive disk failures, firmware warnings, remote console availability | 20-35 min |
| Capacity trend review | Top CPU and memory consumers, fastest-growing filesystems, datastore forecasts, memory contention, swap growth | 25-40 min |
| Maintenance and escalation planning | Vendor tickets, hardware replacement planning, snapshot cleanup plans, maintenance window requirements | 15-20 min |

**Wednesday total including baseline:** approximately **3 hr 50 min to 5 hr 20 min**

---

# Thursday - Platform Services and Automation

## Objectives

- Validate management platforms and automation tooling
- Review AAP, GitLab, and Satellite health in depth
- Confirm integrations between platforms are functioning

## Thursday task list

| Task | What to check | Estimated time |
|---|---|---:|
| AAP health review | Controller reachability, job failures, stuck jobs, execution node health, instance groups, inventory sync, project sync, credentials, disk growth | 35-50 min |
| AAP operational hygiene | Failed schedules, disabled templates, stale credentials, log retention, backup status, license or subscription status | 20-30 min |
| GitLab health review | UI and API status, Sidekiq backlog, runner availability, pipeline failure spikes, storage growth, registry cleanup, TLS expiry, backups | 30-45 min |
| GitLab runner infrastructure review | Runner host CPU, memory, disk pressure, stuck executors, container storage growth, token or network issues | 20-30 min |
| Satellite health review | Core service status, failed tasks, repo sync, Capsule health, content view failures, Pulp storage, DB pressure, entitlements, backups | 35-50 min |
| Platform integration review | AAP project sync from GitLab, AAP access to Satellite, webhook failures, service account drift, TLS trust issues | 15-25 min |

**Thursday total including baseline:** approximately **4 hr 15 min to 6 hr**

---

# Friday - Compliance, Preventive Maintenance, and Weekly Wrap-up

## Objectives

- Close the week with cleanup and risk review
- Prepare for weekend operations and on-call coverage
- Produce a concise weekly health summary

## Friday task list

| Task | What to check | Estimated time |
|---|---|---:|
| Weekly unresolved alert review | Persistent warnings, false positives, tuning candidates, long-suppressed alarms, monitoring gaps | 25-35 min |
| Patch and vulnerability readiness review | New advisories, overdue patching, reboot-required systems, legacy system risk, next patch window requirements | 25-40 min |
| Account and access review | New privileged accounts, unremoved leavers, failing service accounts, privileged group changes, temporary access cleanup | 20-30 min |
| Backup and recovery confidence review | Weekly backup success rate, repeated failures, remaining backup capacity, restore test status, config backup status | 20-30 min |
| Documentation and runbook updates | New fixes, changed ownership, known issues, escalation updates, automation backlog additions | 20-30 min |
| Weekly health report | Major incidents, top risks, capacity concerns, platform issues, weekend risks, recommendations | 30-45 min |
| Pre-weekend readiness check | Monitoring coverage, escalation paths, scheduled weekend jobs, likely threshold breaches, temporary mitigations | 15-25 min |

**Friday total including baseline:** approximately **3 hr 55 min to 5 hr 15 min**

---

# Technology Reference Checklists

## AIX systems

### Check items

- Reachability and monitoring agent reporting
- CPU utilization anomalies
- Memory and paging space usage
- Filesystem capacity thresholds
- Error report review using `errpt`
- MPIO or disk path redundancy warnings
- NTP or time synchronization issues
- Syslog forwarding health
- Failed cron jobs or scheduled scripts
- Recent reboot or uptime anomalies

### Typical review model

- Daily: alert and exception driven
- Monday: deeper fleet summary review
- Estimated deep-review time: **30-45 min**

---

## VIOS

### Check items

- SEA status and failover condition
- FC, NPIV, and vSCSI path health
- Adapter and link status
- Rootvg free space
- Critical errlog entries
- Unexpected reboot events
- NTP and time consistency
- VIOS configuration backup success

### Typical review model

- Daily: exception driven
- Monday: deeper review for critical VIOS pairs
- Estimated deep-review time: **30-45 min**

---

## RHEL 6, 7, and 8 systems

### Check items

- Host availability and check-in status
- CPU, load, memory, swap
- Filesystem and inode usage
- Failed services and daemon health
- OOM and kernel events
- Repository and package manager issues
- NTP, chrony, or ntpd health
- SSH and sudo anomalies
- SELinux denials where relevant
- Reboot-required indicators
- Registration and entitlement status in Satellite

### Typical review model

- Daily: alerts, exceptions, and stale check-ins
- Tuesday: deeper estate review
- Estimated deep-review time: **45-90 min** depending on tooling

---

## VMware ESX or ESXi and vCenter

### Check items

- Host alarms and disconnects
- Hardware sensor alerts
- Datastore free space and latency
- Snapshot sprawl and orphaned snapshots
- VMware Tools and guest heartbeat state
- HA and DRS events
- Host networking issues
- Backup and snapshot consolidation failures
- Time and certificate issues in the management plane

### Typical review model

- Daily: quick review
- Wednesday: deeper hypervisor and VM hygiene review
- Estimated deep-review time: **60-90 min**

---

## Physical hosts

### Check items

- RAID and storage controller alerts
- Predictive disk failure alerts
- PSU, fan, and temperature warnings
- Out-of-band management availability
- Console access problems
- Firmware warnings for future planning

### Typical review model

- Daily: exception driven
- Wednesday: deeper review
- Estimated deep-review time: **20-35 min**

---

## Ansible Automation Platform

### Check items

- Controller UI and API health
- Job execution failures and stuck jobs
- Execution node availability and capacity
- Project sync failures
- Inventory sync failures
- Credential and access issues
- Schedule failures
- Log growth and disk usage
- Backup status
- Certificate or subscription issues

### Typical review model

- Daily: quick platform review
- Thursday: deep operational review
- Estimated deep-review time: **55-80 min**

---

## GitLab

### Check items

- UI and API availability
- Runner online and offline state
- CI pipeline failure spikes
- Sidekiq backlog and background jobs
- Repository and registry storage growth
- Gitaly, Redis, or DB symptoms
- Certificate expiry warnings
- Backup success and restore readiness
- Webhook or integration failures

### Typical review model

- Daily: quick review
- Thursday: deeper platform review
- Estimated deep-review time: **50-75 min**

---

## Red Hat Satellite

### Check items

- Web UI and API status
- Core service health
- Failed or stuck tasks
- Repo synchronization status
- Capsule health where deployed
- Content view publish and promote failures
- Pulp or content storage capacity
- DB growth and performance warnings
- Host check-in and reporting coverage
- Entitlement and subscription issues
- Backup status

### Typical review model

- Daily: quick review
- Thursday: deeper platform review
- Estimated deep-review time: **50-75 min**

---

# Time Planning Guidance

For a single systems administrator supporting a large estate, the following is a practical expectation:

- Routine health checks: **2-4 hours per day**
- Incident response and remediation: **variable**
- Admin, project, patching, and change work: remainder of the working day

A requirement to manually inspect every system each day is not realistic for an estate of this size.

---

# Recommended Service Tiering

## Tier 1 - Critical systems

- Daily detailed review
- Fast escalation for any alert or non-reporting condition
- Stronger backup and restore validation

## Tier 2 - Important systems

- Daily alert-driven review
- Weekly sample-based deeper checks

## Tier 3 - Lower-priority legacy systems

- Alert-driven review
- Weekly or fortnightly sampled checks

---

# Recommended Thresholds

These can be adjusted to match local standards.

| Area | Warning | Critical |
|---|---:|---:|
| CPU sustained utilization | 85% | 95% |
| Memory utilization | 90% | 95% |
| Filesystem usage | 80% | 90% |
| Snapshot age | 48 hours | 72 hours |
| Backup failures | 1 missed cycle | 2 missed cycles |
| Monitoring stale check-in | 12 hours | 24 hours |

---

# Automation Candidates

The following are good candidates for Ansible AAP jobs, scripts, or scheduled reports:

- AIX `errpt` summary report
- VIOS path and adapter health summary
- Linux failed service and OOM report
- Filesystem growth exceptions report
- Non-reporting host report by platform
- VMware snapshot age report
- Datastore capacity exception report
- Satellite stale host registration report
- GitLab runner health report
- AAP failed jobs and stuck queue summary

---

# Example Daily Start-of-Day Checklist

Use this as the working checklist for the sysadmin.

- [ ] Review monitoring alerts and dashboards
- [ ] Review incidents and open tickets
- [ ] Verify overnight backups
- [ ] Review capacity hotspots
- [ ] Perform quick checks for AAP, GitLab, and Satellite
- [ ] Review security and authentication anomalies
- [ ] Record findings, remediation, and escalation items
- [ ] Complete weekday-specific deep-review tasks

---

# Weekly Summary Template

## Suggested headings

- Major incidents this week
- Systems with recurring alerts
- Capacity risks
- Backup failures and recovery concerns
- AAP, GitLab, and Satellite issues
- Patch and vulnerability concerns
- High-risk legacy systems
- Planned maintenance and recommended actions

---

# Notes

- This runbook is designed for operational consistency, not exhaustive host-by-host manual inspection.
- Where possible, add links in your GitHub project to platform-specific procedures, automation playbooks, escalation contacts, and recovery runbooks.
- Review this schedule quarterly and adjust time estimates based on real alert volume and automation maturity.

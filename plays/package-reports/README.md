# Ansible package inventory report

Author: Steve Maher

This contains:

- `package_report.yml` — connectivity checks, Linux/Windows package collection, and report rendering.
- `package_report.html.j2` — HTML package matrix report styled to match the VMware placement report.

## Inventory expectation

Each managed host should have one of:

```yaml
os_type: linux
```

or:

```yaml
os_type: windows
```

## Run Linux only

```bash
ansible-playbook -i inventory package_report.yml \
  -e enable_linux_report=true \
  -e enable_windows_report=false
```

## Run Windows only

```bash
ansible-playbook -i inventory package_report.yml \
  -e enable_linux_report=false \
  -e enable_windows_report=true
```

## Run both

```bash
ansible-playbook -i inventory package_report.yml \
  -e enable_linux_report=true \
  -e enable_windows_report=true
```

Reports are written to `reports/linux_package_report.html` and/or `reports/windows_package_report.html` relative to the playbook directory unless `package_report_output_dir` is overridden.

Windows collection requires the `ansible.windows` collection and working WinRM/PSRP configuration for reachable Windows hosts.

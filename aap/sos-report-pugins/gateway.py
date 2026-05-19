# sos plugin for the gateway for rh issues as non exist in 2.5
# ------------------------------------------------------------------

try:
    from sos.plugins import Plugin, RedHatPlugin
except ImportError:
    from sos.report.plugins import Plugin, RedHatPlugin

SOSREPORT_GATEWAY_COMMANDS = [
    "aap-gateway-manage --version",  # gateway version
    "aap-gateway-manage list_services",  # gateway cluster configuration
    "tree -d /etc/ansible-automation-platform",  # show me the dirs
    "umask -p",  # check current umask
]


SOSREPORT_GATEWAY_DIRS = [
    "/var/log/ansible-automation-platform/gateway/",
    "/etc/ansible-automation-platform/gateway/",
    "/etc/supervisord.conf",
    "/etc/supervisord.d/",
    "/etc/nginx/",
    "/var/log/supervisor",
    "/var/log/redis",
    "/var/log/dist-upgrade",
    "/var/log/installer",
    "/var/log/unattended-upgrades",
]

SOSREPORT_FORBIDDEN_PATHS = [
    "/etc/ansible-automation-platform/gateway/SECRET_KEY",
    "/etc/ansible-automation-platform/gateway/cache.cert",
    "/etc/ansible-automation-platform/gateway/cache.key"
]


class Controller(Plugin, RedHatPlugin):
    '''Collect Ansible Automation Platform gateway information'''

    plugin_name = "gateway"
    short_desc = "Ansible Automation Platform gateway information"

    def setup(self):
        for path in SOSREPORT_GATEWAY_DIRS:
            self.add_copy_spec(path)

        for path in SOSREPORT_FORBIDDEN_PATHS:
            self.add_forbidden_path(path)

        self.add_cmd_output(SOSREPORT_GATEWAY_COMMANDS)

    def postproc(self):

        # remove password
        jreg = r"(PASSWORD\s*=)\'(.+)\'"
        repl = r"\1********"
        self.do_path_regex_sub("/etc/ansible-automation-platform/gateway/settings.py", jreg, repl)

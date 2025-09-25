#!/usr/bin/env python3
"""
Inventory-driven multi-remote console (SSH + WinRM), native Ansible inventory.
Steve Maher

Usage:
    python ansible-ssh-console INVENTORY_PATH

Features:
  - Native Ansible inventory loading (static/dynamic/plugins/dirs)
  - Multiple concurrent sessions; keep others open while switching
  - Ctrl+Tab / Shift+Ctrl+Tab to switch
  - Per-host output buffers, Ctrl+S to save buffers to ./buffers
  - SSH auth: key > password > ssh-agent > prompt (once)
  - Auto-accept host keys by default; respect ansible_host_key_checking=true
  - WinRM 'pseudo terminal': enter sends a PowerShell line, response is shown

Dependencies:
    pip install ansible-core asyncssh textual PyYAML pywinrm
"""

import asyncio
import os
import sys
import getpass
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

# Ansible inventory API
from ansible.parsing.dataloader import DataLoader
from ansible.inventory.manager import InventoryManager
from ansible.vars.manager import VariableManager

# SSH
import asyncssh

# WinRM
try:
    import winrm  # type: ignore
except Exception:
    winrm = None  # handled at runtime if needed

# Textual UI
from textual.app import App, ComposeResult
from textual.widgets import Static, Header, Footer
from textual.containers import Horizontal
from textual.reactive import reactive
from textual import events

# -------------------- Utilities --------------------

def ts() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")

_password_cache: Dict[str, str] = {}

def prompt_for_password(prompt_label: str, cache_key: str) -> str:
    if cache_key not in _password_cache:
        pw = getpass.getpass(f"{prompt_label}: ")
        _password_cache[cache_key] = pw
    return _password_cache[cache_key]

def expanduser_path(p: Optional[str]) -> Optional[str]:
    return os.path.expanduser(p) if p else p

# -------------------- Ansible Inventory --------------------

def load_inventory(source: Path) -> Dict[str, Dict[str, Any]]:
    """Use Ansible APIs to natively load inventory and return per-host vars."""
    loader = DataLoader()
    inventory = InventoryManager(loader=loader, sources=[str(source)])
    variable_manager = VariableManager(loader=loader, inventory=inventory)

    hosts: Dict[str, Dict[str, Any]] = {}
    for host in inventory.get_hosts():
        v = variable_manager.get_vars(host=host)

        # Normalize booleans that may arrive as strings
        def to_bool(val, default=None):
            if isinstance(val, bool):
                return val
            if isinstance(val, str):
                lv = val.strip().lower()
                if lv in ("true", "yes", "1", "on"):
                    return True
                if lv in ("false", "no", "0", "off"):
                    return False
            return default

        entry = {
            "name": host.name,
            "host": v.get("ansible_host", host.name),
            "user": v.get("ansible_user"),
            "connection": v.get("ansible_connection", "ssh"),
            "port": int(v.get("ansible_port", 22)) if str(v.get("ansible_port", "")).strip() else 22,
            "key": expanduser_path(v.get("ansible_ssh_private_key_file")),
            "password": v.get("ansible_password") or v.get("ansible_ssh_pass"),
            "become_password": v.get("ansible_become_password"),
            "common_args": v.get("ansible_ssh_common_args"),
            "host_key_checking": to_bool(v.get("ansible_host_key_checking"), default=None),

            # WinRM specifics (defaults match Ansible expectations)
            "winrm_transport": v.get("ansible_winrm_transport", "ntlm"),
            "winrm_scheme": v.get("ansible_winrm_scheme", "https"),
            "winrm_cert_validation": v.get("ansible_winrm_server_cert_validation", "ignore"),
        }

        # Default WinRM port if connection is winrm and ansible_port not explicit
        if entry["connection"] == "winrm":
            try:
                p = v.get("ansible_port")
                entry["port"] = int(p) if p else (5986 if entry["winrm_scheme"] == "https" else 5985)
            except Exception:
                entry["port"] = 5986 if entry["winrm_scheme"] == "https" else 5985

        hosts[host.name] = entry
    return hosts

# -------------------- Session Abstractions --------------------

class BaseSession:
    """Interface both SSH and WinRM sessions implement."""
    def __init__(self, name: str):
        self.name = name
        self.connected: bool = False
        self.closed: bool = False
        self._lines: List[str] = []

    def _append(self, line: str) -> None:
        self._lines.append(f"{ts()} {line}")
        if len(self._lines) > 10000:
            self._lines = self._lines[-8000:]

    def get_output_lines(self, max_lines: int = 500) -> List[str]:
        return self._lines[-max_lines:]

    async def connect(self) -> None:
        raise NotImplementedError

    async def handle_key(self, key: str) -> None:
        """Handle a textual key press. SSH receives raw bytes; WinRM buffers lines until Enter."""
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError

    async def save_buffer(self, outdir: Path) -> None:
        outdir.mkdir(parents=True, exist_ok=True)
        fname = outdir / f"{self.name.replace('/','_')}.log"
        with fname.open("a", encoding="utf-8") as f:
            f.write("\n".join(self._lines) + "\n")

# -------------------- SSH Session --------------------

class SSHSession(BaseSession):
    def __init__(
        self,
        name: str,
        host: str,
        user: Optional[str],
        port: int,
        key: Optional[str],
        password: Optional[str],
        host_key_checking: Optional[bool],
    ):
        super().__init__(name)
        self.host = host
        self.user = user
        self.port = port
        self.key = key
        self.password = password
        self.host_key_checking = host_key_checking

        self.conn: Optional[asyncssh.SSHClientConnection] = None
        self.proc: Optional[asyncssh.SSHClientProcess] = None

    async def connect(self) -> None:
        opts: Dict[str, Any] = {
            "username": self.user,
            "port": self.port,
        }

        # Host key behavior: default auto-accept (known_hosts=None)
        # If host_key_checking explicitly True, let asyncssh do default verification.
        if self.host_key_checking is not True:
            opts["known_hosts"] = None

        auth_msg = "[auth: "
        # Priority 1: explicit private key
        if self.key:
            opts["client_keys"] = [self.key]
            opts["agent_forwarding"] = False
            opts["agent_path"] = None
            auth_msg += f"private-key {self.key}]"
        else:
            # Priority 2: password (if provided)
            if self.password:
                opts["password"] = self.password
                auth_msg += "password]"
            else:
                # Priority 3: ssh-agent if available
                agent_sock = os.environ.get("SSH_AUTH_SOCK")
                if agent_sock and os.path.exists(agent_sock):
                    opts["agent_path"] = agent_sock
                    opts["agent_forwarding"] = True
                    auth_msg += "ssh-agent]"
                else:
                    # Nothing? Prompt once.
                    pw = prompt_for_password(f"SSH password for {self.user or ''}@{self.host}", f"ssh:{self.user}@{self.host}")
                    opts["password"] = pw
                    auth_msg += "password (prompted)]"

        try:
            self.conn = await asyncssh.connect(self.host, **opts)
            # Start a shell
            self.proc, _ = await self.conn.create_session(
                lambda: _SSHClientHandler(self),
                term_type="xterm",
                term_size=(120, 36),
            )
            self.connected = True
            self._append(f"[connected to {self.host}]")
            self._append(auth_msg)
        except Exception as e:
            self.connected = False
            self._append(f"[connection error] {e}")

    async def handle_key(self, key: str) -> None:
        if not self.proc:
            return
        # Map textual keys to bytes
        if key == "enter":
            data = "\n".encode()
        elif key == "backspace":
            data = "\x7f".encode()
        elif key == "tab":
            data = "\t".encode()
        elif key == "space":
            data = " ".encode()
        elif len(key) == 1:
            data = key.encode()
        else:
            # ignore other special keys for now
            return
        try:
            self.proc.stdin.write(data)
        except Exception as e:
            self._append(f"[send error] {e}")

    async def close(self) -> None:
        self.closed = True
        try:
            if self.proc:
                self.proc.stdin.write_eof()
        except Exception:
            pass
        try:
            if self.conn:
                self.conn.close()
                await self.conn.wait_closed()
        except Exception:
            pass
        self._append("[ssh closed]")


class _SSHClientHandler(asyncssh.SSHClientSession):
    def __init__(self, sess: SSHSession):
        self.sess = sess

    def data_received(self, data, datatype):
        # datatype may be 1 for stderr
        d = data.replace("\r\n", "\n")
        for line in d.splitlines():
            self.sess._append(line if line else "")

    def connection_lost(self, exc):
        self.sess.connected = False
        self.sess._append("[remote closed connection]")

# -------------------- WinRM Session (pseudo terminal) --------------------

class WinRMSession(BaseSession):
    """
    Pseudo-terminal: we buffer a line locally; on Enter we run it remotely
    via PowerShell and stream the result back into the buffer.
    """
    def __init__(
        self,
        name: str,
        host: str,
        user: Optional[str],
        password: Optional[str],
        port: int,
        scheme: str,
        transport: str,
        cert_validation: str = "ignore",
    ):
        super().__init__(name)
        self.host = host
        self.user = user or ""
        self.password = password
        self.port = port
        self.scheme = scheme
        self.transport = transport
        self.cert_validation = cert_validation
        self._input_line: List[str] = []

        self._session: Optional["winrm.Session"] = None

    async def connect(self) -> None:
        if winrm is None:
            self._append("[error] pywinrm not installed. pip install pywinrm")
            return
        if not self.password:
            # WinRM needs a password unless you configure other auth
            self.password = prompt_for_password(f"WinRM password for {self.user}@{self.host}", f"winrm:{self.user}@{self.host}")

        endpoint = f"{self.scheme}://{self.host}:{self.port}/wsman"
        try:
            self._session = winrm.Session(
                endpoint,
                auth=(self.user, self.password),
                transport=self.transport,
                server_cert_validation=self.cert_validation,
            )
            # simple probe
            r = await asyncio.to_thread(self._session.run_ps, "$PSVersionTable.PSVersion")
            if r.status_code != 0:
                self._append(f"[connect warning] {r.std_err.decode(errors='ignore')}")
            self.connected = True
            self._append(f"[connected to {self.host} via WinRM/{self.transport}]")
            self._append("[type PowerShell commands, press Enter to run]")
        except Exception as e:
            self.connected = False
            self._append(f"[connection error] {e}")

    async def handle_key(self, key: str) -> None:
        if not self._session:
            return
        if key == "enter":
            cmd = "".join(self._input_line).strip()
            self._input_line.clear()
            if not cmd:
                self._append("")
                return
            self._append(f"> {cmd}")
            try:
                # Run on a background thread (pywinrm is blocking)
                result = await asyncio.to_thread(self._session.run_ps, cmd)
                out = result.std_out.decode(errors="ignore")
                err = result.std_err.decode(errors="ignore")
                if out:
                    for line in out.replace("\r\n", "\n").splitlines():
                        self._append(line)
                if err:
                    for line in err.replace("\r\n", "\n").splitlines():
                        self._append(f"[err] {line}")
                self._append(f"[exit {result.status_code}]")
            except Exception as e:
                self._append(f"[exec error] {e}")
        elif key == "backspace":
            if self._input_line:
                self._input_line.pop()
        elif key == "tab":
            self._input_line.append("\t")  # simple insert
        elif key == "space":
            self._input_line.append(" ")
        elif len(key) == 1:
            self._input_line.append(key)
        # render current input line as a prompt
        prompt = "> " + "".join(self._input_line)
        # Show prompt as an updating line (lightweight: append on change)
        self._append(prompt)

    async def close(self) -> None:
        self.closed = True
        self._append("[winrm closed]")

# -------------------- Textual UI --------------------

class HostPane(Static):
    def __init__(self, session: BaseSession, **kwargs):
        super().__init__(**kwargs)
        self.session = session
        self._visible_lines = 400

    def render(self) -> str:
        header = f"[{self.session.name}] connected={self.session.connected} closed={self.session.closed}\n"
        body = "\n".join(self.session.get_output_lines(self._visible_lines))
        return header + body

class ConsoleApp(App):
    BINDINGS = [
        ("ctrl+tab", "next_tab", "Next"),
        ("shift+ctrl+tab", "prev_tab", "Prev"),
        ("ctrl+s", "save_buffers", "Save"),
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
    ]

    def __init__(self, sessions: List[BaseSession]):
        super().__init__()
        self.sessions = sessions
        self.current_index = reactive(0)
        self.panes: List[HostPane] = []
        self._refresh_task: Optional[asyncio.Task] = None

    async def compose(self) -> ComposeResult:
        yield Header()
        row = Horizontal()
        for s in self.sessions:
            p = HostPane(s)
            self.panes.append(p)
            row.mount(p)
        yield row
        yield Footer()

    async def on_mount(self) -> None:
        # start periodic refresh
        self._refresh_task = asyncio.create_task(self._periodic_refresh())
        # kick off connections
        for s in self.sessions:
            asyncio.create_task(s.connect())

    async def _periodic_refresh(self):
        while True:
            try:
                # Only show active pane
                for i, p in enumerate(self.panes):
                    p.visible = (i == self.current_index)
                    p.refresh(layout=True)
                await asyncio.sleep(0.2)
            except asyncio.CancelledError:
                break

    async def action_next_tab(self):
        if self.sessions:
            self.current_index = (self.current_index + 1) % len(self.sessions)

    async def action_prev_tab(self):
        if self.sessions:
            self.current_index = (self.current_index - 1) % len(self.sessions)

    async def action_save_buffers(self):
        outdir = Path("./buffers")
        for s in self.sessions:
            await s.save_buffer(outdir)
        self.exit(message="Saved buffers to ./buffers")

    async def action_quit(self):
        await self.shutdown()
        self.exit()

    async def shutdown(self):
        for s in self.sessions:
            try:
                await s.close()
            except Exception:
                pass
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except Exception:
                pass

    async def on_key(self, event: events.Key) -> None:
        # Bound keys are routed via actions; others we hand to the active session
        # We ignore ctrl+tab combos here (handled by actions)
        special = {"ctrl+tab", "shift+ctrl+tab", "ctrl+s", "ctrl+c", "q"}
        if event.key in special:
            return
        if not self.sessions:
            return
        active = self.sessions[self.current_index]
        # normalize key names similar to our handlers
        key = event.key
        await active.handle_key(key)

# -------------------- Session Factory --------------------

def build_sessions(hosts: Dict[str, Dict[str, Any]]) -> List[BaseSession]:
    sessions: List[BaseSession] = []
    for name, meta in hosts.items():
        connection = str(meta.get("connection", "ssh")).lower()
        user = meta.get("user")
        if connection == "winrm":
            sess = WinRMSession(
                name=name,
                host=meta["host"],
                user=user,
                password=meta.get("password"),
                port=int(meta["port"]),
                scheme=meta.get("winrm_scheme", "https"),
                transport=meta.get("winrm_transport", "ntlm"),
                cert_validation=str(meta.get("winrm_cert_validation", "ignore")),
            )
        else:
            sess = SSHSession(
                name=name,
                host=meta["host"],
                user=user,
                port=int(meta["port"]),
                key=meta.get("key"),
                password=meta.get("password"),
                host_key_checking=meta.get("host_key_checking"),
            )
        sessions.append(sess)
    return sessions

# -------------------- Main --------------------

async def main_async(inv_path: Path):
    hosts = load_inventory(inv_path)
    if not hosts:
        print("No hosts found in inventory.")
        return
    sessions = build_sessions(hosts)
    app = ConsoleApp(sessions)
    await app.run_async()

def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py /path/to/inventory")
        sys.exit(1)
    inv = Path(sys.argv[1]).expanduser()
    if not inv.exists():
        print(f"Inventory not found: {inv}")
        sys.exit(2)
    asyncio.run(main_async(inv))

if __name__ == "__main__":
    main()
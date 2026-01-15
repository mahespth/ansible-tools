#!/usr/bin/env python3

"""
  aap_tui(2) Steve Maher

  python aap_tui.py --url https://your-gateway.example.com --token YOUR_TOKEN
  
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
    TextArea,
    Tree,
)

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


SPLIT_RE = re.compile(r"\s*-\s*")


@dataclass(frozen=True)
class TemplatePath:
    org: str
    folders: Tuple[str, ...]
    display_name: str


def derive_path(org_name: str, template_name: str, known_prefixes: Tuple[str, ...]) -> TemplatePath:
    raw_parts = [p.strip() for p in SPLIT_RE.split(template_name.strip()) if p.strip()]
    if not raw_parts:
        return TemplatePath(org_name, tuple(), template_name.strip())

    first = raw_parts[0].lower()
    prefix_set = {p.lower() for p in known_prefixes}
    if first in prefix_set and len(raw_parts) >= 2:
        # admin - users - add  => folders: admin/users ; display: add
        folders = tuple([raw_parts[0]] + raw_parts[1:-1])
        display = raw_parts[-1]
        return TemplatePath(org_name, folders, display)

    return TemplatePath(org_name, tuple(), template_name.strip())


def parse_vars(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {}
    # Prefer YAML if available (handles JSON too)
    if yaml is not None:
        obj = yaml.safe_load(text)
        if obj is None:
            return {}
        if not isinstance(obj, dict):
            raise ValueError("extra_vars must be a mapping (YAML/JSON object).")
        return obj
    # Fallback to JSON only
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("extra_vars must be a JSON object.")
    return obj


class AAPClient:
    def __init__(self, base_url: str, token: str, timeout_s: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=timeout_s,
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def _get_all(self, path: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        url = path
        p = params or {}
        while True:
            r = await self.client.get(url, params=p)
            r.raise_for_status()
            data = r.json()
            results = data.get("results", [])
            if not isinstance(results, list):
                raise RuntimeError("Unexpected API response shape")
            out.extend(results)
            next_url = data.get("next")
            if not next_url:
                break
            # next is typically absolute; httpx base_url can still handle it
            url = next_url
            p = {}  # already encoded in next
        return out

    async def list_job_templates(self) -> List[Dict[str, Any]]:
        # Via gateway: /api/controller/v2/...
        return await self._get_all(
            "/api/controller/v2/job_templates/",
            params={"page_size": 200, "order_by": "name"},
        )

    async def get_job_template(self, template_id: int) -> Dict[str, Any]:
        r = await self.client.get(f"/api/controller/v2/job_templates/{template_id}/")
        r.raise_for_status()
        return r.json()

    async def get_launch_info(self, template_id: int) -> Dict[str, Any]:
        r = await self.client.get(f"/api/controller/v2/job_templates/{template_id}/launch/")
        r.raise_for_status()
        return r.json()

    async def get_survey_spec(self, template_id: int) -> Dict[str, Any]:
        r = await self.client.get(f"/api/controller/v2/job_templates/{template_id}/survey_spec/")
        # Some templates may not have surveys enabled; controller can return 404
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        return r.json()

    async def launch_template(self, template_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = await self.client.post(f"/api/controller/v2/job_templates/{template_id}/launch/", json=payload)
        r.raise_for_status()
        return r.json()

    async def get_job(self, job_id: int) -> Dict[str, Any]:
        r = await self.client.get(f"/api/controller/v2/jobs/{job_id}/")
        r.raise_for_status()
        return r.json()

    async def get_job_stdout_txt(self, job_id: int) -> str:
        r = await self.client.get(f"/api/controller/v2/jobs/{job_id}/stdout/", params={"format": "txt"})
        r.raise_for_status()
        return r.text


@dataclass
class JobState:
    job_id: int
    template_id: int
    status: str = "unknown"
    started: Optional[str] = None
    finished: Optional[str] = None
    last_stdout_len: int = 0
    cached_stdout: str = ""


class ExplorerItem:
    """Marker class for tree node data."""


@dataclass
class TemplateItem(ExplorerItem):
    template_id: int
    org_name: str
    full_name: str


@dataclass
class JobItem(ExplorerItem):
    job_id: int
    template_id: int


class TemplateSelected(Message):
    def __init__(self, template: TemplateItem) -> None:
        self.template = template
        super().__init__()


class JobSelected(Message):
    def __init__(self, job: JobItem) -> None:
        self.job = job
        super().__init__()


class AAPTui(App):
    CSS = """
    #root { height: 100%; }
    #main { height: 1fr; }
    #left { width: 42%; border: solid $panel; }
    #right { width: 58%; border: solid $panel; }
    #details { padding: 1 1; border-bottom: solid $panel; }
    #form { padding: 1 1; border-bottom: solid $panel; }
    #output { height: 1fr; }
    .section_title { text-style: bold; }
    .field_row { height: auto; padding: 0 0 1 0; }
    """

    BINDINGS = [
        ("tab", "focus_next", "Next pane"),
        ("shift+tab", "focus_previous", "Prev pane"),
        ("r", "refresh_templates", "Refresh"),
        ("q", "quit", "Quit"),
    ]

    status_text: reactive[str] = reactive("Disconnected")
    selected_template_id: reactive[Optional[int]] = reactive(None)
    selected_job_id: reactive[Optional[int]] = reactive(None)

    def __init__(self, base_url: str, token: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.token = token
        self.client = AAPClient(base_url, token)

        self.tree: Tree[ExplorerItem] | None = None
        self.details = Static("")
        self.form_container = Container()
        self.output = TextArea()
        self.execute_btn = Button("Execute", id="execute", variant="success")

        self.limit_in = Input(placeholder="limit (optional)", id="limit")
        self.tags_in = Input(placeholder="job_tags (comma-separated, optional)", id="job_tags")
        self.skip_tags_in = Input(placeholder="skip_tags (comma-separated, optional)", id="skip_tags")
        self.extra_vars = TextArea("", id="extra_vars")
        self.extra_vars.border_title = "extra_vars (YAML/JSON mapping)"

        self.known_prefixes = ("admin", "ops", "net", "sec", "db")

        self.templates_by_id: Dict[int, Dict[str, Any]] = {}
        self.template_items: Dict[int, TemplateItem] = {}
        self.template_node_by_id: Dict[int, Any] = {}

        self.jobs: Dict[int, JobState] = {}  # job_id -> state
        self.job_node_by_id: Dict[int, Any] = {}

        self.survey_widgets_by_var: Dict[str, Any] = {}  # var -> widget

        self.launch_info_cache: Dict[int, Dict[str, Any]] = {}
        self.survey_spec_cache: Dict[int, Dict[str, Any]] = {}

        self._poll_task: Optional[asyncio.Task] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main"):
            with Vertical(id="left"):
                yield Label(f"AAP: {self.base_url}", id="conn")
                self.tree = Tree("Templates", id="tree")
                self.tree.root.expand()
                yield self.tree
            with Vertical(id="right"):
                with VerticalScroll(id="details"):
                    yield Label("Details", classes="section_title")
                    yield self.details
                with VerticalScroll(id="form"):
                    yield Label("Launch", classes="section_title")
                    yield self.limit_in
                    yield self.tags_in
                    yield self.skip_tags_in
                    yield self.extra_vars
                    yield self.form_container
                    yield self.execute_btn
                self.output.read_only = True
                self.output.border_title = "Output"
                yield self.output
        yield Footer()

    async def on_mount(self) -> None:
        self.status_text = "Connecting…"
        await self.refresh_templates()

        # Poll job status/stdout
        self._poll_task = asyncio.create_task(self._poll_jobs_loop())

        self.status_text = "Ready"

    async def on_unmount(self) -> None:
        if self._poll_task:
            self._poll_task.cancel()
        await self.client.close()

    def watch_status_text(self, new: str) -> None:
        self.query_one("#conn", Label).update(f"AAP: {self.base_url}  |  {new}")

    async def action_refresh_templates(self) -> None:
        await self.refresh_templates()

    async def refresh_templates(self) -> None:
        if self.tree is None:
            return
        self.status_text = "Loading templates…"
        self.tree.root.remove_children()
        self.templates_by_id.clear()
        self.template_items.clear()
        self.template_node_by_id.clear()

        try:
            templates = await self.client.list_job_templates()
        except Exception as e:
            self.status_text = f"Error: {e}"
            return

        # Build tree by org -> derived folders -> templates
        org_nodes: Dict[str, Any] = {}
        for t in templates:
            tid = int(t["id"])
            name = str(t.get("name", f"template-{tid}"))
            org_name = "Unknown Org"
            summary_fields = t.get("summary_fields") or {}
            org = (summary_fields.get("organization") or {}).get("name")
            if org:
                org_name = str(org)

            self.templates_by_id[tid] = t
            item = TemplateItem(template_id=tid, org_name=org_name, full_name=name)
            self.template_items[tid] = item

            if org_name not in org_nodes:
                org_nodes[org_name] = self.tree.root.add(org_name, data=None, expand=False)

            path = derive_path(org_name, name, self.known_prefixes)
            parent = org_nodes[org_name]
            # add folders
            for folder in path.folders:
                # reuse existing folder node if present
                child = None
                for n in parent.children:
                    if n.label.plain == folder:
                        child = n
                        break
                if child is None:
                    child = parent.add(folder, data=None, expand=False)
                parent = child

            node_label = path.display_name
            node = parent.add(node_label, data=item, expand=False)
            self.template_node_by_id[tid] = node

        # expand org nodes by default
        for n in org_nodes.values():
            n.expand()

        self.status_text = f"Loaded {len(templates)} templates"

    @on(Tree.NodeSelected)
    async def on_tree_selected(self, event: Tree.NodeSelected) -> None:
        data = event.node.data
        if isinstance(data, TemplateItem):
            self.selected_job_id = None
            self.selected_template_id = data.template_id
            await self.post_message(TemplateSelected(data))
        elif isinstance(data, JobItem):
            self.selected_template_id = data.template_id
            self.selected_job_id = data.job_id
            await self.post_message(JobSelected(data))

    @on(TemplateSelected)
    async def handle_template_selected(self, msg: TemplateSelected) -> None:
        tid = msg.template.template_id
        self.output.clear()
        self.output.border_title = "Output"
        self.details.update("Loading…")
        self.form_container.remove_children()
        self.survey_widgets_by_var.clear()

        # template details
        try:
            tmpl = await self.client.get_job_template(tid)
            launch_info = self.launch_info_cache.get(tid) or await self.client.get_launch_info(tid)
            self.launch_info_cache[tid] = launch_info
            survey_spec = self.survey_spec_cache.get(tid)
            if survey_spec is None:
                survey_spec = await self.client.get_survey_spec(tid)
                self.survey_spec_cache[tid] = survey_spec
        except Exception as e:
            self.details.update(f"[b]Error[/b]\n{e}")
            return

        # details panel
        desc = tmpl.get("description") or ""
        proj = ((tmpl.get("summary_fields") or {}).get("project") or {}).get("name") or ""
        pb = tmpl.get("playbook") or ""
        org = ((tmpl.get("summary_fields") or {}).get("organization") or {}).get("name") or ""
        self.details.update(
            f"[b]{tmpl.get('name','')}[/b]\n"
            f"Org: {org}\n"
            f"Project: {proj}\n"
            f"Playbook: {pb}\n\n"
            f"{desc}"
        )

        # Build survey widgets (common types)
        questions = (survey_spec or {}).get("spec") or []
        if questions:
            self.form_container.mount(Label("Survey", classes="section_title"))
        for q in questions:
            var = str(q.get("variable") or "")
            qtype = str(q.get("type") or "text")
            prompt = str(q.get("question_name") or var or "question")
            required = bool(q.get("required"))
            default = q.get("default")

            label = Label(f"{prompt}{' *' if required else ''}")
            self.form_container.mount(label)

            widget = self._widget_for_survey_question(qtype, q)
            # set default if possible
            try:
                if default is not None:
                    if isinstance(widget, Input):
                        widget.value = str(default)
                    elif isinstance(widget, TextArea):
                        widget.text = str(default)
                    elif isinstance(widget, Select):
                        # try to match option value
                        widget.value = str(default)
            except Exception:
                pass

            self.survey_widgets_by_var[var] = widget
            self.form_container.mount(widget)

        # Show running jobs under template as children (if any)
        self._ensure_job_children_for_template(tid)

    def _widget_for_survey_question(self, qtype: str, q: Dict[str, Any]):
        qtype = qtype.lower().strip()
        if qtype in ("text", "textarea", "password", "integer", "float"):
            inp = Input(password=(qtype == "password"))
            inp.placeholder = qtype
            return inp
        if qtype in ("multiplechoice", "multiselect"):
            # choices can be a string with newlines in controller survey specs
            choices = q.get("choices", "")
            if isinstance(choices, str):
                opts = [c.strip() for c in choices.splitlines() if c.strip()]
            elif isinstance(choices, list):
                opts = [str(c) for c in choices]
            else:
                opts = []
            if qtype == "multiplechoice":
                return Select([(o, o) for o in opts], prompt="Select…")
            # multiselect: simplest MVP as comma-separated input
            inp = Input()
            inp.placeholder = "comma-separated selections"
            return inp
        # fallback
        inp = Input()
        inp.placeholder = qtype
        return inp

    @on(JobSelected)
    async def handle_job_selected(self, msg: JobSelected) -> None:
        job_id = msg.job.job_id
        self.output.clear()
        self.output.border_title = f"Job {job_id} Output"
        await self._refresh_job_output(job_id, full=True)

    @on(Button.Pressed, "#execute")
    async def on_execute(self, event: Button.Pressed) -> None:
        tid = self.selected_template_id
        if tid is None:
            self.status_text = "No template selected"
            return

        # Build payload
        payload: Dict[str, Any] = {}
        limit = self.limit_in.value.strip()
        if limit:
            payload["limit"] = limit

        tags = self.tags_in.value.strip()
        if tags:
            payload["job_tags"] = tags

        skip_tags = self.skip_tags_in.value.strip()
        if skip_tags:
            payload["skip_tags"] = skip_tags

        # Gather survey answers into extra_vars
        extra: Dict[str, Any] = {}
        # user-entered extra_vars YAML/JSON
        try:
            extra.update(parse_vars(self.extra_vars.text))
        except Exception as e:
            self.status_text = f"extra_vars error: {e}"
            return

        for var, widget in self.survey_widgets_by_var.items():
            if not var:
                continue
            val: Any = None
            if isinstance(widget, Input):
                val = widget.value
            elif isinstance(widget, TextArea):
                val = widget.text
            elif isinstance(widget, Select):
                val = widget.value
            else:
                try:
                    val = getattr(widget, "value", None)
                except Exception:
                    val = None
            if val is None or (isinstance(val, str) and val.strip() == ""):
                continue
            extra[var] = val

        if extra:
            payload["extra_vars"] = extra

        self.status_text = "Launching…"
        try:
            resp = await self.client.launch_template(tid, payload)
        except Exception as e:
            self.status_text = f"Launch failed: {e}"
            return

        job_id = resp.get("job")
        if not job_id:
            # Sometimes controller returns "id" or errors; show response
            self.status_text = "Launch returned no job id"
            self.output.clear()
            self.output.border_title = "Launch response"
            self.output.insert(json.dumps(resp, indent=2))
            return

        job_id = int(job_id)
        self.jobs[job_id] = JobState(job_id=job_id, template_id=tid, status="running")
        self._attach_job_node(job_id, tid)
        self._update_template_marker(tid)

        self.selected_job_id = job_id
        self.output.clear()
        self.output.border_title = f"Job {job_id} Output"
        self.status_text = f"Launched job {job_id}"

    def _attach_job_node(self, job_id: int, template_id: int) -> None:
        if self.tree is None:
            return
        template_node = self.template_node_by_id.get(template_id)
        if template_node is None:
            return

        # ensure child nodes are visible
        template_node.expand()
        label = f"job {job_id}  ⏳"
        node = template_node.add(label, data=JobItem(job_id=job_id, template_id=template_id), expand=False)
        self.job_node_by_id[job_id] = node

    def _ensure_job_children_for_template(self, template_id: int) -> None:
        # If jobs exist for this template, ensure nodes exist
        for job_id, js in list(self.jobs.items()):
            if js.template_id != template_id:
                continue
            if job_id not in self.job_node_by_id:
                self._attach_job_node(job_id, template_id)

    def _update_template_marker(self, template_id: int) -> None:
        node = self.template_node_by_id.get(template_id)
        if node is None:
            return
        running = any(js.template_id == template_id and js.status in ("running", "pending", "waiting")
                      for js in self.jobs.values())
        base_label = node.label.plain
        # Remove old marker
        base_label = base_label.replace(" ●", "").replace(" ⏳", "")
        node.set_label(base_label + (" ●" if running else ""))

    async def _poll_jobs_loop(self) -> None:
        while True:
            try:
                await self._poll_jobs_once()
            except asyncio.CancelledError:
                return
            except Exception:
                # keep app alive even if polling fails temporarily
                pass
            await asyncio.sleep(1.0)

    async def _poll_jobs_once(self) -> None:
        if not self.jobs:
            return

        # Update each job status and stdout if selected
        for job_id, js in list(self.jobs.items()):
            try:
                job = await self.client.get_job(job_id)
            except Exception:
                continue

            status = str(job.get("status") or "unknown")
            js.status = status
            js.started = job.get("started")
            js.finished = job.get("finished")

            # update job node label
            node = self.job_node_by_id.get(job_id)
            if node is not None:
                marker = "⏳" if status in ("running", "pending", "waiting") else ("✅" if status == "successful" else "❌")
                node.set_label(f"job {job_id}  {marker}")

            # update template marker
            self._update_template_marker(js.template_id)

            # if this job is selected, refresh output incrementally
            if self.selected_job_id == job_id:
                await self._refresh_job_output(job_id, full=False)

            # Optionally prune finished jobs later (keep for now)

    async def _refresh_job_output(self, job_id: int, full: bool) -> None:
        js = self.jobs.get(job_id)
        try:
            txt = await self.client.get_job_stdout_txt(job_id)
        except Exception as e:
            if full:
                self.output.insert(f"Error fetching stdout: {e}\n")
            return

        if js is None:
            js = JobState(job_id=job_id, template_id=self.selected_template_id or -1)
            self.jobs[job_id] = js

        if full:
            js.cached_stdout = txt
            js.last_stdout_len = len(txt)
            self.output.clear()
            self.output.insert(txt)
            self.output.move_cursor_end()
            return

        # incremental append
        if len(txt) > js.last_stdout_len:
            delta = txt[js.last_stdout_len :]
            js.cached_stdout = txt
            js.last_stdout_len = len(txt)
            self.output.insert(delta)
            self.output.move_cursor_end()


def main() -> None:
    p = argparse.ArgumentParser(description="AAP template runner TUI")
    p.add_argument("--url", default=os.environ.get("AAP_URL", "").strip(), help="AAP Gateway base URL")
    p.add_argument("--token", default=os.environ.get("AAP_TOKEN", "").strip(), help="Bearer token")
    args = p.parse_args()

    if not args.url:
        raise SystemExit("Missing --url or AAP_URL")
    if not args.token:
        raise SystemExit("Missing --token or AAP_TOKEN")

    app = AAPTui(args.url, args.token)
    app.run()


if __name__ == "__main__":
    main()

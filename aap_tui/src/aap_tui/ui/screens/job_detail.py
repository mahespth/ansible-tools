from __future__ import annotations

import asyncio
import contextlib
from typing import Optional

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Label, Log

from ...services.controller import ControllerClient
from ...models.jobs import Job, JobEvent
from ...models.common import Paginated

class JobDetailScreen(Screen):
    BINDINGS = [
        ("q", "pop_screen", "Back"),
        ("s", "toggle_follow", "Follow/Unfollow"),
        ("e", "export_stdout", "Export stdout"),
        ("/", "focus_search", "Search in log"),
    ]

    def __init__(self, client: ControllerClient, job_id: int, *, follow: bool = True) -> None:
        super().__init__()
        self.client = client
        self.job_id = job_id
        self.follow_enabled = follow
        self._last_counter = 0
        self._poll_task: Optional[asyncio.Task] = None
        self._status_task: Optional[asyncio.Task] = None
        self._terminal = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Label(f"Job #{self.job_id}", id="job-title")
        yield Log(id="stdout", highlight=True)
        yield Footer()

    @property
    def log_widget(self) -> Log:
        return self.query_one("#stdout", Log)

    async def on_mount(self) -> None:
        job_raw = await asyncio.to_thread(self.client.job, self.job_id)
        job = Job.model_validate(job_raw)
        self._terminal = job.is_terminal
        self.query_one("#job-title", Label).update(f"Job #{job.id} — {job.name} [{job.status}]")
        await self._fetch_append_events()
        self._status_task = asyncio.create_task(self._status_watch_loop())
        if self.follow_enabled and not self._terminal:
            self._poll_task = asyncio.create_task(self._event_follow_loop())

    async def on_unmount(self) -> None:
        for task in (self._poll_task, self._status_task):
            if task and not task.done():
                task.cancel()
                with contextlib.suppress(Exception):
                    await task

    async def _status_watch_loop(self):
        try:
            while True:
                job_raw = await asyncio.to_thread(self.client.job, self.job_id)
                job = Job.model_validate(job_raw)
                self.query_one("#job-title", Label).update(f"Job #{job.id} — {job.name} [{job.status}]")
                if job.is_terminal:
                    self._terminal = True
                    if self._poll_task and not self._poll_task.done():
                        self._poll_task.cancel()
                    break
                await asyncio.sleep(2.0)
        except asyncio.CancelledError:
            pass

    async def _event_follow_loop(self):
        try:
            while not self._terminal:
                appended = await self._fetch_append_events()
                await asyncio.sleep(0.5 if appended else 1.2)
        except asyncio.CancelledError:
            pass

    async def _fetch_append_events(self) -> int:
        data = await asyncio.to_thread(
            self.client.job_events,
            self.job_id,
            counter__gt=self._last_counter,
            order_by="counter",
            page_size=200,
        )
        page = Paginated.model_validate(data)
        count = 0
        for raw in page.results:
            evt = JobEvent.model_validate(raw)
            if evt.counter <= self._last_counter:
                continue
            self.log_widget.write_line(evt.stdout.rstrip("\n"))
            self._last_counter = max(self._last_counter, evt.counter)
            count += 1
        return count

    async def action_toggle_follow(self):
        self.follow_enabled = not self.follow_enabled
        if self.follow_enabled and not self._terminal:
            if not self._poll_task or self._poll_task.done():
                self._poll_task = asyncio.create_task(self._event_follow_loop())
        else:
            if self._poll_task and not self._poll_task.done():
                self._poll_task.cancel()

    async def action_export_stdout(self):
        txt = await asyncio.to_thread(self.client.job_stdout_txt, self.job_id, "txt_download")
        path = f"job_{self.job_id}_stdout.txt"
        with open(path, "w", encoding="utf-8") as f:
            f.write(txt)
        self.log_widget.write_line(f"\n[Saved] {path}")

    async def action_focus_search(self):
        self.log_widget.write_line("[Search not yet implemented — TODO]")

from __future__ import annotations
from textual.app import App
from .ui.screens.job_detail import JobDetailScreen
from .services.controller import ControllerClient

class AAPTui(App):
    CSS_PATH = None

    def __init__(self, base_url: str, token: str) -> None:
        super().__init__()
        self.client = ControllerClient(base_url=base_url, token=token)

    def open_job_detail(self, job_id: int):
        self.push_screen(JobDetailScreen(self.client, job_id))

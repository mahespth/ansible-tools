from __future__ import annotations
from typing import Optional, Literal, Dict, Any
from datetime import datetime
from pydantic import Field
from .common import OrjsonModel, SummaryFields

JobStatus = Literal[
    "new", "pending", "waiting", "running",
    "successful", "failed", "error", "canceled"
]

class Job(OrjsonModel):
    id: int
    name: str
    status: JobStatus
    job_type: Optional[Literal["run", "check", "scan"]] = None
    created: Optional[datetime] = None
    started: Optional[datetime] = None
    finished: Optional[datetime] = None
    elapsed: Optional[float] = None
    job_template: Optional[int] = None
    project: Optional[int] = None
    inventory: Optional[int] = None
    summary_fields: Optional[SummaryFields] = None
    @property
    def is_terminal(self) -> bool:
        return self.status in {"successful", "failed", "error", "canceled"}

class JobEvent(OrjsonModel):
    id: int
    event: Optional[str] = None
    counter: int
    created: Optional[datetime] = None
    event_display: Optional[str] = None
    stdout: str = ""
    host: Optional[str] = None
    failed: Optional[bool] = None
    event_data: Optional[Dict[str, Any]] = None

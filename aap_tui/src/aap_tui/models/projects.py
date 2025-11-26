from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import Field
from .common import OrjsonModel, SummaryFields

class Project(OrjsonModel):
    id: int
    name: str
    description: Optional[str] = None
    scm_type: Optional[str] = None
    scm_url: Optional[str] = None
    scm_branch: Optional[str] = None
    status: Optional[str] = None
    last_job_run: Optional[datetime] = None
    last_job_failed: Optional[bool] = None
    summary_fields: Optional[SummaryFields] = None

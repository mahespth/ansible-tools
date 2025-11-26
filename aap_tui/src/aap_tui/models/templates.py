from __future__ import annotations
from typing import Optional, Literal
from pydantic import Field
from .common import OrjsonModel, SummaryFields

class JobTemplate(OrjsonModel):
    id: int
    name: str
    description: Optional[str] = None
    job_type: Optional[Literal["run", "check", "scan"]] = None
    inventory: Optional[int] = None
    project: Optional[int] = None
    playbook: Optional[str] = None
    execution_environment: Optional[int] = None

    ask_inventory_on_launch: bool = False
    ask_variables_on_launch: bool = False
    ask_limit_on_launch: bool = False
    ask_tags_on_launch: bool = False
    ask_skip_tags_on_launch: bool = False
    ask_verbosity_on_launch: bool = False
    ask_credential_on_launch: bool = False
    ask_execution_environment_on_launch: bool = False
    ask_scm_branch_on_launch: bool = False

    survey_enabled: bool = False
    summary_fields: Optional[SummaryFields] = None

class WorkflowJobTemplate(OrjsonModel):
    id: int
    name: str
    description: Optional[str] = None
    survey_enabled: bool = False
    summary_fields: Optional[SummaryFields] = None

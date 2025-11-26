from __future__ import annotations
from typing import Optional, Dict, Any
from pydantic import Field
from .common import OrjsonModel, SummaryFields

class Inventory(OrjsonModel):
    id: int
    name: str
    description: Optional[str] = None
    kind: Optional[str] = None  # 'smart' | 'constructed' | None
    variables: Optional[str] = None
    summary_fields: Optional[SummaryFields] = None

class Host(OrjsonModel):
    id: int
    name: str
    description: Optional[str] = None
    enabled: Optional[bool] = True
    variables: Optional[str] = None
    last_job: Optional[int] = None

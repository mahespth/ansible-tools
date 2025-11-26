from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field

class OrjsonModel(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)

class RelatedRef(OrjsonModel):
    id: int
    name: Optional[str] = None

class SummaryFields(OrjsonModel):
    job_template: Optional[RelatedRef] = None
    inventory: Optional[RelatedRef] = None
    project: Optional[RelatedRef] = None
    organization: Optional[RelatedRef] = None

class Paginated(OrjsonModel):
    count: int
    next: Optional[str] = None
    previous: Optional[str] = None
    results: list[Dict[str, Any]] = Field(default_factory=list)

    def items_typed(self, model: type[BaseModel]):
        for item in self.results:
            yield model.model_validate(item)

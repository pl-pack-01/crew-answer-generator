from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FieldType(str, Enum):
    DROPDOWN = "dropdown"
    MULTI_SELECT = "multi_select"
    TEXT = "text"
    TEXTAREA = "textarea"
    DATE = "date"
    YES_NO = "yes_no"
    NUMBER = "number"


class SchemaStatus(str, Enum):
    DRAFT = "draft"
    LIVE = "live"
    ARCHIVED = "archived"


class ResponseStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"


class Condition(BaseModel):
    """Show this question only when a previous question has a specific answer."""
    question_id: str
    operator: str = "equals"  # equals, not_equals, contains, in
    value: str | list[str]


class Question(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    text: str
    field_type: FieldType
    options: list[str] = []
    required: bool = True
    default: Optional[str] = None
    help_text: Optional[str] = None
    screenshot_b64: Optional[str] = None
    section: Optional[str] = None
    conditions: list[Condition] = []


class Section(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str
    description: Optional[str] = None
    questions: list[Question] = []


class FormSchema(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    description: Optional[str] = None
    version: int = 1
    status: SchemaStatus = SchemaStatus.DRAFT
    created_at: datetime = Field(default_factory=datetime.now)
    source_filename: Optional[str] = None
    sections: list[Section] = []


class FormResponse(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    schema_id: str
    schema_version: int
    status: ResponseStatus = ResponseStatus.DRAFT
    draft_code: str = Field(default_factory=lambda: str(uuid.uuid4())[:8].upper())
    customer_name: Optional[str] = None
    answers: dict[str, str | list[str]] = {}
    submitted_at: Optional[datetime] = None
    signed_off: bool = False
    signed_off_at: Optional[datetime] = None
